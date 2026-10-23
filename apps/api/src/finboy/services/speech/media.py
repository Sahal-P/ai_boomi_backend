"""Bounded pipe-only media decoding. No temporary audio files or network protocols."""

import io
import json
import subprocess
import wave

from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable

MAX_PROVIDER_AUDIO_BYTES = 12 * 1024 * 1024
SAMPLE_RATE = 24000
MIME_FORMATS = {
    "audio/wav": {"wav"},
    "audio/x-wav": {"wav"},
    "audio/wave": {"wav"},
    "audio/mpeg": {"mp3"},
    "audio/mp3": {"mp3"},
    "audio/webm": {"matroska", "webm"},
    "audio/ogg": {"ogg"},
    "audio/mp4": {"mov", "mp4", "m4a", "3gp", "3g2", "mj2"},
    "audio/x-m4a": {"mov", "mp4", "m4a", "3gp", "3g2", "mj2"},
}


class InvalidAudio(ValueError):
    """Fixed user-input error, never a decoder exception message."""

    def __init__(self, status_code: int = 422) -> None:
        self.status_code = status_code
        super().__init__("invalid_audio")


def run_media(command: list[str], data: bytes) -> bytes:
    try:
        result = subprocess.run(command, input=data, capture_output=True, timeout=10, check=True)
        return result.stdout
    except FileNotFoundError:
        raise ProviderUnavailable("speech_unavailable") from None
    except subprocess.SubprocessError, OSError:
        raise InvalidAudio() from None


def decode_audio(
    *, audio: bytes, content_type: str, settings: Settings, max_bytes: int, max_seconds: int
) -> bytes:
    if not audio:
        raise InvalidAudio()
    if len(audio) > max_bytes:
        raise InvalidAudio(413)
    mime = content_type.split(";", 1)[0].strip().lower()
    if mime not in MIME_FORMATS:
        raise InvalidAudio(415)
    output = run_media(
        [
            settings.ffprobe_binary,
            "-v",
            "error",
            "-protocol_whitelist",
            "pipe",
            "-show_entries",
            "format=format_name:stream=codec_type,codec_name",
            "-of",
            "json",
            "-i",
            "pipe:0",
        ],
        audio,
    )
    try:
        probe = json.loads(output)
        streams = probe["streams"]
        formats = set(probe["format"]["format_name"].split(","))
        if not streams or len(streams) != 1 or streams[0]["codec_type"] != "audio":
            raise InvalidAudio()
        if not formats.intersection(MIME_FORMATS[mime]):
            raise InvalidAudio(415)
    except InvalidAudio:
        raise
    except KeyError, TypeError, ValueError:
        raise InvalidAudio() from None
    pcm = run_media(
        [
            settings.ffmpeg_binary,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-protocol_whitelist",
            "pipe",
            "-err_detect",
            "explode",
            "-xerror",
            "-i",
            "pipe:0",
            "-map",
            "0:a:0",
            "-vn",
            "-sn",
            "-dn",
            "-t",
            str(max_seconds + 0.1),
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            "-f",
            "s16le",
            "pipe:1",
        ],
        audio,
    )
    if not pcm or len(pcm) > max_seconds * SAMPLE_RATE * 2:
        raise InvalidAudio()
    return pcm


def pcm_to_wav(pcm: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    if not pcm or len(pcm) % 2 or not 8000 <= sample_rate <= 48000:
        raise InvalidAudio()
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return output.getvalue()


def to_mp3(audio: bytes, content_type: str, settings: Settings) -> bytes:
    pcm = decode_audio(
        audio=audio,
        content_type=content_type,
        settings=settings,
        max_bytes=MAX_PROVIDER_AUDIO_BYTES,
        max_seconds=180,
    )
    return run_media(
        [
            settings.ffmpeg_binary,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-f",
            "s16le",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            "-i",
            "pipe:0",
            "-map_metadata",
            "-1",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "64k",
            "-f",
            "mp3",
            "pipe:1",
        ],
        pcm,
    )
