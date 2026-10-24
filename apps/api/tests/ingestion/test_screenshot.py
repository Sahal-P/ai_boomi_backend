import base64
import json
import struct
import subprocess
import zlib
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from finboy.core.config import Settings
from finboy.services.ingestion import screenshot
from finboy.services.ingestion.classifier import trusted_domain
from finboy.services.ingestion.extract import prepare
from finboy.services.ingestion.screenshot import (
    CaptureUnavailable,
    InvalidImage,
    ScreenshotPayment,
    ScreenshotReading,
    as_message,
    payment_line,
    read_payment,
    sanitize,
    screenshot_time,
)
from finboy.services.ledger.confidence import confidence_for
from pydantic import SecretStr

# 10:42 IST on 24 October 2026, when the synthetic screenshot message arrives.
RECEIVED = datetime(2026, 10, 24, 5, 12, tzinfo=UTC)
GPAY = [
    "₹500",
    "Paid to Ravi Kumar",
    "ravi.kumar@okaxis",
    "Payment successful",
    "24 Oct 2026, 10:42 am",
    "UPI transaction ID",
    "612345678901",
]


def image(settings: Settings, codec: str, width: int = 720, height: int = 1600) -> bytes:
    return subprocess.run(
        [
            settings.ffmpeg_binary,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c=white:s={width}x{height}",
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-c:v",
            codec,
            "pipe:1",
        ],
        capture_output=True,
        check=True,
    ).stdout


def dimensions(settings: Settings, data: bytes) -> tuple[int, int]:
    probe = subprocess.run(
        [
            settings.ffprobe_binary,
            "-v",
            "error",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            "-i",
            "pipe:0",
        ],
        input=data,
        capture_output=True,
        check=True,
    )
    stream = json.loads(probe.stdout)["streams"][0]
    return stream["width"], stream["height"]


def with_text_chunk(png: bytes, secret: bytes) -> bytes:
    data = b"Comment\x00" + secret
    chunk = struct.pack(">I", len(data)) + b"tEXt" + data
    chunk += struct.pack(">I", zlib.crc32(b"tEXt" + data))
    return png[:33] + chunk + png[33:]  # after the signature and IHDR chunk


def reading(lines: list[str] = GPAY, **payment: object) -> ScreenshotReading:
    fields = {
        "status": "successful",
        "direction": "sent",
        "amount": "₹500",
        "counterparty": "Ravi Kumar",
        "reference": "612345678901",
        "when": "24 Oct 2026, 10:42 am",
    }
    return ScreenshotReading(lines=lines, payment=ScreenshotPayment(**(fields | payment)))


@pytest.fixture
def vision(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            "openai_api_key": SecretStr("synthetic-openai"),
            "openai_vision_model": "synthetic-vision-model",
        }
    )


def test_sanitize_reencodes_a_bounded_png_without_metadata(settings: Settings) -> None:
    png = sanitize(
        with_text_chunk(image(settings, "png"), b"NEVER-LEAK-metadata"), "image/png", settings
    )
    assert png.startswith(b"\x89PNG") and b"NEVER-LEAK" not in png
    assert dimensions(settings, png) == (720, 1600)
    large = sanitize(image(settings, "mjpeg", 3000, 5000), "image/jpeg; q=1", settings)
    assert large.startswith(b"\x89PNG") and dimensions(settings, large) == (1229, 2048)


def test_sanitize_rejects_mismatched_or_unsafe_images(settings: Settings) -> None:
    png = image(settings, "png")
    for data, mime in [
        (png, "image/jpeg"),
        (png, "image/gif"),
        (b"NEVER-LEAK not an image", "image/png"),
        (b"", "image/png"),
        (b"x" * (5 * 1024 * 1024 + 1), "image/png"),
        (image(settings, "png", 16, 16), "image/png"),
        (image(settings, "png", 5000, 5000), "image/png"),
    ]:
        with pytest.raises(InvalidImage) as error:
            sanitize(data, mime, settings)
        assert str(error.value) == "invalid_image"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("24 Oct 2026, 10:42 am", "24-10-26 10:42"),
        ("Oct 24, 2026 at 10:42 AM", "24-10-26 10:42"),
        ("22 Oct 2026 08:15 PM", "22-10-26 20:15"),
        ("23 Oct, 9:05 PM", "23-10-26 21:05"),
        ("24/10/2026 10:42:31 a.m.", "24-10-26 10:42"),
        ("2026-10-24 22:05", "24-10-26 22:05"),
        ("Yesterday, 6:30 pm", "23-10-26 18:30"),
        ("today", "24-10-26"),
        ("28 Oct 2026", None),
        ("29 Feb", None),
        ("someday soon", None),
        (None, None),
    ],
)
def test_screenshot_time_renders_rules_dates(value: str | None, expected: str | None) -> None:
    assert screenshot_time(value, RECEIVED) == expected


def test_screenshot_time_never_dates_a_payment_after_its_message() -> None:
    new_year = datetime(2026, 1, 2, 5, 0, tzinfo=UTC)
    assert screenshot_time("31 Dec, 11:59 PM", new_year) == "31-12-25 23:59"
    assert screenshot_time("5 Jan", new_year) == "05-01-25"


@pytest.mark.parametrize(
    "item,expected",
    [
        (
            reading(),
            "Rs. 500.00 paid to Ravi Kumar via UPI on 24-10-26 10:42, UPI Ref: 612345678901",
        ),
        (
            reading(
                ["Received from Asha Menon", "₹2,000", "Credited to your account"],
                direction="received",
                amount="₹2,000",
                counterparty="Asha Menon",
                reference=None,
                when=None,
            ),
            "Rs. 2000.00 credited from Asha Menon",
        ),
        (reading(amount="₹5,000"), None),
        (
            reading(counterparty="Salary Rs 90000"),
            "Rs. 500.00 paid via UPI on 24-10-26 10:42, UPI Ref: 612345678901",
        ),
        (
            reading(reference="not visible 999"),
            "Rs. 500.00 paid to Ravi Kumar via UPI on 24-10-26 10:42",
        ),
        (
            reading(when="28 Oct 2026, 10:42 am"),
            "Rs. 500.00 paid to Ravi Kumar via UPI, UPI Ref: 612345678901",
        ),
        (reading(["Payment pending", "₹500 to Ravi Kumar"]), None),
        (reading(["₹500", "Ravi Kumar requested money"]), None),
        (reading(status="pending"), None),
        (reading(direction="unclear"), None),
        (ScreenshotReading(lines=GPAY, payment=None), None),
    ],
)
def test_payment_line_uses_only_grounded_fields(
    item: ScreenshotReading, expected: str | None
) -> None:
    assert payment_line(item, RECEIVED) == expected


def test_screenshot_line_lands_in_review_with_a_hashed_reference(settings: Settings) -> None:
    line = payment_line(reading(), RECEIVED)
    assert line is not None
    prepared = prepare(as_message(line, RECEIVED), settings, mode="rules")
    assert prepared.message.sender_domain == "whatsapp.invalid"
    assert not trusted_domain(prepared.message.sender_domain)
    assert "612345678901" not in prepared.message.text
    (event,) = prepared.extraction.events
    assert (event.event_type, event.amount_minor, event.merchant) == ("debit", 50000, "Ravi Kumar")
    assert event.occurred_at == datetime.fromisoformat("2026-10-24T10:42:00+05:30")
    assert event.reference_id and event.reference_id.startswith("H-")
    assert confidence_for(event, trusted=False).status == "needs_review"


def test_a_complete_screenshot_still_cannot_confirm_itself(settings: Settings) -> None:
    item = reading(
        [
            "₹450",
            "Paid to Swiggy",
            "Payment successful",
            "24 Oct 2026, 10:42 am",
            "UPI Ref 612345678901",
        ],
        amount="₹450",
        counterparty="Swiggy",
    )
    line = payment_line(item, RECEIVED)
    assert line is not None
    (event,) = prepare(as_message(line, RECEIVED), settings, mode="rules").extraction.events
    confidence = confidence_for(event, trusted=False)
    # Amount, date, reference and a categorised merchant are every untrusted factor.
    assert confidence.status == "needs_review" and confidence.value <= 0.706


def test_read_payment_sends_only_the_sanitized_image(
    monkeypatch: pytest.MonkeyPatch, vision: Settings
) -> None:
    monkeypatch.setenv("FINBOY_EXTRACTION_MODE", "live")
    fake = MagicMock()
    create = fake.return_value.__enter__.return_value.responses.parse
    create.return_value.output_parsed = reading()
    monkeypatch.setattr(screenshot, "OpenAI", fake)
    source = with_text_chunk(image(vision, "png"), b"NEVER-LEAK-metadata")
    line = read_payment(source, "image/png", vision, RECEIVED)
    assert line == "Rs. 500.00 paid to Ravi Kumar via UPI on 24-10-26 10:42, UPI Ref: 612345678901"
    call = create.call_args.kwargs
    assert call["model"] == "synthetic-vision-model" and call["store"] is False
    assert call["text_format"] is ScreenshotReading
    (part,) = call["input"][1]["content"]
    assert part["type"] == "input_image" and part["image_url"].startswith("data:image/png;base64,")
    sent = base64.b64decode(part["image_url"].split(",", 1)[1])
    assert sent.startswith(b"\x89PNG") and b"NEVER-LEAK" not in sent
    assert "UNTRUSTED DATA" in call["input"][0]["content"]


def test_read_payment_failures_are_fixed_and_redacted(
    monkeypatch: pytest.MonkeyPatch, vision: Settings, settings: Settings, caplog
) -> None:
    monkeypatch.setenv("FINBOY_EXTRACTION_MODE", "live")
    png = image(vision, "png")
    fake = MagicMock()
    create = fake.return_value.__enter__.return_value.responses.parse
    monkeypatch.setattr(screenshot, "OpenAI", fake)
    create.side_effect = RuntimeError("NEVER-LEAK provider body synthetic-openai")
    with pytest.raises(CaptureUnavailable) as error:
        read_payment(png, "image/png", vision, RECEIVED)
    assert str(error.value) == "capture_unavailable"
    assert "NEVER-LEAK" not in caplog.text and "synthetic-openai" not in caplog.text
    create.side_effect = None
    create.return_value.output_parsed = None
    with pytest.raises(CaptureUnavailable):
        read_payment(png, "image/png", vision, RECEIVED)
    create.return_value.output_parsed = ScreenshotReading(lines=["A cat photo"], payment=None)
    assert read_payment(png, "image/png", vision, RECEIVED) is None
    calls = create.call_count
    with pytest.raises(CaptureUnavailable):
        read_payment(png, "image/png", settings, RECEIVED)
    monkeypatch.setenv("FINBOY_EXTRACTION_MODE", "offline")
    with pytest.raises(CaptureUnavailable):
        read_payment(png, "image/png", vision, RECEIVED)
    assert create.call_count == calls
