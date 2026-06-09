from services.transcript_provider import _select_transcript, _youtube_http_client


class FakeTranscript:
    def __init__(self, language_code, is_generated=False):
        self.language_code = language_code
        self.language = language_code
        self.is_generated = is_generated
        self.is_translatable = False
        self.translation_languages = []


class FakeTranscriptList:
    def __init__(self, transcripts, selected=None):
        self.transcripts = transcripts
        self.selected = selected

    def __iter__(self):
        return iter(self.transcripts)


def test_select_transcript_uses_language_priority():
    preferred = FakeTranscript("zh-TW")
    transcript_list = FakeTranscriptList(
        [FakeTranscript("en"), preferred],
    )

    assert _select_transcript(transcript_list, tuple(transcript_list)) is preferred


def test_select_transcript_prefers_manual_transcripts():
    generated_preferred = FakeTranscript("zh-TW", is_generated=True)
    manual_available = FakeTranscript("en")
    transcript_list = FakeTranscriptList([generated_preferred, manual_available])

    assert _select_transcript(transcript_list, tuple(transcript_list)) is manual_available


def test_select_transcript_uses_generated_preferred_language_when_no_manual_match():
    generated_preferred = FakeTranscript("zh-TW", is_generated=True)
    transcript_list = FakeTranscriptList([FakeTranscript("fr"), generated_preferred])

    assert _select_transcript(transcript_list, tuple(transcript_list)) is generated_preferred


def test_select_transcript_uses_chinese_language_priority():
    preferred = FakeTranscript("zh-Hans")
    transcript_list = FakeTranscriptList([FakeTranscript("zh-CN"), preferred, FakeTranscript("en")])

    assert _select_transcript(transcript_list, tuple(transcript_list)) is preferred


def test_select_transcript_falls_back_to_first_available():
    first_available = FakeTranscript("fr")
    transcript_list = FakeTranscriptList([first_available, FakeTranscript("de")])

    assert _select_transcript(transcript_list, tuple(transcript_list)) is first_available


def test_youtube_http_client_ignores_environment_proxies():
    assert _youtube_http_client().trust_env is False
