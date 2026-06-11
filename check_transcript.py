from services.transcript_provider import TranscriptError, fetch_transcript_result


video_id = "8H0D_RYS-zQ"

try:
    result = fetch_transcript_result(video_id)
    print("Selected transcript:")
    print(
        f"- language={result.selected_transcript.language}, "
        f"code={result.selected_transcript.language_code}, "
        f"generated={result.selected_transcript.is_generated}, "
        f"provider={result.transcript_provider}"
    )
    print(f"Items: {result.item_count}")
except TranscriptError as exc:
    print("ERROR TYPE:", type(exc).__name__)
    print("ERROR:", exc)
