from ui.source_section import prepared_from_article_url, prepared_from_manual_text, stable_manual_source_id


def test_manual_text_prepared_object_has_source_fields():
    source_id = stable_manual_source_id(
        source_title="Semiconductor Notes",
        source_url="https://example.com/article",
        text="manual body",
    )

    prepared = prepared_from_manual_text(
        text="manual body",
        source_title="Semiconductor Notes",
        source_url="https://example.com/article",
        language="en",
        source_id=source_id,
    )

    assert prepared["text"] == "manual body"
    assert prepared["source"] == "manual_text"
    assert prepared["provider"] == "manual_text"
    assert prepared["source_type"] == "manual_text"
    assert prepared["source_title"] == "Semiconductor Notes"
    assert prepared["source_url"] == "https://example.com/article"
    assert prepared["source_id"] == source_id
    assert prepared["language"] == "en"
    assert prepared["cache_path"] == ""
    assert prepared["available_transcripts"] == []
    assert prepared["debug_messages"] == []


def test_manual_text_source_id_does_not_require_youtube_url():
    source_id = stable_manual_source_id(source_title="Copied Notes", source_url="", text="notes body")

    assert source_id.startswith("manual-")
    assert source_id == stable_manual_source_id(source_title="Copied Notes", source_url="", text="notes body")


def test_manual_text_source_id_prefers_source_url_when_provided():
    first = stable_manual_source_id(source_title="Title A", source_url="https://example.com/a", text="body one")
    second = stable_manual_source_id(source_title="Title B", source_url="https://example.com/a", text="body two")

    assert first == second


def test_article_url_prepared_object_has_expected_metadata_fields():
    prepared = prepared_from_article_url(
        text="article body",
        source_title="Public Article",
        source_url="https://example.com/public-article",
        source_id="article-abc123",
        debug_messages=["short extraction warning"],
    )

    assert prepared["text"] == "article body"
    assert prepared["source"] == "article_url"
    assert prepared["provider"] == "article_extractor"
    assert prepared["language"] == "unknown"
    assert prepared["source_type"] == "article_url"
    assert prepared["source_title"] == "Public Article"
    assert prepared["source_url"] == "https://example.com/public-article"
    assert prepared["source_id"] == "article-abc123"
    assert prepared["cache_path"] == ""
    assert prepared["available_transcripts"] == []
    assert prepared["debug_messages"] == ["short extraction warning"]
