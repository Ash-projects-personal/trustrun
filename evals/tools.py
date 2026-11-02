"""Real tools the eval agents can call.

calculator: safe arithmetic over a parsed AST. No eval on raw input.
search_docs: real TF-IDF retrieval over the eval corpus. Pure Python
    token math on top of numpy, deterministic, no randomness.

Both tools return dicts with a "content" string, which is the shape the
stress module's poisoned tool wrapper expects.
"""

import ast
import json
import math
import os
import re

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus.jsonl")

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text):
    return _TOKEN.findall(text.lower())


# ---------------------------------------------------------------- calculator

_ALLOWED = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.FloorDiv,
)


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("only numbers allowed")
    if isinstance(node, ast.BinOp):
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.Pow):
            return left**right
        raise ValueError("operator not allowed")
    if isinstance(node, ast.UnaryOp):
        value = _safe_eval(node.operand)
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.UAdd):
            return value
        raise ValueError("operator not allowed")
    raise ValueError("expression not allowed")


def calculator(expression):
    """Evaluate an arithmetic expression. Returns {"content": str}."""
    try:
        tree = ast.parse(str(expression), mode="eval")
    except SyntaxError as exc:
        return {"content": "error: could not parse expression: %s" % exc}
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            return {"content": "error: expression not allowed"}
    try:
        value = _safe_eval(tree)
    except Exception as exc:
        return {"content": "error: %s" % exc}
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return {"content": str(value)}


# ------------------------------------------------------------------ tfidf search

class TfIdfIndex:
    """Deterministic TF-IDF over the corpus file. Built once, reused."""

    def __init__(self, path=CORPUS):
        self.doc_ids = []
        self.texts = []
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                doc = json.loads(line)
                self.doc_ids.append(doc["doc_id"])
                self.texts.append(doc["text"])
        vocab = {}
        doc_tokens = []
        for text in self.texts:
            toks = _tokens(text)
            doc_tokens.append(toks)
            for tok in set(toks):
                vocab[tok] = vocab.get(tok, 0) + 1
        self.vocab = {tok: i for i, tok in enumerate(sorted(vocab))}
        n_docs = len(self.texts)
        idf = np.zeros(len(self.vocab))
        for tok, df in vocab.items():
            idf[self.vocab[tok]] = math.log((1 + n_docs) / (1 + df)) + 1.0
        self.idf = idf
        mat = np.zeros((n_docs, len(self.vocab)))
        for d, toks in enumerate(doc_tokens):
            counts = {}
            for tok in toks:
                counts[tok] = counts.get(tok, 0) + 1
            for tok, count in counts.items():
                mat[d, self.vocab[tok]] = count * idf[self.vocab[tok]]
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.matrix = mat / norms

    def search(self, query, top=1):
        vec = np.zeros(len(self.vocab))
        counts = {}
        for tok in _tokens(query):
            counts[tok] = counts.get(tok, 0) + 1
        for tok, count in counts.items():
            if tok in self.vocab:
                vec[self.vocab[tok]] = count * self.idf[self.vocab[tok]]
        norm = np.linalg.norm(vec)
        if norm == 0:
            return []
        vec = vec / norm
        scores = self.matrix @ vec
        order = np.argsort(-scores, kind="stable")
        hits = []
        for idx in order[:top]:
            if scores[idx] <= 0:
                continue
            hits.append(
                {
                    "doc_id": self.doc_ids[idx],
                    "score": float(scores[idx]),
                    "text": self.texts[idx],
                }
            )
        return hits


_INDEX = None


def get_index():
    global _INDEX
    if _INDEX is None:
        _INDEX = TfIdfIndex()
    return _INDEX


def search_docs(query):
    """Search the corpus. Returns {"content": doc text, "doc_id": id}."""
    hits = get_index().search(str(query), top=1)
    if not hits:
        return {"content": "no matching document found", "doc_id": None}
    return {"content": hits[0]["text"], "doc_id": hits[0]["doc_id"]}
