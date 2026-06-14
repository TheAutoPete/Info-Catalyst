import hashlib
import ipaddress
import re
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


PROVIDER = "article_extractor"
USER_AGENT = "InfoCatalyst/1.0 (+https://localhost; best-effort article extraction)"
MAX_RESPONSE_BYTES = 2_000_000
REQUEST_TIMEOUT_SECONDS = 10
MIN_ARTICLE_TEXT_CHARS = 500
MIN_USEFUL_TEXT_CHARS = 120


class ArticleExtractionError(Exception):
    pass


@dataclass(frozen=True)
class ArticleExtractionResult:
    source_url: str
    source_title: str
    text: str
    provider: str
    extracted_at: str
    warnings: list[str]


def stable_article_source_id(url: str) -> str:
    normalized = _normalize_url_for_id(url)
    if not normalized:
        return "article-url"
    return f"article-{hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]}"


def extract_article_from_url(url: str) -> ArticleExtractionResult:
    parsed = _validate_public_http_url(url)
    html = _fetch_html(url.strip())
    return extract_article_from_html(html, source_url=parsed.geturl())


def extract_article_from_html(html: str, *, source_url: str = "") -> ArticleExtractionResult:
    warnings: list[str] = []
    if not str(html or "").strip():
        raise ArticleExtractionError("No HTML content was available to extract.")

    soup = BeautifulSoup(html, "html.parser")
    _strip_boilerplate(soup)

    title = _extract_title(soup, source_url=source_url)
    text = clean_article_text(_extract_readable_text(soup))
    if not text:
        raise ArticleExtractionError("No readable article text was found.")
    if len(text) < MIN_USEFUL_TEXT_CHARS:
        raise ArticleExtractionError("The extracted article text was too short to use.")
    if len(text) < MIN_ARTICLE_TEXT_CHARS:
        warnings.append(
            "Extracted text is short. The page may be paywalled, JavaScript-rendered, or mostly boilerplate."
        )

    return ArticleExtractionResult(
        source_url=source_url,
        source_title=title,
        text=text,
        provider=PROVIDER,
        extracted_at=datetime.now().isoformat(timespec="seconds"),
        warnings=warnings,
    )


def clean_article_text(text: str) -> str:
    text = unescape(str(text or ""))
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _fetch_html(url: str) -> str:
    try:
        with httpx.Client(
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
            max_redirects=5,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        ) as client:
            with client.stream("GET", url) as response:
                if response.status_code >= 400:
                    raise ArticleExtractionError(f"Article fetch failed with HTTP {response.status_code}.")

                content_type = response.headers.get("content-type", "").casefold()
                if content_type and "html" not in content_type and "text/plain" not in content_type:
                    raise ArticleExtractionError("The URL did not return an HTML page.")

                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > MAX_RESPONSE_BYTES:
                        raise ArticleExtractionError("The page was too large to extract safely.")
                    chunks.append(chunk)

                encoding = response.encoding or "utf-8"
                return b"".join(chunks).decode(encoding, errors="replace")
    except ArticleExtractionError:
        raise
    except httpx.TimeoutException as exc:
        raise ArticleExtractionError("Article fetch timed out.") from exc
    except httpx.HTTPError as exc:
        raise ArticleExtractionError("Article fetch failed. The site may block automated requests.") from exc


def _validate_public_http_url(url: str):
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        raise ArticleExtractionError("Article URL must start with http:// or https://.")
    if not parsed.netloc:
        raise ArticleExtractionError("Article URL is missing a hostname.")
    if _is_local_or_private_host(parsed.hostname or ""):
        raise ArticleExtractionError("Localhost and private network URLs are not supported for article extraction.")
    return parsed


def _is_local_or_private_host(hostname: str) -> bool:
    host = hostname.strip().strip("[]").casefold()
    if not host:
        return True
    if host in {"localhost", "0.0.0.0"} or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved


def _strip_boilerplate(soup: BeautifulSoup) -> None:
    selectors = [
        "script",
        "style",
        "noscript",
        "nav",
        "footer",
        "header",
        "form",
        "aside",
        "[aria-hidden='true']",
        ".advertisement",
        ".ads",
        ".cookie",
        ".newsletter",
        ".related",
        ".share",
        ".social",
        "#comments",
    ]
    for element in soup.select(",".join(selectors)):
        element.decompose()


def _extract_title(soup: BeautifulSoup, *, source_url: str) -> str:
    og_title = soup.find("meta", attrs={"property": "og:title"}) or soup.find("meta", attrs={"name": "og:title"})
    if og_title and og_title.get("content"):
        return clean_article_text(og_title["content"])
    if soup.title and soup.title.get_text(strip=True):
        return clean_article_text(soup.title.get_text(" ", strip=True))
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return clean_article_text(h1.get_text(" ", strip=True))
    return _fallback_title_from_url(source_url)


def _extract_readable_text(soup: BeautifulSoup) -> str:
    root = soup.find("article") or soup.find("main") or soup.body or soup
    paragraphs = []
    for element in root.find_all(["p", "h2", "h3", "li", "blockquote"]):
        text = clean_article_text(element.get_text(" ", strip=True))
        if len(text) >= 20:
            paragraphs.append(text)
    if not paragraphs:
        text = root.get_text("\n", strip=True)
        return clean_article_text(text)
    return clean_article_text("\n\n".join(paragraphs))


def _fallback_title_from_url(source_url: str) -> str:
    parsed = urlparse(source_url or "")
    path = parsed.path.strip("/").replace("-", " ").replace("_", " ")
    title = " ".join(part for part in (parsed.hostname or "", path) if part)
    return clean_article_text(title) or "Article URL"


def _normalize_url_for_id(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return str(url or "").strip()
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{scheme}://{netloc}{path}{query}"
