import httpx
import pytest

from services import apple_podcast_resolver as resolver
from services.apple_podcast_resolver import (
    ApplePodcastResolverError,
    match_episode_from_feed,
    parse_apple_podcast_url,
    parse_podcast_feed,
    resolve_apple_podcast_episode_url,
)


RSS_XML = """\
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Example Podcast</title>
    <item>
      <title>Episode 100: AI Infrastructure</title>
      <guid>episode-1000654321000</guid>
      <link>https://example.com/episodes/ai-infrastructure</link>
      <pubDate>Sun, 14 Jun 2026 10:00:00 GMT</pubDate>
      <itunes:duration>01:12:30</itunes:duration>
      <description>Example description</description>
      <enclosure url="https://cdn.example.com/episode100.mp3" type="audio/mpeg" />
    </item>
    <item>
      <title>Episode 99: No Enclosure</title>
      <guid>episode-99</guid>
      <link>https://example.com/episodes/no-enclosure</link>
    </item>
    <item>
      <title>Episode 98: Product Systems</title>
      <guid>episode-98</guid>
      <link>https://example.com/episodes/product-systems</link>
      <pubDate>Sat, 13 Jun 2026 10:00:00 GMT</pubDate>
      <itunes:duration>00:42:00</itunes:duration>
      <description>Second description</description>
      <enclosure url="https://cdn.example.com/episode98.mp3" type="audio/mpeg" />
    </item>
  </channel>
</rss>
"""


def test_parses_apple_podcasts_episode_url_with_country_show_id_and_episode_id():
    parts = parse_apple_podcast_url(
        "https://podcasts.apple.com/us/podcast/show-name/id123456789?i=1000654321000"
    )

    assert parts.country == "us"
    assert parts.show_id == "123456789"
    assert parts.episode_id == "1000654321000"
    assert parts.path_slug == "show-name"
    assert parts.query == {"i": "1000654321000"}


def test_parses_apple_podcasts_url_without_explicit_country():
    parts = parse_apple_podcast_url("https://podcasts.apple.com/podcast/show-name/id123456789?i=1000654321000")

    assert parts.country == ""
    assert parts.show_id == "123456789"
    assert parts.episode_id == "1000654321000"


def test_rejects_non_apple_url():
    with pytest.raises(ApplePodcastResolverError, match="Apple Podcasts URL"):
        parse_apple_podcast_url("https://example.com/podcast/show-name/id123456789?i=1000654321000")


def test_rejects_malformed_apple_podcasts_url():
    with pytest.raises(ApplePodcastResolverError, match="show id"):
        parse_apple_podcast_url("https://podcasts.apple.com/us/podcast/show-name")


def test_parses_rss_xml_with_multiple_audio_items_and_ignores_items_without_enclosure():
    episodes = parse_podcast_feed(RSS_XML)

    assert len(episodes) == 2
    assert [episode.title for episode in episodes] == [
        "Episode 100: AI Infrastructure",
        "Episode 98: Product Systems",
    ]


def test_extracts_feed_show_title_through_resolution(monkeypatch):
    monkeypatch.setattr(
        resolver,
        "_fetch_json",
        lambda url, expected_label: {"results": [{"feedUrl": "https://feeds.example.com/show.xml"}]},
    )
    monkeypatch.setattr(resolver, "_fetch_text", lambda url, expected_label: RSS_XML)

    result = resolve_apple_podcast_episode_url(
        "https://podcasts.apple.com/us/podcast/show-name/id123456789?i=1000654321000"
    )

    assert result.show_title == "Example Podcast"
    assert result.source_title == "Episode 100: AI Infrastructure"
    assert result.audio_url == "https://cdn.example.com/episode100.mp3"
    assert result.audio_type == "audio/mpeg"
    assert result.match_status == "exact"


def test_extracts_item_metadata_from_rss_xml():
    episode = parse_podcast_feed(RSS_XML)[0]

    assert episode.title == "Episode 100: AI Infrastructure"
    assert episode.guid == "episode-1000654321000"
    assert episode.link == "https://example.com/episodes/ai-infrastructure"
    assert episode.published_at == "Sun, 14 Jun 2026 10:00:00 GMT"
    assert episode.duration == "01:12:30"
    assert episode.description == "Example description"
    assert episode.audio_url == "https://cdn.example.com/episode100.mp3"
    assert episode.audio_type == "audio/mpeg"


@pytest.mark.parametrize(
    "episodes_xml, episode_id",
    [
        (RSS_XML, "1000654321000"),
        (RSS_XML.replace("https://example.com/episodes/ai-infrastructure", "https://example.com/1000654321000"), "1000654321000"),
        (RSS_XML.replace("https://cdn.example.com/episode100.mp3", "https://cdn.example.com/1000654321000.mp3"), "1000654321000"),
    ],
)
def test_matches_episode_by_episode_id_in_guid_link_or_enclosure(episodes_xml, episode_id):
    episodes = parse_podcast_feed(episodes_xml)

    episode = match_episode_from_feed(episodes, episode_id=episode_id)

    assert episode is not None
    assert episode.title == "Episode 100: AI Infrastructure"


def test_matches_episode_by_exact_title_hint_if_provided():
    episodes = parse_podcast_feed(RSS_XML)

    episode = match_episode_from_feed(episodes, episode_title_hint="Episode 98: Product Systems")

    assert episode is not None
    assert episode.audio_url == "https://cdn.example.com/episode98.mp3"


def test_matches_episode_by_low_risk_normalized_title_similarity():
    episodes = parse_podcast_feed(RSS_XML)

    episode = match_episode_from_feed(episodes, episode_title_hint="Episode 98 - Product Systems")

    assert episode is not None
    assert episode.audio_url == "https://cdn.example.com/episode98.mp3"


def test_handles_malformed_xml_gracefully():
    with pytest.raises(ApplePodcastResolverError, match="XML could not be parsed"):
        parse_podcast_feed("<rss><channel><item></rss>")


def test_handles_missing_feed_url_gracefully(monkeypatch):
    monkeypatch.setattr(resolver, "_fetch_json", lambda url, expected_label: {"results": [{}]})

    with pytest.raises(ApplePodcastResolverError, match="Could not discover"):
        resolve_apple_podcast_episode_url(
            "https://podcasts.apple.com/us/podcast/show-name/id123456789?i=1000654321000"
        )


def test_handles_http_timeout_with_debug_messages(monkeypatch):
    monkeypatch.setattr(resolver.httpx, "Client", lambda *args, **kwargs: TimeoutClient())

    with pytest.raises(ApplePodcastResolverError) as exc_info:
        resolve_apple_podcast_episode_url(
            "https://podcasts.apple.com/us/podcast/show-name/id123456789?i=1000654321000"
        )

    assert "timed out" in str(exc_info.value)
    assert "Parsed Apple Podcasts show id: 123456789" in exc_info.value.debug_messages
    assert "Fetching Apple metadata lookup for show id: 123456789" in exc_info.value.debug_messages


def test_handles_http_error_with_debug_messages(monkeypatch):
    monkeypatch.setattr(resolver.httpx, "Client", lambda *args, **kwargs: HttpErrorClient())

    with pytest.raises(ApplePodcastResolverError) as exc_info:
        resolve_apple_podcast_episode_url(
            "https://podcasts.apple.com/us/podcast/show-name/id123456789?i=1000654321000"
        )

    assert "HTTP 503" in str(exc_info.value)
    assert "Fetching Apple metadata lookup for show id: 123456789" in exc_info.value.debug_messages


def test_resolver_uses_mocked_metadata_and_feed_to_return_direct_audio_url(monkeypatch):
    calls = []

    def fake_fetch_json(url, expected_label):
        calls.append((url, expected_label))
        if "id=123456789" in url:
            return {"results": [{"feedUrl": "https://feeds.example.com/show.xml"}]}
        if "id=1000654321000" in url:
            return {"results": [{"trackName": "Episode 100: AI Infrastructure"}]}
        return {"results": []}

    monkeypatch.setattr(resolver, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(resolver, "_fetch_text", lambda url, expected_label: RSS_XML)

    result = resolve_apple_podcast_episode_url(
        "https://podcasts.apple.com/tw/podcast/show-name/id123456789?i=1000654321000"
    )

    assert result.source_type == "apple_podcast_episode_url"
    assert result.source_url == "https://podcasts.apple.com/tw/podcast/show-name/id123456789?i=1000654321000"
    assert result.audio_url == "https://cdn.example.com/episode100.mp3"
    assert result.provider == "apple_podcast_resolver"
    assert "Apple metadata" in calls[0][1]


def test_no_single_candidate_success_when_multiple_candidates_are_ambiguous():
    episodes = parse_podcast_feed(RSS_XML)

    episode = match_episode_from_feed(episodes, episode_id="missing")

    assert episode is None


class TimeoutClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url):
        raise httpx.TimeoutException("timeout")


class HttpErrorClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url):
        return FakeHttpResponse(503)


class FakeHttpResponse:
    def __init__(self, status_code):
        self.status_code = status_code
