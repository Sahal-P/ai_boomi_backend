"""Streaming multipart parser with memory-only buffers (no UploadFile spool files)."""

from fastapi import Request
from python_multipart import MultipartParser
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import parse_options_header

from finboy.services.imports.files import MAX_BYTES, MAX_FILES, parse_eml
from finboy.services.ingestion.pipeline import InboundMessage
from finboy.services.mail.security import MailError


async def read_eml_uploads(request: Request) -> list[InboundMessage]:
    media_type, options = parse_options_header(request.headers.get("content-type", ""))
    boundary = options.get(b"boundary")
    if media_type != b"multipart/form-data" or not boundary or len(boundary) > 200:
        raise MailError("invalid_eml")
    messages: list[InboundMessage] = []
    data = bytearray()
    header_name, header_value = bytearray(), bytearray()
    headers: dict[bytes, bytes] = {}
    total = header_bytes = 0
    complete = False

    def part_begin() -> None:
        nonlocal header_bytes
        data.clear()
        headers.clear()
        header_bytes = 0
        if len(messages) >= MAX_FILES:
            raise MailError("upload_limit")

    def header_field(chunk: bytes, start: int, end: int) -> None:
        header_name.extend(chunk[start:end])
        if len(header_name) > 1024:
            raise MailError("invalid_eml")

    def header_content(chunk: bytes, start: int, end: int) -> None:
        header_value.extend(chunk[start:end])
        if len(header_value) > 4096:
            raise MailError("invalid_eml")

    def header_end() -> None:
        nonlocal header_bytes
        header_bytes += len(header_name) + len(header_value)
        if header_bytes > 8192 or len(headers) >= 16:
            raise MailError("invalid_eml")
        headers[bytes(header_name).lower()] = bytes(header_value)
        header_name.clear()
        header_value.clear()

    def headers_finished() -> None:
        disposition, params = parse_options_header(headers.get(b"content-disposition", b""))
        filename = params.get(b"filename", b"")
        content_type = headers.get(b"content-type", b"").split(b";", 1)[0].lower()
        if (
            disposition != b"form-data"
            or params.get(b"name") != b"files"
            or not filename.lower().endswith(b".eml")
            or content_type not in {b"message/rfc822", b"application/octet-stream"}
        ):
            raise MailError("invalid_eml")

    def part_data(chunk: bytes, start: int, end: int) -> None:
        if len(data) + end - start > MAX_BYTES:
            raise MailError("upload_limit")
        data.extend(chunk[start:end])

    def part_end() -> None:
        messages.append(parse_eml(bytes(data)))
        data.clear()

    def end() -> None:
        nonlocal complete
        complete = True

    parser = MultipartParser(
        boundary,
        {
            "on_part_begin": part_begin,
            "on_header_field": header_field,
            "on_header_value": header_content,
            "on_header_end": header_end,
            "on_headers_finished": headers_finished,
            "on_part_data": part_data,
            "on_part_end": part_end,
            "on_end": end,
        },
    )
    try:
        async for chunk in request.stream():
            total += len(chunk)
            if total > MAX_FILES * (MAX_BYTES + 16_384):
                raise MailError("upload_limit")
            parser.write(chunk)
        parser.finalize()
    except MultipartParseError, ValueError:
        raise MailError("invalid_eml") from None
    if not complete or not messages:
        raise MailError("invalid_eml")
    return messages
