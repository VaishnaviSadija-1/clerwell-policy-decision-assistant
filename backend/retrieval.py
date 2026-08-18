"""Policy section index and keyword-based retrieval engine.

Parses the five supplied markdown policy files into H2-level sections,
scores them against a request's text (+ optional metadata) with a small
TF-IDF-flavoured keyword scorer, and offers exact-substring passage
verification for grounding checks. Stdlib only, no LLM calls.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "of", "to",
    "in", "on", "for", "is", "are", "was", "were", "be", "been", "being",
    "it", "its", "this", "that", "these", "those", "with", "as", "by", "at",
    "from", "we", "our", "i", "my", "me", "you", "your", "he", "she", "they",
    "them", "their", "us", "please", "will", "would", "can", "could",
    "should", "have", "has", "had", "do", "does", "did", "not", "no", "so",
    "also", "into", "about", "up", "out", "over", "under", "again", "here",
    "there", "when", "where", "how", "all", "any", "both", "each", "more",
    "most", "other", "some", "such", "only", "own", "same", "than", "too",
    "very", "just", "am", "one", "two",
}

# Domain words that are worth extra weight when they appear in both the
# query and a candidate section -- these are the vocabulary that actually
# distinguishes which policy governs a given request.
_DOMAIN_BOOST = {
    "leave", "annual", "sick", "manager", "balance", "certificate",
    "refund", "invoice", "workflows", "chargeback", "duplicate",
    "discount", "pricing", "quote", "users", "billing", "sla",
    "indemnity", "residency", "expense", "reimburse", "reimbursement",
    "receipt", "travel", "international", "cost", "center",
    "credential", "credentials", "secret", "secrets", "api", "key", "keys",
    "password", "prompt", "injection", "export", "personal", "data",
    "privacy", "phishing", "malware", "administrator", "verified",
    "bank", "payout", "approval", "approve", "escalate", "security",
}


def _tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


def _bigrams(tokens: list[str]) -> set[str]:
    return {f"{a}_{b}" for a, b in zip(tokens, tokens[1:])}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class PolicySection:
    policy_file: str
    section: str
    text: str


_HEADING_RE = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)


def _parse_sections(policy_file: str, raw: str) -> list[PolicySection]:
    """Split raw markdown into sections on ``## `` headings.

    Content before the first H2 heading (title / version line) is skipped.
    Each section's text runs up to (but not including) the next ``## ``
    heading or end of file, so text never bleeds across sections.
    """
    headings = list(_HEADING_RE.finditer(raw))
    sections: list[PolicySection] = []
    for i, m in enumerate(headings):
        title = m.group(1).strip()
        body_start = m.end()
        body_end = headings[i + 1].start() if i + 1 < len(headings) else len(raw)
        body = raw[body_start:body_end]
        # Trim exactly one leading newline (the one that ends the heading
        # line) and any trailing whitespace/newlines, without touching
        # interior formatting.
        if body.startswith("\n"):
            body = body[1:]
        body = body.rstrip("\n")
        sections.append(PolicySection(policy_file=policy_file, section=title, text=body))
    return sections


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

class PolicyIndex:
    def __init__(self, policies_dir):
        self._dir = Path(policies_dir)
        self._raw_by_file: dict[str, str] = {}
        self.sections: list[PolicySection] = []

        for path in sorted(self._dir.glob("*.md")):
            raw = path.read_text(encoding="utf-8")
            self._raw_by_file[path.name] = raw
            self.sections.extend(_parse_sections(path.name, raw))

        # Precompute per-section token frequency + bigram sets, and
        # document-frequency stats across all sections for IDF weighting.
        self._section_tokens: list[list[str]] = []
        self._section_termfreq: list[dict[str, int]] = []
        self._section_bigrams: list[set[str]] = []
        df: dict[str, int] = {}

        for sec in self.sections:
            haystack = f"{sec.section}\n{sec.text}"
            toks = _tokenize(haystack)
            self._section_tokens.append(toks)
            tf: dict[str, int] = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            self._section_termfreq.append(tf)
            self._section_bigrams.append(_bigrams(toks))
            for t in set(toks):
                df[t] = df.get(t, 0) + 1

        self._df = df
        self._n_sections = len(self.sections) or 1

    # -- passage verification -------------------------------------------------

    def verify_passage(self, policy_file: str, passage: str) -> bool:
        raw = self._raw_by_file.get(policy_file)
        if raw is None:
            return False
        return passage in raw

    # -- search -----------------------------------------------------------

    def _idf(self, term: str) -> float:
        n_containing = self._df.get(term, 0)
        return math.log((self._n_sections + 1) / (n_containing + 1)) + 1.0

    def search(self, query: str, metadata: dict | None = None, top_k: int = 20):
        signal_parts = [query or ""]
        if metadata:
            for key, value in metadata.items():
                signal_parts.append(str(key).replace("_", " "))
                signal_parts.append(str(value))
        signal_text = " ".join(signal_parts)

        q_tokens = _tokenize(signal_text)
        if not q_tokens:
            return []

        q_tf: dict[str, int] = {}
        for t in q_tokens:
            q_tf[t] = q_tf.get(t, 0) + 1
        q_bigrams = _bigrams(q_tokens)

        scored: list[tuple[PolicySection, float]] = []
        for idx, sec in enumerate(self.sections):
            tf = self._section_termfreq[idx]
            if not tf:
                continue

            score = 0.0
            for term, qcount in q_tf.items():
                tcount = tf.get(term)
                if not tcount:
                    continue
                idf = self._idf(term)
                weight = idf * math.sqrt(qcount) * math.sqrt(tcount)
                if term in _DOMAIN_BOOST:
                    weight *= 1.8
                score += weight

            shared_bigrams = q_bigrams & self._section_bigrams[idx]
            score += 1.5 * len(shared_bigrams)

            # Normalize a little by section length so long sections don't
            # dominate purely on volume.
            length_norm = math.sqrt(len(self._section_tokens[idx]) + 1)
            score = score / length_norm * 3.0

            if score > 0:
                scored.append((sec, score))

        scored.sort(key=lambda pair: pair[1], reverse=True)

        threshold = 0.35
        qualifying = [(sec, s) for sec, s in scored if s > threshold]
        if not qualifying:
            return []

        # Once a policy FILE is established as relevant (>=1 of its sections
        # cleared the threshold on its own vocabulary), return every section
        # of that file, not just the ones that happen to share words with
        # this specific request. A quiet exception/exclusion clause (e.g. a
        # refund policy's "Exceptions" section) can score near zero on pure
        # keyword overlap yet be exactly the clause that governs the case —
        # a human reviewer would read the whole relevant policy, not a
        # keyword-curated fragment of it.
        relevant_files = {sec.policy_file for sec, _ in qualifying}
        results = [(sec, s) for sec, s in scored if sec.policy_file in relevant_files]
        results.sort(key=lambda pair: pair[1], reverse=True)
        return results[:top_k]
