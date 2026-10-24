"""Repeatable offline intent/media checks; explicit flags enable actual provider calls."""

import argparse
import json
import re
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.core.languages import Language
from finboy.services.assistant.intent import amounts_in_question, normalized, rule_intent
from finboy.services.speech.media import InvalidAudio, decode_audio
from finboy.services.speech.service import synthesize_speech, transcribe_routed

ROOT = Path(__file__).resolve().parents[4] / "fixtures" / "voice"


class Sample(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    language: Language
    text: str = Field(repr=False)
    path: str
    synthetic: bool
    live_generated: bool = False
    human_approved: bool = False
    provider: str | None = None
    model: str | None = None
    voice: str | None = None
    tts_latency_ms: int | None = None
    intent: str | None = None
    number_words: str | None = Field(default=None, repr=False)
    amount_minor: int | None = None


def tokens(value: str) -> list[str]:
    return re.sub(r"[^\w\s]", " ", normalized(value)).split()


def word_error_rate(expected: str, actual: str) -> float:
    reference, hypothesis = tokens(expected), tokens(actual)
    previous = list(range(len(hypothesis) + 1))
    for i, left in enumerate(reference, 1):
        current = [i]
        for j, right in enumerate(hypothesis, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (left != right)))
        previous = current
    return round(previous[-1] / max(1, len(reference)), 4)


def load_samples(root: Path, *, real: bool = False) -> list[Sample]:
    manifest = root / "manifest.json"
    if not manifest.exists():
        return []
    samples = [Sample.model_validate(item) for item in json.loads(manifest.read_text())["samples"]]
    if real and any(s.synthetic or not s.human_approved for s in samples):
        raise ValueError("Real samples require an explicit human-approved manifest")
    for sample in samples:
        path = (root / sample.path).resolve()
        if not path.is_relative_to(root.resolve()) or path.suffix != ".mp3":
            raise ValueError("Audio must remain inside its fixture directory")
    return samples


def generate_questions(settings: Settings) -> list[dict[str, object]]:
    """Generate only three bounded synthetic questions, never financial answer clips."""
    cases = json.loads((ROOT / "intent_cases.json").read_text())
    samples = load_samples(ROOT)
    results = []
    for language in ("en", "hi", "ml"):
        case = next(c for c in cases if c["id"] == f"{language}-01")
        start = time.monotonic()
        try:
            audio = synthesize_speech(text=case["text"], language=language, settings=settings)
            latency = round((time.monotonic() - start) * 1000)
            name = f"question-{language}.mp3"
            (ROOT / name).write_bytes(audio.data)
            sample = Sample(
                id=f"question-{language}",
                language=language,
                text=case["text"],
                path=name,
                synthetic=True,
                live_generated=True,
                provider="gemini" if language == "ml" else "resemble",
                model=settings.gemini_tts_model
                if language == "ml"
                else settings.resemble_tts_model,
                voice=settings.gemini_tts_voice
                if language == "ml"
                else "Fatima"
                if language == "hi"
                else "Lucy",
                tts_latency_ms=latency,
                intent=case["intent"],
            )
            samples = [s for s in samples if s.id != sample.id] + [sample]
            results.append({"language": language, "status": "passed", "latency_ms": latency})
        except ProviderUnavailable, InvalidAudio:
            results.append({"language": language, "status": "provider_unavailable"})
    (ROOT / "manifest.json").write_text(
        json.dumps(
            {"schema_version": 1, "samples": [s.model_dump(exclude_none=True) for s in samples]},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    return results


def run(*, settings: Settings, live: bool, real: bool, hint: bool = True) -> dict[str, object]:
    cases = json.loads((ROOT / "intent_cases.json").read_text())
    failures = [
        case["id"]
        for case in cases
        if (rule_intent(case["text"]).intent, rule_intent(case["text"]).category)
        != (case["intent"], case["category"])
    ]
    rows = []
    all_samples = [(ROOT, s) for s in load_samples(ROOT)]
    if real:
        all_samples.extend((ROOT / "real", s) for s in load_samples(ROOT / "real", real=True))
    for root, sample in all_samples:
        result: dict[str, object] = {
            "id": sample.id,
            "language": sample.language,
            "synthetic": sample.synthetic,
            "live_generated": sample.live_generated,
            "tts_recorded_latency_ms": sample.tts_latency_ms,
            "stt_status": "not_run",
            "spoken_number_human_intelligibility": "not_measured",
        }
        try:
            audio = (root / sample.path).read_bytes()
            decode_audio(
                audio=audio,
                content_type="audio/mpeg",
                settings=settings,
                max_bytes=settings.speech_max_audio_bytes,
                max_seconds=30,
            )
            result["media_status"] = "passed"
            if live:
                start = time.monotonic()
                transcript, provider = transcribe_routed(
                    audio=audio,
                    content_type="audio/mpeg",
                    settings=settings,
                    language_hint=sample.language if hint else None,
                )
                result.update(
                    stt_status="passed",
                    stt_provider=provider,
                    stt_latency_ms=round((time.monotonic() - start) * 1000),
                    language_correct=transcript.detected_language == sample.language,
                    exact_transcript=tokens(transcript.transcript) == tokens(sample.text),
                    word_error_rate=word_error_rate(sample.text, transcript.transcript),
                )
                if sample.intent:
                    result["intent_correct"] = (
                        rule_intent(transcript.transcript).intent == sample.intent
                    )
                if sample.amount_minor is not None:
                    result["spoken_number_machine_check"] = (
                        sample.amount_minor in amounts_in_question(transcript.transcript)
                        or (
                            sample.number_words is not None
                            and " ".join(tokens(sample.number_words))
                            in " ".join(tokens(transcript.transcript))
                        )
                    )
        except ProviderUnavailable, InvalidAudio, OSError:
            result["stt_status" if live else "media_status"] = "unavailable_or_invalid"
        rows.append(result)
    return {
        "mode": ("live_stt" if hint else "live_stt_no_hint")
        if live
        else "offline_intent_and_media",
        "intent_cases": len(cases),
        "intent_passed": len(cases) - len(failures),
        "intent_failed_ids": failures,
        "synthetic_audio_count": sum(s.synthetic for _, s in all_samples),
        "human_recording_count": sum(not s.synthetic for _, s in all_samples),
        "live_stt_calls": len(rows) if live else 0,
        "samples": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="Actually call the configured STT routing on fixtures"
    )
    parser.add_argument(
        "--no-hint",
        action="store_true",
        help="With --live, omit language hints to exercise detection and Malayalam routing",
    )
    parser.add_argument(
        "--generate", action="store_true", help="Actually synthesize three questions"
    )
    parser.add_argument(
        "--real", action="store_true", help="Include ignored, human-approved real samples"
    )
    args = parser.parse_args()
    settings = Settings()
    generation = generate_questions(settings) if args.generate else []
    report = run(settings=settings, live=args.live, real=args.real, hint=not args.no_hint)
    if generation:
        report["live_tts_generation"] = generation
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if (
        report["intent_failed_ids"]
        or any(
            row.get("media_status") != "passed"
            or row.get("stt_status") == "unavailable_or_invalid"
            or any(
                row.get(key) is False
                for key in ("language_correct", "intent_correct", "spoken_number_machine_check")
            )
            for row in report["samples"]
        )
        or any(row["status"] != "passed" for row in generation)
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
