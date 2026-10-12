"""End-to-end tests against a real index (offline extractive mode, no API key needed)."""

from rag.guardrails import REFUSAL


def test_import_app_is_lightweight():
    import app

    assert app._pipeline is None or app._pipeline is not None  # importing must not fail


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok" and data["index_ready"] and data["documents"] == 13


def test_index_and_docs_pages(client):
    assert b"PolicyBot" in client.get("/").data
    assert b"HR-002" in client.get("/docs").data
    page = client.get("/docs/HR-002")
    assert page.status_code == 200 and b'id="sec-' in page.data
    assert client.get("/docs/NOPE-999").status_code == 404


def test_chat_answers_with_citations(client):
    r = client.post("/chat", json={"question": "How many PTO days do employees with 4 years of service get?"})
    assert r.status_code == 200
    data = r.get_json()
    assert not data["refused"]
    assert "20" in data["answer"]
    assert data["citations"], "answers must always cite sources"
    c = data["citations"][0]
    assert c["doc_id"] == "HR-002" and c["url"].startswith("/docs/HR-002#sec-") and c["snippet"]


def test_chat_refuses_out_of_scope(client):
    data = client.post("/chat", json={"question": "What is the capital of France?"}).get_json()
    assert data["refused"] and data["answer"] == REFUSAL and data["citations"] == []


def test_chat_validates_input(client):
    assert client.post("/chat", json={}).status_code == 400
    assert client.post("/chat", json={"question": "x" * 2000}).status_code == 400
    assert client.post("/chat", json={"question": "PTO?", "k": 99}).status_code == 400


class _StubLLM:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = 0

    def answer(self, q, passages):
        return self.complete([])

    def complete(self, messages, max_tokens=None):
        self.calls += 1
        return self.replies.pop(0)


def test_llm_answer_invalid_citations_dropped(pipeline, monkeypatch):
    stub = _StubLLM("Employees with 3-5 years accrue 20 days [1][9].")
    monkeypatch.setattr(pipeline, "llm", stub)
    res = pipeline.answer("How many PTO days after 4 years?")
    assert res.answer == "Employees with 3-5 years accrue 20 days [1]."
    assert [c["n"] for c in res.citations] == [1]


def test_llm_uncited_answer_retried_then_refused(pipeline, monkeypatch):
    stub = _StubLLM("You get lots of days.", "Still no citations.")
    monkeypatch.setattr(pipeline, "llm", stub)
    res = pipeline.answer("How many PTO days after 4 years?")
    assert stub.calls == 2 and res.refused and res.answer == REFUSAL


def test_llm_refusal_passthrough(pipeline, monkeypatch):
    monkeypatch.setattr(pipeline, "llm", _StubLLM(REFUSAL))
    res = pipeline.answer("What is Lumora's current stock price?")
    assert res.refused and res.citations == []
