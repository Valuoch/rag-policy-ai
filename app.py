"""Flask web app for the Lumora policy assistant.

Routes
  GET  /              chat UI
  POST /chat          {"question": "..."} -> answer + citations (+ snippets and source links)
  GET  /health        JSON status
  GET  /docs          list of indexed policy documents
  GET  /docs/<id>     a policy document rendered by section (citation links jump to #sec-N)

Importing this module is cheap: models and the index are loaded lazily on first use, so
`python -c "import app"` works in CI without downloading anything.
"""

from __future__ import annotations

import logging
import os
import threading
import time

from flask import Flask, abort, jsonify, render_template, request

from rag.config import get_settings

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024

settings = get_settings()
_pipeline = None
_lock = threading.Lock()
_started = time.time()


def get_pipeline():
    """Create the RAG pipeline once (thread-safe). Builds the index first if it is missing."""
    global _pipeline
    if _pipeline is None:
        with _lock:
            if _pipeline is None:
                from rag.ingest import build_index, read_manifest
                from rag.pipeline import RAGPipeline

                if read_manifest(settings.index_dir) is None:
                    log.info("No index found at %s - building it now", settings.index_dir)
                    build_index(settings)
                _pipeline = RAGPipeline(settings)
    return _pipeline


def _manifest() -> dict | None:
    from rag.ingest import read_manifest

    return read_manifest(settings.index_dir)


@app.get("/")
def index():
    m = _manifest() or {}
    return render_template("index.html", documents=m.get("documents", []))


@app.post("/chat")
def chat():
    from rag.guardrails import InvalidQuestion

    payload = request.get_json(silent=True) or {}
    question = payload.get("question", request.form.get("question"))
    k = payload.get("k")
    if k is not None and (not isinstance(k, int) or not 1 <= k <= 10):
        return jsonify(error="'k' must be an integer between 1 and 10"), 400
    try:
        result = get_pipeline().answer(question, k=k)
    except InvalidQuestion as e:
        return jsonify(error=str(e)), 400
    except Exception:  # upstream LLM/network errors should not leak stack traces
        log.exception("chat failed")
        return jsonify(error="The assistant is temporarily unavailable. Please try again."), 503
    return jsonify(result.to_dict())


@app.get("/health")
def health():
    m = _manifest()
    return jsonify(
        status="ok",
        index_ready=m is not None,
        documents=(m or {}).get("num_documents", 0),
        chunks=(m or {}).get("num_chunks", 0),
        embedding_model=settings.embedding_model,
        rerank=settings.rerank,
        llm_mode="llm" if settings.llm_enabled else "extractive",
        llm_model=settings.llm_model if settings.llm_enabled else None,
        pipeline_loaded=_pipeline is not None,
        uptime_s=round(time.time() - _started, 1),
    )


@app.get("/docs")
def docs_list():
    m = _manifest() or {}
    return render_template("docs.html", documents=m.get("documents", []))


@app.get("/docs/<doc_id>")
def doc_view(doc_id: str):
    from rag.loaders import load_corpus

    doc = next((d for d in load_corpus(settings.corpus_dir) if d.doc_id == doc_id), None)
    if doc is None:
        abort(404)
    return render_template("doc.html", doc=doc)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=False)
