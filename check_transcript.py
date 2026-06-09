from youtube_transcript_api import YouTubeTranscriptApi

video_id = "8H0D_RYS-zQ"

ytt_api = YouTubeTranscriptApi()

try:
    transcript_list = ytt_api.list(video_id)

    print("Available transcripts:")
    for transcript in transcript_list:
        print(
            f"- language={transcript.language}, "
            f"code={transcript.language_code}, "
            f"generated={transcript.is_generated}, "
            f"translatable={transcript.is_translatable}"
        )

except Exception as e:
    print("ERROR TYPE:", type(e).__name__)
    print("ERROR:", e)
