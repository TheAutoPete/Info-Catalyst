import difflib
import ipaddress
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlparse

import httpx


APPLE_PODCASTS_HOST = "podcasts.apple.com"
ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"
PROVIDER = "apple_podcast_resolver"
USER_AGENT = "InfoCatalyst/1.0 (+apple-podcast-url-resolver)"
REQUEST_TIMEOUT_SECONDS = 10
MAX_FEED_BYTES = 5_000_000


@dataclass(frozen=True)
class ApplePodcastUrlParts:
    original_url: str
    country: str
    show_id: str
    episode_id: str
    path_slug: str
    query: dict[str, str]


@dataclass(frozen=True)
class PodcastEpisode:
    title: str
    audio_url: str
    audio_type: str
    guid: str = ""
    link: str = ""
    published_at: str = ""
    duration: str = ""
    description: str = ""


@dataclass(frozen=True)
class ApplePodcastResolutionResult:
    source_type: str
    source_url: str
    source_title: str
    show_title: str
    episode_url: str
    audio_url: str
    audio_type: str
    published_at: str
    duration: str
    provider: str
    match_status: str
    warnings: tuple[str, ...]
    debug_messages: tuple[str, ...]


class ApplePodcastResolverError(RuntimeError):
    def __init__(self, message: str, debug_messages: tuple[str, ...] = ()):
        super().__init__(message)
        self.debug_messages = debug_messages


@dataclass(frozen=True)
class _PodcastFeed:
    show_title: str
    episodes: tuple[PodcastEpisode, ...]


def parse_apple_podcast_url(url: str) -> ApplePodcastUrlParts:
    original_url = str(url or "").strip()
    parsed = urlparse(original_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname != APPLE_PODCASTS_HOST:
        raise ApplePodcastResolverError("Enter a valid Apple Podcasts URL from podcasts.apple.com.")
    if parsed.username or parsed.password:
        raise ApplePodcastResolverError("Apple Podcasts URL must not include credentials.")

    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts:
        raise ApplePodcastResolverError("Apple Podcasts URL is missing a podcast path.")

    country = ""
    if len(path_parts) >= 2 and path_parts[0].casefold() != "podcast":
        country = path_parts[0].casefold()
        podcast_index = 1
    else:
        podcast_index = 0

    if len(path_parts) <= podcast_index or path_parts[podcast_index].casefold() != "podcast":
        raise ApplePodcastResolverError("Unsupported Apple Podcasts URL path.")

    show_id = ""
    show_id_index = -1
    for index, part in enumerate(path_parts):
        match = re.fullmatch(r"id(\d+)", part)
        if match:
            show_id = match.group(1)
            show_id_index = index
            break
    if not show_id:
        raise ApplePodcastResolverError("Apple Podcasts URL is missing a show id.")

    slug_parts = path_parts[podcast_index + 1 : show_id_index]
    path_slug = "/".join(slug_parts)
    query = {key: values[-1] for key, values in parse_qs(parsed.query, keep_blank_values=True).items()}
    episode_id = query.get("i", "").strip()

    return ApplePodcastUrlParts(
        original_url=original_url,
        country=country,
        show_id=show_id,
        episode_id=episode_id,
        path_slug=path_slug,
        query=query,
    )


def resolve_apple_podcast_episode_url(url: str) -> ApplePodcastResolutionResult:
    debug_messages: list[str] = []
    warnings: list[str] = []
    parts = parse_apple_podcast_url(url)
    debug_messages.append(f"Parsed Apple Podcasts show id: {parts.show_id}")
    if parts.episode_id:
        debug_messages.append(f"Parsed Apple Podcasts episode id: {parts.episode_id}")
    else:
        warnings.append("Apple Podcasts URL did not include an episode id; matching will be conservative.")

    feed_url = _discover_feed_url(parts, debug_messages)
    if not feed_url:
        raise ApplePodcastResolverError(
            "Could not discover an RSS feed URL for this Apple Podcasts show.",
            tuple(debug_messages),
        )
    debug_messages.append(f"Discovered RSS feed URL: {feed_url}")

    try:
        feed_xml = _fetch_text(feed_url, expected_label="RSS feed")
    except ApplePodcastResolverError as exc:
        debug_messages.extend(exc.debug_messages)
        raise ApplePodcastResolverError(str(exc), tuple(debug_messages)) from exc
    feed = _parse_podcast_feed_with_show_title(feed_xml)
    debug_messages.append(f"Parsed RSS feed episodes with audio enclosures: {len(feed.episodes)}")

    title_hint = _lookup_episode_title_hint(parts, debug_messages)
    episode, match_status = _match_episode_with_status(
        feed.episodes,
        episode_id=parts.episode_id,
        episode_title_hint=title_hint,
        episode_url=parts.original_url,
    )
    if episode is None:
        raise ApplePodcastResolverError(
            "Could not confidently match the Apple Podcasts episode in the RSS feed.",
            tuple(debug_messages),
        )
    if match_status == "single_candidate":
        warnings.append("Only one feed episode had an audio enclosure, so it was selected.")
    if match_status == "probable":
        warnings.append("Episode was matched by title similarity, not by Apple episode id.")

    return ApplePodcastResolutionResult(
        source_type="apple_podcast_episode_url",
        source_url=parts.original_url,
        source_title=episode.title,
        show_title=feed.show_title,
        episode_url=episode.link or parts.original_url,
        audio_url=episode.audio_url,
        audio_type=episode.audio_type,
        published_at=episode.published_at,
        duration=episode.duration,
        provider=PROVIDER,
        match_status=match_status,
        warnings=tuple(warnings),
        debug_messages=tuple(debug_messages),
    )


def parse_podcast_feed(xml_text: str) -> tuple[PodcastEpisode, ...]:
    return _parse_podcast_feed_with_show_title(xml_text).episodes


def match_episode_from_feed(
    episodes: tuple[PodcastEpisode, ...],
    *,
    episode_id: str = "",
    episode_title_hint: str = "",
    episode_url: str = "",
) -> PodcastEpisode | None:
    episode, _status = _match_episode_with_status(
        episodes,
        episode_id=episode_id,
        episode_title_hint=episode_title_hint,
        episode_url=episode_url,
    )
    return episode


def _discover_feed_url(parts: ApplePodcastUrlParts, debug_messages: list[str]) -> str:
    params = {"id": parts.show_id, "entity": "podcast"}
    if parts.country:
        params["country"] = parts.country
    lookup_url = f"{ITUNES_LOOKUP_URL}?{urlencode(params)}"
    debug_messages.append(f"Fetching Apple metadata lookup for show id: {parts.show_id}")
    try:
        data = _fetch_json(lookup_url, expected_label="Apple metadata")
    except ApplePodcastResolverError as exc:
        debug_messages.extend(exc.debug_messages)
        raise ApplePodcastResolverError(str(exc), tuple(debug_messages)) from exc
    for result in data.get("results", []):
        feed_url = str(result.get("feedUrl") or "").strip()
        if feed_url:
            _validate_public_http_url(feed_url, "RSS feed URL")
            return feed_url
    debug_messages.append("Apple metadata did not include a feedUrl.")
    return ""


def _lookup_episode_title_hint(parts: ApplePodcastUrlParts, debug_messages: list[str]) -> str:
    if not parts.episode_id:
        return ""
    lookup_url = f"{ITUNES_LOOKUP_URL}?{urlencode({'id': parts.episode_id})}"
    try:
        debug_messages.append(f"Fetching Apple metadata lookup for episode id: {parts.episode_id}")
        data = _fetch_json(lookup_url, expected_label="Apple episode metadata")
    except ApplePodcastResolverError as exc:
        debug_messages.extend(exc.debug_messages)
        debug_messages.append("Apple episode metadata lookup failed; continuing without a title hint.")
        return ""
    for result in data.get("results", []):
        title = str(result.get("trackName") or result.get("collectionName") or "").strip()
        if title:
            debug_messages.append(f"Apple episode title hint: {title}")
            return title
    debug_messages.append("Apple episode metadata did not include a title hint.")
    return ""


def _parse_podcast_feed_with_show_title(xml_text: str) -> _PodcastFeed:
    try:
        root = ET.fromstring(str(xml_text or "").encode("utf-8"))
    except ET.ParseError as exc:
        raise ApplePodcastResolverError("RSS feed XML could not be parsed.") from exc

    channel_node = _first_child(root, "channel")
    channel = channel_node if channel_node is not None else root
    show_title = _child_text(channel, "title")
    episodes: list[PodcastEpisode] = []
    for item in _children(channel, "item"):
        enclosure = _first_child(item, "enclosure")
        audio_url = str(enclosure.attrib.get("url", "") if enclosure is not None else "").strip()
        if not audio_url:
            continue
        audio_type = str(enclosure.attrib.get("type", "") if enclosure is not None else "").strip()
        if audio_type and not audio_type.casefold().startswith("audio/"):
            continue
        episodes.append(
            PodcastEpisode(
                title=_child_text(item, "title"),
                audio_url=audio_url,
                audio_type=audio_type,
                guid=_child_text(item, "guid"),
                link=_child_text(item, "link"),
                published_at=_child_text(item, "pubDate"),
                duration=_child_text(item, "duration"),
                description=_child_text(item, "description"),
            )
        )
    return _PodcastFeed(show_title=show_title, episodes=tuple(episodes))


def _match_episode_with_status(
    episodes: tuple[PodcastEpisode, ...],
    *,
    episode_id: str = "",
    episode_title_hint: str = "",
    episode_url: str = "",
) -> tuple[PodcastEpisode | None, str]:
    clean_episode_id = str(episode_id or "").strip()
    if clean_episode_id:
        for episode in episodes:
            haystack = "\n".join([episode.guid, episode.link, episode.audio_url])
            if clean_episode_id in haystack:
                return episode, "exact"

    clean_episode_url = str(episode_url or "").strip()
    if clean_episode_url:
        for episode in episodes:
            if clean_episode_url in {episode.link, episode.guid, episode.audio_url}:
                return episode, "exact"

    title_hint = str(episode_title_hint or "").strip()
    if title_hint:
        for episode in episodes:
            if episode.title.strip().casefold() == title_hint.casefold():
                return episode, "exact"

        normalized_hint = _normalize_title(title_hint)
        probable_matches = [
            episode
            for episode in episodes
            if normalized_hint
            and difflib.SequenceMatcher(None, normalized_hint, _normalize_title(episode.title)).ratio() >= 0.94
        ]
        if len(probable_matches) == 1:
            return probable_matches[0], "probable"

    if len(episodes) == 1:
        return episodes[0], "single_candidate"
    return None, "not_found"


def _fetch_json(url: str, *, expected_label: str) -> dict:
    _validate_public_http_url(url, expected_label)
    try:
        with httpx.Client(
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        ) as client:
            response = client.get(url)
            if response.status_code >= 400:
                raise ApplePodcastResolverError(f"{expected_label} fetch failed with HTTP {response.status_code}.")
            return response.json()
    except ApplePodcastResolverError:
        raise
    except httpx.TimeoutException as exc:
        raise ApplePodcastResolverError(f"{expected_label} fetch timed out.") from exc
    except httpx.HTTPError as exc:
        raise ApplePodcastResolverError(f"{expected_label} fetch failed: {exc}") from exc
    except ValueError as exc:
        raise ApplePodcastResolverError(f"{expected_label} response was not valid JSON.") from exc


def _fetch_text(url: str, *, expected_label: str) -> str:
    _validate_public_http_url(url, expected_label)
    try:
        with httpx.Client(
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml, */*"},
        ) as client:
            with client.stream("GET", url) as response:
                if response.status_code >= 400:
                    raise ApplePodcastResolverError(f"{expected_label} fetch failed with HTTP {response.status_code}.")
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > MAX_FEED_BYTES:
                        raise ApplePodcastResolverError(f"{expected_label} response was too large.")
                    chunks.append(chunk)
                encoding = response.encoding or "utf-8"
                return b"".join(chunks).decode(encoding, errors="replace")
    except ApplePodcastResolverError:
        raise
    except httpx.TimeoutException as exc:
        raise ApplePodcastResolverError(f"{expected_label} fetch timed out.") from exc
    except httpx.HTTPError as exc:
        raise ApplePodcastResolverError(f"{expected_label} fetch failed: {exc}") from exc


def _validate_public_http_url(url: str, label: str) -> None:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ApplePodcastResolverError(f"{label} must be an http:// or https:// URL.")
    host = (parsed.hostname or "").strip().strip("[]").casefold()
    if not host:
        raise ApplePodcastResolverError(f"{label} is missing a hostname.")
    if host in {"localhost", "0.0.0.0"} or host.endswith(".localhost"):
        raise ApplePodcastResolverError(f"{label} cannot point to localhost.")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        raise ApplePodcastResolverError(f"{label} cannot point to a private network address.")


def _children(element: ET.Element, local_name: str) -> list[ET.Element]:
    return [child for child in list(element) if _local_name(child.tag) == local_name]


def _first_child(element: ET.Element, local_name: str) -> ET.Element | None:
    for child in list(element):
        if _local_name(child.tag) == local_name:
            return child
    return None


def _child_text(element: ET.Element, local_name: str) -> str:
    child = _first_child(element, local_name)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def _local_name(tag: str) -> str:
    return str(tag or "").rsplit("}", 1)[-1]


def _normalize_title(title: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(title or "").casefold())
    return " ".join(text.split())
