import pytest

from services.article_extractor import (
    ArticleExtractionError,
    clean_article_text,
    extract_article_from_html,
    extract_article_from_url,
    stable_article_source_id,
)


LONG_PARAGRAPH = (
    "This paragraph contains enough useful article content for deterministic extraction tests. "
    "It describes the main topic with concrete details and avoids relying on any external network call."
)


def test_extract_title_from_title_tag():
    result = extract_article_from_html(
        f"<html><head><title>Plain Title</title></head><body><article><p>{LONG_PARAGRAPH}</p></article></body></html>"
    )

    assert result.source_title == "Plain Title"


def test_og_title_is_preferred_over_title_tag():
    result = extract_article_from_html(
        (
            "<html><head><meta property='og:title' content='Open Graph Title'>"
            "<title>Plain Title</title></head>"
            f"<body><article><p>{LONG_PARAGRAPH}</p></article></body></html>"
        )
    )

    assert result.source_title == "Open Graph Title"


def test_extract_text_from_article_element():
    result = extract_article_from_html(
        f"<html><body><article><p>{LONG_PARAGRAPH}</p><p>Second paragraph adds detail.</p></article></body></html>"
    )

    assert LONG_PARAGRAPH in result.text
    assert "Second paragraph adds detail." in result.text


def test_extract_paragraph_text_from_body_fallback():
    result = extract_article_from_html(
        f"<html><body><section><p>{LONG_PARAGRAPH}</p><p>Fallback body paragraph with useful context.</p></section></body></html>"
    )

    assert LONG_PARAGRAPH in result.text
    assert "Fallback body paragraph" in result.text


def test_strip_script_style_nav_and_footer_text():
    result = extract_article_from_html(
        (
            "<html><body><nav><p>Navigation should disappear from extracted text.</p></nav>"
            "<style>.x{display:none}</style><script>alert('x')</script>"
            f"<article><p>{LONG_PARAGRAPH}</p></article>"
            "<footer><p>Footer should disappear from extracted text.</p></footer></body></html>"
        )
    )

    assert LONG_PARAGRAPH in result.text
    assert "Navigation should disappear" not in result.text
    assert "Footer should disappear" not in result.text
    assert "display:none" not in result.text


def test_clean_article_text_collapses_whitespace():
    assert clean_article_text("  One\t\t two \n\n\n three&nbsp; ") == "One two\n\nthree"


def test_reject_unsupported_url_scheme():
    with pytest.raises(ArticleExtractionError, match="http:// or https://"):
        extract_article_from_url("file:///tmp/article.html")


def test_reject_localhost_url():
    with pytest.raises(ArticleExtractionError, match="Localhost and private network"):
        extract_article_from_url("http://localhost:8501/article")


def test_handle_empty_html_gracefully():
    with pytest.raises(ArticleExtractionError, match="No HTML content"):
        extract_article_from_html("")


def test_handle_too_short_extraction_gracefully():
    with pytest.raises(ArticleExtractionError, match="too short"):
        extract_article_from_html("<html><body><article><p>Too short.</p></article></body></html>")


def test_warn_when_extracted_text_is_short_but_useful():
    result = extract_article_from_html(
        (
            "<html><body><article><p>"
            "This is useful but still shorter than a normal article. It contains enough characters to be editable."
            " Additional useful detail keeps the parser from rejecting it outright."
            "</p></article></body></html>"
        )
    )

    assert result.warnings
    assert "short" in result.warnings[0].casefold()


def test_stable_article_source_id_is_deterministic_and_filename_safe():
    source_id = stable_article_source_id("https://Example.com/Article Path/?q=AI")

    assert source_id.startswith("article-")
    assert source_id == stable_article_source_id("https://example.com/Article Path/?q=AI")
    assert "/" not in source_id
    assert len(source_id) <= 32
