# PolicyBot: a RAG assistant for company policies

PolicyBot answers employee questions about the policies and procedures of **Lumora Systems, Inc.**, a fictional company with a synthetic corpus of 13 policies (~33k words, ~67 pages, in Markdown, HTML, TXT and PDF). It retrieves the relevant policy passages and generates a short answer from them. Every answer cites its sources with document IDs, section names, snippets and links. It refuses questions that the policies don't cover.

- **Stack:** Flask · Chroma (local, persistent) · `BAAI/bge-small-en-v1.5` embeddings plus an `ms-marco-MiniLM-L-6-v2` cross-encoder re-ranker. Both models are free and run locally on ONNX via fastembed. Any OpenAI-compatible chat LLM can generate the answers (default: Groq free tier, `openai/gpt-oss-120b`).
- **Endpoints:**
  - `GET /`: chat UI.
  - `POST /chat`: answer with citations and snippets.
  - `GET /health`: JSON status.
  - `GET /docs/<id>`: the source document, with each section anchored.
- **Docs:** [design-and-evaluation.md](design-and-evaluation.md) · [ai-tooling.md](ai-tooling.md) · [deployed.md](deployed.md)

## Quick start

Requirements: Python 3.12+ (developed on 3.14, CI uses 3.13). You don't need a GPU or torch.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt          # add -r requirements-dev.txt for tests/PDF tooling
cp .env.example .env                     # then set GROQ_API_KEY (free: https://console.groq.com/keys)

python -m rag.ingest                     # parse -> chunk -> embed -> store in ./index (~30 s; downloads ~150 MB of models once)
python app.py                            # http://localhost:8000
```

Without an API key, the app still runs in **extractive mode**. It answers with the most relevant cited sentences copied from the policies, so CI and demos work offline. With a key, it writes fluent answers grounded in the retrieved passages.

If you're behind a corporate TLS-intercepting proxy, the app trusts the OS certificate store through `truststore` when downloading models. Set `USE_SYSTEM_CA=0` to disable that.

### API

```bash
curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
     -d '{"question": "How many PTO days do I get after 4 years?"}'
```

```jsonc
{
  "answer": "Employees with 3-5 years of service accrue 20 days of PTO per year [1].",
  "refused": false,
  "citations": [{"n": 1, "doc_id": "HR-002", "title": "Paid Time Off & Leave Policy",
                 "section": "4. Paid Time Off (PTO) > 4.1 PTO accrual by tenure", "snippet": "...",
                 "url": "/docs/HR-002#sec-4", "score": 8.28}],
  "retrieved": [...], "mode": "llm", "model": "openai/gpt-oss-120b", "latency_ms": 912.4
}
```

The request body accepts an optional `"k"` (1–10) to override top-k. `GET /health` returns the index status, document and chunk counts, the models in use and the LLM mode.

## Evaluation

```bash
python -m eval.run_eval                  # 30 questions -> eval/results/<mode>/summary.json + per_question.jsonl
python -m eval.run_eval --ablations      # + retrieval ablations (k, re-ranking, chunk size) -> eval/results/ablations.json
```

The evaluation reports groundedness, citation accuracy, exact and partial match, refusal accuracy and p50/p95 latency. The method and results are in [design-and-evaluation.md](design-and-evaluation.md).

## Tests and CI

```bash
pip install -r requirements-dev.txt
pytest -q                                # parsers, chunking, guardrails, pipeline (stubbed LLM), Flask endpoints
```

On every push and PR, `.github/workflows/ci.yml` does the following:
1. Installs the dependencies.
2. Runs `python -c "import app"`.
3. Prints the corpus stats.
4. Runs `pytest`.
5. Builds the index.
6. Boots gunicorn and smoke-tests `/health` and `/chat`.

On a push to `main`, a `deploy` job then triggers the Render deploy hook, if the `RENDER_DEPLOY_HOOK_URL` secret is set.

## Deployment (Render free tier)

1. Create a new **Blueprint** on Render from this repo. It uses `render.yaml`: the build step installs the dependencies and runs `python -m rag.ingest`, and the server runs on gunicorn.
2. Set `GROQ_API_KEY` in the Render dashboard.
3. Copy the service's **Deploy Hook** URL into the GitHub secret `RENDER_DEPLOY_HOOK_URL`. From then on, pushes to `main` deploy only after CI passes.

## Configuration

Settings are environment variables; the full list is in `.env.example`. The main ones are:

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` / `OPENROUTER_API_KEY` / `LLM_API_KEY` | – | Enables LLM generation (otherwise extractive mode) |
| `LLM_MODEL`, `LLM_BASE_URL`, `LLM_REASONING_EFFORT` | `openai/gpt-oss-120b`, Groq, `low` | Any OpenAI-compatible endpoint (set the effort empty for non-reasoning models) |
| `TOP_K`, `FETCH_K`, `RERANK` | 4, 20, true | Retrieval depth and cross-encoder re-ranking |
| `CHUNK_SIZE`, `CHUNK_OVERLAP` | 220, 40 (words) | Chunking |
| `MIN_RERANK_SCORE` | -4.0 | Retrieval gate: refuse below this |
| `MAX_ANSWER_TOKENS`, `MAX_ANSWER_CHARS` | 350, 1500 | Output length guardrails |
| `SEED` | 42 | Seed for evaluation sampling |

## Repository layout

```
app.py                  Flask app (/, /chat, /health, /docs)
rag/
  config.py             settings from env
  loaders.py            parse + clean MD / HTML / TXT / PDF into heading-delimited sections
  chunking.py           heading-aware chunking with overlapping word windows
  embeddings.py         fastembed embedder + cross-encoder re-ranker
  vectorstore.py        persistent Chroma collection
  ingest.py             build the index (python -m rag.ingest)
  retriever.py          top-k retrieval + re-ranking + retrieval-confidence gate
  llm.py                prompt, OpenAI-compatible client, extractive fallback
  guardrails.py         refusal, citation enforcement, length limits, input validation
  pipeline.py           end-to-end question -> cited answer
templates/, static/     chat UI and document viewer
data/policies/          the corpus (13 synthetic Lumora policies)
corpus_src/             fact sheet used to keep the corpus consistent + Markdown source of the PDF
eval/                   questions.jsonl (30), retrieval_hard.jsonl (16), run_eval.py, results/
tests/                  pytest suite
scripts/build_pdf.py    regenerates the PDF member of the corpus
```

The corpus is entirely synthetic and was written for this project, so it can be included in the repo. Lumora Systems, its staff and its contact details are fictional.
