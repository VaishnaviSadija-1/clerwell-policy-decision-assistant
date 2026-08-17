"""Entry point for the CLERWELL Policy Decision Assistant desktop app.

Builds a PyWebView window whose frontend (frontend/index.html) talks to Python
through the `Api` js_api bridge defined here. Importing this module must never
open a window or start the webview event loop — only `python app.py` does that.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

from backend.analyzer import Analyzer
from backend.llm import default_client
from backend.retrieval import PolicyIndex
from backend.store import RequestStore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REQUESTS_PATH = os.path.join(BASE_DIR, "data", "requests.json")
POLICIES_DIR = os.path.join(BASE_DIR, "policies")
FRONTEND_INDEX = os.path.join(BASE_DIR, "frontend", "index.html")


class Api:
    """The pywebview js_api bridge exposed to the frontend as window.pywebview.api."""

    def __init__(self, store: RequestStore, analyzer: Analyzer):
        self._store = store
        self._analyzer = analyzer

    def get_requests(self) -> list:
        """Return all request records as JSON-serializable dicts."""
        return self._store.all()

    def analyze(self, request_id) -> dict:
        """Run policy analysis for request_id. Never raises — any failure is
        returned as {"ok": False, "error": "<readable>"}."""
        try:
            return self._analyzer.analyze(request_id)
        except Exception as exc:  # noqa: BLE001 - must never crash the bridge
            return {"ok": False, "error": f"Unexpected error: {exc}"}


def create_api(llm_client=None) -> Api:
    """Build the RequestStore, PolicyIndex, Analyzer and wrap them in an Api.

    All paths are resolved relative to this file, not the current working
    directory, so the app works regardless of where it is launched from.
    """
    store = RequestStore(REQUESTS_PATH)
    index = PolicyIndex(POLICIES_DIR)
    analyzer = Analyzer(store, index, llm_client or default_client())
    return Api(store, analyzer)


if __name__ == "__main__":
    import webview

    load_dotenv()
    api = create_api()
    webview.create_window(
        "CLERWELL Policy Decision Assistant",
        FRONTEND_INDEX,
        js_api=api,
        width=1200,
        height=800,
        min_size=(960, 640),
    )
    webview.start()
