"""Read-only JSON-backed store for policy decision requests."""
import copy
import json


class RequestStore:
    def __init__(self, path):
        with open(path, "r", encoding="utf-8") as f:
            self._records = json.load(f)

    def all(self) -> list:
        return copy.deepcopy(self._records)

    def get(self, request_id):
        for record in self._records:
            if record.get("request_id") == request_id:
                return copy.deepcopy(record)
        return None
