from services.output_languages import (
    DEFAULT_OUTPUT_LANGUAGE,
    get_default_output_language,
    get_output_language,
    get_output_language_labels,
)


def test_output_language_profiles_exist_and_default_to_traditional_chinese():
    labels = get_output_language_labels()
    default_language = get_default_output_language()

    assert labels == ["Traditional Chinese", "English", "Japanese"]
    assert DEFAULT_OUTPUT_LANGUAGE == "zh-TW"
    assert default_language.label == "Traditional Chinese"
    assert default_language.code == "zh-TW"
    assert get_output_language("en").label == "English"
    assert get_output_language("ja").label == "Japanese"
    assert get_output_language("missing").code == "zh-TW"
