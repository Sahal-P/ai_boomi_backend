# Agent 3 shared setup requests

No additional Python dependency or schema change. Use locked httpx/OpenAI/stdlib.
System ffmpeg + ffprobe are required (both present locally in /opt/homebrew/bin).
Bootstrap already provides configurable GEMINI_TTS_BASE_URL, RESEMBLE_TTS_BASE_URL,
FFMPEG_BINARY, FFPROBE_BINARY and timeout/size settings.

Human explicitly approved **Resemble Ultra using the existing credit** after seeing
that hosted Chatterbox is end-of-life. This supersedes the interim Replicate approval.
No Replicate settings/dependency are needed. Use the existing bootstrap Resemble
settings; require `RESEMBLE_TTS_MODEL=resemble-ultra` plus verified stock voice IDs
in the private environment. Live English/Hindi sample verification is pending.

Gemini /models and one real synthetic /interactions request verified
`gemini-3.8-flash-tts`, stock Kore, store=false, audio/wav output → actual MP3.
Set the chosen model/voice only in ignored environment files. Model/voice remain
blank in committed examples. GEMINI_API_KEY was copied directly from the human-
authorized Layover project to the private secrets file; never expose its value.
