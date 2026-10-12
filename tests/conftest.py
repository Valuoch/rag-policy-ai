import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Tests never call a paid/remote LLM: force the offline extractive mode.
os.environ["LLM_MODE"] = "extractive"


@pytest.fixture(scope="session")
def built_settings(tmp_path_factory):
    """A real index over the real corpus, built once per test session in a temp dir."""
    from rag.config import get_settings
    from rag.ingest import build_index

    s = get_settings(index_dir=tmp_path_factory.mktemp("index"))
    build_index(s, verbose=False)
    return s


@pytest.fixture(scope="session")
def pipeline(built_settings):
    from rag.pipeline import RAGPipeline

    return RAGPipeline(built_settings)


@pytest.fixture()
def client(built_settings, pipeline, monkeypatch):
    import app as webapp

    monkeypatch.setattr(webapp, "settings", built_settings)
    monkeypatch.setattr(webapp, "_pipeline", pipeline)
    return webapp.app.test_client()
