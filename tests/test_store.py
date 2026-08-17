"""Tests for backend/store.py — read-only request loading."""
import hashlib

from tests.conftest import REQUESTS_PATH


def file_digest():
    return hashlib.sha256(REQUESTS_PATH.read_bytes()).hexdigest()


class TestRequestStore:
    def test_loads_all_20_requests(self, store):
        assert len(store.all()) == 20

    def test_get_returns_full_record(self, store):
        r = store.get("REQ-001")
        assert r is not None
        assert r["requester_type"] == "employee"
        assert "annual leave" in r["request_text"].lower()
        assert isinstance(r["metadata"], dict)

    def test_get_unknown_id_returns_none(self, store):
        assert store.get("REQ-999") is None

    def test_all_ids_unique_and_well_formed(self, store):
        ids = [r["request_id"] for r in store.all()]
        assert len(set(ids)) == 20
        assert all(i.startswith("REQ-") for i in ids)

    def test_source_file_not_modified(self, store):
        before = file_digest()
        store.all()
        store.get("REQ-005")
        assert file_digest() == before

    def test_mutating_returned_record_does_not_corrupt_store(self, store):
        r = store.get("REQ-001")
        r["request_text"] = "TAMPERED"
        assert store.get("REQ-001")["request_text"] != "TAMPERED"
