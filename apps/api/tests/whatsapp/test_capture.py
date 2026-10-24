from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from finboy.core.config import Settings
from finboy.services.ingestion.screenshot import CaptureUnavailable, InvalidImage
from finboy.services.mail.security import MailError
from finboy.services.whatsapp import capture
from finboy.services.whatsapp.capture import Capture, capture_reply, capture_screenshot
from finboy.services.whatsapp.events import InboundQuestion
from finboy.services.whatsapp.meta import DownloadedMedia, InvalidMedia, MetaUnavailable

QUESTION = InboundQuestion(
    "wamid.image",
    "919000000001",
    datetime.now(UTC),
    "image",
    media_id="5678",
    mime_type="image/png",
)


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch):
    client = MagicMock()
    client.download_image.return_value = DownloadedMedia(b"synthetic image", "image/png")
    read = MagicMock(return_value="Rs. 500.00 paid to Ravi Kumar via UPI")
    monkeypatch.setattr(capture.screenshot, "read_payment", read)
    create_run = MagicMock(side_effect=MailError("import_busy"))
    run_import = MagicMock()
    monkeypatch.setattr(capture, "create_run", create_run)
    monkeypatch.setattr(capture, "run_import", run_import)
    return client, read, create_run, run_import


@pytest.mark.parametrize(
    "fault,outcome",
    [
        ("download_invalid", "invalid_image"),
        ("image_invalid", "invalid_image"),
        ("download_unavailable", "unavailable"),
        ("reader_unavailable", "unavailable"),
        ("not_payment", "no_payment"),
        ("busy", "busy"),
    ],
)
def test_capture_outcomes_before_the_ledger(
    harness, settings: Settings, fault: str, outcome: str
) -> None:
    client, read, create_run, run_import = harness
    if fault == "download_invalid":
        client.download_image.side_effect = InvalidMedia
    if fault == "download_unavailable":
        client.download_image.side_effect = MetaUnavailable
    if fault == "image_invalid":
        read.side_effect = InvalidImage()
    if fault == "reader_unavailable":
        read.side_effect = CaptureUnavailable()
    if fault == "not_payment":
        read.return_value = None
    result = capture_screenshot(MagicMock(), settings, client, QUESTION)
    assert result == Capture(outcome)
    client.download_image.assert_called_once_with("5678", "image/png")
    assert create_run.called == (fault == "busy")
    assert not run_import.called
    if fault not in {"download_invalid", "download_unavailable"}:
        assert read.call_args.args[3] == QUESTION.provider_at


@pytest.mark.parametrize("language", [None, "en", "hi", "ml"])
@pytest.mark.parametrize(
    "outcome", ["saved", "already_recorded", "no_payment", "busy", "invalid_image", "unavailable"]
)
def test_every_outcome_has_a_reply(language: str | None, outcome: str) -> None:
    reply = capture_reply(Capture(outcome, 125050, "Hotel Arya"), language)
    assert reply and "http" not in reply
    if outcome in {"saved", "already_recorded"}:
        assert "₹1,250.50" in reply and "Hotel Arya" in reply
    if language == "hi":
        assert any("ऀ" <= character <= "ॿ" for character in reply)
    if language == "ml":
        assert any("ഀ" <= character <= "ൿ" for character in reply)


@pytest.mark.parametrize("merchant", [None, "Unknown", "Unknown VPA [address]", "[address]"])
def test_reply_omits_masked_or_unknown_payees(merchant: str | None) -> None:
    reply = capture_reply(Capture("saved", 50000, merchant), "en")
    assert reply.startswith("Saved for review: ₹500.") and "address" not in reply.lower()
    assert "Unknown" not in reply


@pytest.mark.parametrize("outcome", ["saved", "already_recorded"])
@pytest.mark.parametrize("language", ["en", "hi", "ml"])
def test_received_payment_reply_does_not_invent_an_outgoing_direction(outcome, language) -> None:
    reply = capture_reply(Capture(outcome, 50000, "Synthetic Sender"), language)
    assert "₹500 · Synthetic Sender" in reply
    assert "to Synthetic Sender" not in reply
    assert "Synthetic Sender को" not in reply and "Synthetic Sender-ന് നൽകിയ" not in reply
