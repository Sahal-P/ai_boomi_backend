"""Bounded in-memory multipart parsing; Starlette UploadFile may spool to disk."""

from dataclasses import dataclass, field

from python_multipart import MultipartParser
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import parse_options_header
from starlette.requests import Request

from finboy.core.languages import Language
from finboy.services.speech.media import InvalidAudio


@dataclass
class AudioUpload:
    audio: bytes = field(repr=False)
    content_type: str
    language_hint: Language | None


async def read_upload(request: Request, maximum: int) -> AudioUpload:
    kind, options = parse_options_header(request.headers.get("content-type", ""))
    boundary = options.get(b"boundary", b"")
    if kind != b"multipart/form-data" or not 1 <= len(boundary) <= 200:
        raise InvalidAudio(415)
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > maximum + 8192:
            raise InvalidAudio(413)
        body.extend(chunk)
    headers: dict[bytes, bytes] = {}
    header_name = bytearray()
    header_value = bytearray()
    part_data = bytearray()
    fields: dict[bytes, tuple[bytes, str]] = {}
    ended = False

    def start() -> None:
        headers.clear()
        header_name.clear()
        header_value.clear()
        part_data.clear()

    def header_field(data: bytes, start: int, end: int) -> None:
        if len(header_name) + end - start > 1024:
            raise InvalidAudio()
        header_name.extend(data[start:end])

    def header_value_part(data: bytes, start: int, end: int) -> None:
        if len(header_value) + end - start > 1024:
            raise InvalidAudio()
        header_value.extend(data[start:end])

    def header_end() -> None:
        if len(headers) > 4:
            raise InvalidAudio()
        headers[bytes(header_name).lower()] = bytes(header_value)
        header_name.clear()
        header_value.clear()

    def data_part(data: bytes, start: int, end: int) -> None:
        if len(part_data) + end - start > maximum:
            raise InvalidAudio(413)
        part_data.extend(data[start:end])

    def part_end() -> None:
        disposition, attrs = parse_options_header(headers.get(b"content-disposition", b""))
        name = attrs.get(b"name")
        if (
            disposition != b"form-data"
            or name not in {b"audio", b"language_hint"}
            or name in fields
        ):
            raise InvalidAudio()
        if name == b"language_hint" and len(part_data) > 2:
            raise InvalidAudio()
        try:
            mime = headers.get(b"content-type", b"application/octet-stream").decode("ascii")
        except UnicodeError:
            raise InvalidAudio() from None
        fields[name] = (bytes(part_data), mime)

    def finish() -> None:
        nonlocal ended
        ended = True

    try:
        parser = MultipartParser(
            boundary,
            {
                "on_part_begin": start,
                "on_header_field": header_field,
                "on_header_value": header_value_part,
                "on_header_end": header_end,
                "on_part_data": data_part,
                "on_part_end": part_end,
                "on_end": finish,
            },
        )
        parser.write(bytes(body))
        parser.finalize()
    except InvalidAudio:
        raise
    except MultipartParseError, UnicodeError, ValueError:
        raise InvalidAudio() from None
    if not ended or b"audio" not in fields:
        raise InvalidAudio()
    raw_hint = fields.get(b"language_hint", (b"", ""))[0]
    if raw_hint not in {b"", b"en", b"hi", b"ml"}:
        raise InvalidAudio()
    hint: Language | None = {b"en": "en", b"hi": "hi", b"ml": "ml"}.get(raw_hint)
    return AudioUpload(
        audio=fields[b"audio"][0], content_type=fields[b"audio"][1], language_hint=hint
    )
