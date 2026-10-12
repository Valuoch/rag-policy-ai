"""Central configuration, read from environment variables (optionally a .env file).

Every tunable used by ingestion, retrieval, generation and evaluation lives here so a
run is fully described by its environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # optional: .env support for local development
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parent.parent

# Fixed seed for anything stochastic (evaluation sampling, tie-breaking). Chunking is
# fully deterministic and does not depend on it.
SEED = int(os.getenv("SEED", "42"))


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _path(name: str, default: Path) -> Path:
    val = os.getenv(name)
    if not val:
        return default
    p = Path(val)
    return p if p.is_absolute() else ROOT / p


def _llm_defaults() -> tuple[str, str, str]:
    """Resolve (api_key, base_url, model). Generic LLM_* vars win over provider shortcuts."""
    if os.getenv("LLM_API_KEY"):
        return (
            os.environ["LLM_API_KEY"],
            os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
            os.getenv("LLM_MODEL", "openai/gpt-oss-120b"),
        )
    if os.getenv("GROQ_API_KEY"):
        return (
            os.environ["GROQ_API_KEY"],
            os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
            os.getenv("LLM_MODEL", "openai/gpt-oss-120b"),
        )
    if os.getenv("OPENROUTER_API_KEY"):
        return (
            os.environ["OPENROUTER_API_KEY"],
            os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
            os.getenv("LLM_MODEL", "openai/gpt-oss-120b:free"),
        )
    return ("", os.getenv("LLM_BASE_URL", ""), os.getenv("LLM_MODEL", "extractive"))


@dataclass
class Settings:
    # --- corpus & index -------------------------------------------------------
    corpus_dir: Path = field(default_factory=lambda: _path("CORPUS_DIR", ROOT / "data" / "policies"))
    index_dir: Path = field(default_factory=lambda: _path("INDEX_DIR", ROOT / "index"))
    model_cache_dir: Path = field(default_factory=lambda: _path("MODEL_CACHE_DIR", ROOT / ".cache" / "fastembed"))
    collection: str = field(default_factory=lambda: os.getenv("COLLECTION", "policies"))

    # --- chunking (sizes are in words; ~1.3 tokens per word for English) -----
    chunk_size: int = field(default_factory=lambda: int(os.getenv("CHUNK_SIZE", "220")))
    chunk_overlap: int = field(default_factory=lambda: int(os.getenv("CHUNK_OVERLAP", "40")))
    min_chunk_words: int = field(default_factory=lambda: int(os.getenv("MIN_CHUNK_WORDS", "40")))

    # --- embeddings / retrieval ----------------------------------------------
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"))
    rerank: bool = field(default_factory=lambda: _bool("RERANK", True))
    rerank_model: str = field(default_factory=lambda: os.getenv("RERANK_MODEL", "Xenova/ms-marco-MiniLM-L-6-v2"))
    top_k: int = field(default_factory=lambda: int(os.getenv("TOP_K", "4")))
    fetch_k: int = field(default_factory=lambda: int(os.getenv("FETCH_K", "20")))
    # Out-of-corpus gate. Questions whose best passage scores below these are refused
    # before the LLM is called. Calibrated on the eval set (see design-and-evaluation.md).
    min_similarity: float = field(default_factory=lambda: float(os.getenv("MIN_SIMILARITY", "0.50")))
    min_rerank_score: float = field(default_factory=lambda: float(os.getenv("MIN_RERANK_SCORE", "-4.0")))

    # --- generation -----------------------------------------------------------
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    temperature: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0")))
    max_answer_tokens: int = field(default_factory=lambda: int(os.getenv("MAX_ANSWER_TOKENS", "350")))
    max_answer_chars: int = field(default_factory=lambda: int(os.getenv("MAX_ANSWER_CHARS", "1500")))
    max_question_chars: int = field(default_factory=lambda: int(os.getenv("MAX_QUESTION_CHARS", "500")))
    llm_timeout: float = field(default_factory=lambda: float(os.getenv("LLM_TIMEOUT", "30")))
    # Sent as `reasoning_effort` for reasoning models (gpt-oss: low|medium|high; qwen3: none|default).
    # Empty = parameter not sent (non-reasoning models reject it).
    llm_reasoning_effort: str = field(default_factory=lambda: os.getenv("LLM_REASONING_EFFORT", "low"))
    # Groundedness judge for the evaluation: a different model family than the generator.
    judge_model: str = field(default_factory=lambda: os.getenv("JUDGE_MODEL", "qwen/qwen3.8-27b"))
    judge_reasoning_effort: str = field(default_factory=lambda: os.getenv("JUDGE_REASONING_EFFORT", "none"))

    def __post_init__(self) -> None:
        key, base, model = _llm_defaults()
        self.llm_api_key = self.llm_api_key or key
        self.llm_base_url = self.llm_base_url or base
        self.llm_model = self.llm_model or model

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key) and os.getenv("LLM_MODE", "auto") != "extractive"


def get_settings(**overrides) -> Settings:
    s = Settings()
    for k, v in overrides.items():
        if not hasattr(s, k):
            raise AttributeError(f"Unknown setting {k!r}")
        setattr(s, k, v)
    return s


def use_system_trust_store() -> None:
    """Trust the OS certificate store (needed behind TLS-intercepting corporate proxies
    when downloading models). No-op if truststore isn't installed or USE_SYSTEM_CA=0."""
    if not _bool("USE_SYSTEM_CA", True):
        return
    try:
        import truststore

        truststore.inject_into_ssl()
    except Exception:  # pragma: no cover - best effort
        pass
