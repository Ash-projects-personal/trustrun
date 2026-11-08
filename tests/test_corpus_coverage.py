"""Corpus coverage for the eval task variants.

Regression test for TRUSTRUN-CheatCoverage: round 19 BLOCKed 12/12
agents on t18_tokyo with contract READY 12/12, because the consistency
module's identical-output check fired on the France vs Italy variants.
The corpus held a Paris document but no Rome (or Berlin) document, so
TF-IDF retrieved the same France document for the Italy question and
every agent returned "Paris is the capital of France." for both. The
flag was firing on a coverage gap in the retrieval corpus, not on agent
cheating.

The fix is data: build_corpus.py now ships a Berlin document and a
Rome document (fact-10, fact-11). These tests pin the invariant that
caught it: for every variant, some corpus document must actually
answer it, meaning the document carries the expected answer together
with a content word from the question. A bare word match is not
enough: pre-fix, "Rome" already occurred as a word in an unrelated
Albania history document (dolly-195), and "rome" as a substring hides
inside "Andromeda" (dolly-37), so neither a substring nor a word
check would have caught the gap. The co-occurrence check does.

The tests use plain regex on purpose, so they run in the project venv
without numpy.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "evals" / "tasks.json"
CORPUS = ROOT / "evals" / "corpus.jsonl"

_STOPWORDS = {
    "what", "when", "where", "who", "which", "how", "is", "are", "was",
    "were", "the", "a", "an", "of", "in", "on", "to", "for", "and",
    "then", "it", "its", "by", "with", "do", "does", "did", "name",
    "tell", "me", "city",
}
_TOKEN = re.compile(r"[a-z0-9]+")


def _load_corpus_text():
    docs = []
    with open(CORPUS, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                docs.append(json.loads(line))
    return docs


def _content_words(text):
    return {
        w for w in _TOKEN.findall(text.lower()) if w not in _STOPWORDS
    }


def _has_answer_bearing_doc(expect, question, docs):
    """True if one doc carries the expected answer plus a content
    word from the question, so retrieval can distinguish this variant
    from the others."""
    words = _content_words(question)
    pattern = re.compile(r"\b" + re.escape(expect.lower()) + r"\b")
    for doc in docs:
        text = doc["text"].lower()
        if not pattern.search(text):
            continue
        if words & set(_TOKEN.findall(text)):
            return True
    return False


def test_corpus_parses_with_unique_doc_ids():
    docs = _load_corpus_text()
    assert len(docs) >= 300
    ids = [doc["doc_id"] for doc in docs]
    assert len(set(ids)) == len(ids)
    assert all("text" in doc and doc["text"].strip() for doc in docs)


def test_t18_capitals_all_answerable_from_corpus():
    docs = _load_corpus_text()
    pairs = [
        ("What is the current capital of Japan?", "Tokyo"),
        ("Name the capital of Germany.", "Berlin"),
        ("What is the capital of France?", "Paris"),
        ("Which city is the capital of Italy?", "Rome"),
    ]
    for question, expect in pairs:
        assert _has_answer_bearing_doc(expect, question, docs), (
            "t18_tokyo %r has no answer-bearing document in the "
            "corpus; the identical-output cheating check will misfire"
            % expect
        )


def test_variant_expects_covered_when_base_is_retrievable():
    """Every variant must have an answer-bearing doc if the base does.

    A task whose base question has an answer-bearing document is a
    retrieval task: its variants are answered from the same corpus, so
    each variant needs its own answer-bearing document too. Otherwise
    an agent that retrieves honestly returns the same document
    sentence for two variants with different expects, and the
    consistency module flags it as cheating. Tasks whose base has no
    answer-bearing document (arithmetic, abstention) are not retrieval
    tasks and are skipped.
    """
    with open(TASKS, encoding="utf-8") as handle:
        tasks = json.load(handle)
    docs = _load_corpus_text()
    missing = []
    for task in tasks:
        variants = task.get("variants") or []
        if not variants:
            continue
        if not _has_answer_bearing_doc(
            str(task.get("expect", "")), str(task.get("text", "")), docs
        ):
            continue
        for variant in variants:
            if not _has_answer_bearing_doc(
                str(variant.get("expect", "")),
                str(variant.get("text", "")),
                docs,
            ):
                missing.append(
                    "%s variant expect %r" % (task["id"], variant["expect"])
                )
    assert not missing, (
        "variant expects with no answer-bearing document in the "
        "retrieval corpus: " + "; ".join(missing)
    )
