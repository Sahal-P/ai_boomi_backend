"""Embeddings: off without a model, normalised, batched, and failures logged without content."""

from types import SimpleNamespace

import pytest
from finboy.services.advisor import embeddings

from .support import embedding_settings, make_settings


class FakeClient:
    """Stands in for the OpenAI client's embeddings endpoint."""

    def __init__(self, size: int = 64, fail: bool = False) -> None:
        self.size, self.fail = size, fail
        self.batches: list[list[str]] = []
        self.embeddings = SimpleNamespace(create=self.create)

    def create(self, *, model: str, input: list[str], dimensions: int, timeout: float):
        if self.fail:
            raise RuntimeError("provider said something sensitive")
        self.batches.append(list(input))
        rows = [
            SimpleNamespace(index=index, embedding=[3.0, 4.0] + [0.0] * (self.size - 2))
            for index in range(len(input))
        ]
        return SimpleNamespace(data=list(reversed(rows)))


def test_embeddings_are_off_without_a_model() -> None:
    assert not embeddings.available(make_settings())
    assert embeddings.embed(["text"], make_settings()) is None
    assert embeddings.available(embedding_settings())


def test_vectors_come_back_in_order_normalised_and_batched(monkeypatch) -> None:
    fake = FakeClient()
    monkeypatch.setattr(embeddings, "_client", lambda *_: fake)
    found = embeddings.embed([f"text {number}" for number in range(70)], embedding_settings())
    assert found is not None and len(found) == 70
    assert [len(batch) for batch in fake.batches] == [64, 6]
    assert found[0][:2] == pytest.approx([0.6, 0.8])
    assert embeddings.similarity(found[0], found[1]) == pytest.approx(1.0)
    assert embeddings.similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


def test_a_failed_or_wrong_sized_call_is_logged_without_content(monkeypatch, caplog) -> None:
    monkeypatch.setattr(embeddings, "_client", lambda *_: FakeClient(fail=True))
    assert embeddings.embed(["Ramesh owes me ₹5,000"], embedding_settings()) is None
    monkeypatch.setattr(embeddings, "_client", lambda *_: FakeClient(size=32))
    assert embeddings.embed(["Ramesh owes me ₹5,000"], embedding_settings()) is None
    assert "advisor.embedding" in caplog.text
    assert "Ramesh" not in caplog.text and "sensitive" not in caplog.text
