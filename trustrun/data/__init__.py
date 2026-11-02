"""Data module: was the agent trained on clean data.

Audits an agent's training and fine tuning data for collapse, poisoning,
and synthetic rot. Point it at the records and it measures three
signals: exact duplicates, near duplicates, and template clusters.

Method source: CollapseWatch and the Lexsi collapse gate, which measured
the same signals on dolly-15k (15,011 real rows). The near duplicate
method is the same one the gate used: word 5 gram Jaccard at 0.8 or
higher, found through a 5 gram index so only pairs that share a 5 gram
are compared. The template clustering here is simpler than the gate's
first four word key: it masks pure numbers and capitalized words across
the whole normalized text, then counts the distinct keys. Masking is
crude on purpose. "Write a summary of Apple" and "Write a summary of
Google" land in the same cluster, which is the point: they are the same
template with a different slot.

audit_dataset takes a list of dicts. Each dict needs a "text" field
holding the training text as a string. It returns a dict with the three
measurements, a per metric verdict of "pass", "review", or "unverified"
with evidence attached, and the overall verdict.

Thresholds, kept simple and stated plainly:

- Fewer than 10 records: every metric is "unverified". Small samples
  cannot support a rate, so the module says so instead of guessing.
- Exact duplicates: "pass" under 0.1 percent, "review" at or above.
  Any systematic duplication is worth a look. dolly-15k measured 0.1
  percent and the Lexsi gate dropped those rows.
- Near duplicates: "pass" under 1 percent, "review" at or above.
  dolly-15k measured 0.4 percent on responses.
- Template clusters: "pass" when no template repeats at all, or when
  the largest repeated template holds under 5 percent of records.
  "review" when a repeated template holds 5 percent or more.
  dolly-15k measured 1.8 percent for its largest cluster under the
  gate's first four word key.

Overall verdict: "review" if any metric is "review", "unverified" if
any metric is "unverified" and none is "review", otherwise "pass".

Limits, documented so nobody mistakes this for a proof:

- Near duplicate detection only sees pairs that share a word 5 gram.
  That is complete for Jaccard at 0.8 or higher, since such pairs must
  share a 5 gram, but texts shorter than five words have no 5 grams
  and are never flagged.
- Masking merges distinct real sentences that share a shape. A high
  cluster count is not automatically bad and a low one is not
  automatically clean. It is a screening signal, not a diagnosis.
- This module does not detect poisoning by a capable adversary. It
  catches sloppy data: copies, near copies, and template floods.
"""

import re
from collections import defaultdict

_WORD = re.compile(r"[a-z0-9]+")

_NGRAM_N = 5
_NEAR_DUP_THRESHOLD = 0.8
_MIN_RECORDS = 10
_EXACT_DUP_REVIEW_AT = 0.001
_NEAR_DUP_REVIEW_AT = 0.01
_TOP1_TEMPLATE_REVIEW_AT = 0.05


def _normalize(text):
    """Lowercase, collapse whitespace, strip surrounding space."""
    return " ".join(str(text).lower().split())


def _tokens(normalized):
    """Word tokens of normalized text."""
    return _WORD.findall(normalized)


def _ngrams(normalized, n=_NGRAM_N):
    """Set of word n gram tuples. Empty when the text is too short."""
    toks = _tokens(normalized)
    if len(toks) < n:
        return set()
    return {tuple(toks[i : i + n]) for i in range(len(toks) - n + 1)}


def _jaccard(set_a, set_b):
    """Jaccard similarity of two sets. 0.0 when either set is empty."""
    if not set_a or not set_b:
        return 0.0
    shared = len(set_a & set_b)
    if shared == 0:
        return 0.0
    return shared / len(set_a | set_b)


def _mask_template(text):
    """Mask the slots in a raw text, then normalize.

    Capitalized words become CAP and pure number tokens become NUM, so
    the same template with different slot values lands on one key.
    Masking runs before lowercasing so capitalization is still visible.
    """
    parts = []
    for tok in str(text).split():
        if tok and tok[0].isupper():
            parts.append("CAP")
        elif tok.isdigit():
            parts.append("NUM")
        else:
            parts.append(tok)
    return _normalize(" ".join(parts))


def _exact_dup_rows(normalized_texts):
    """Indexes of records whose normalized text already appeared."""
    seen = set()
    dup = []
    for i, text in enumerate(normalized_texts):
        if text in seen:
            dup.append(i)
        else:
            seen.add(text)
    return dup


def _near_dup_rows(normalized_texts):
    """Indexes of records with at least one near duplicate partner.

    Builds a 5 gram to row index map, then computes Jaccard only for
    pairs that share at least one 5 gram. Any pair with Jaccard at or
    above the threshold shares a 5 gram, so this finds every such pair.
    """
    shingle_sets = [_ngrams(t) for t in normalized_texts]
    index = defaultdict(set)
    for i, grams in enumerate(shingle_sets):
        for gram in grams:
            index[gram].add(i)
    flagged = set()
    for i, grams in enumerate(shingle_sets):
        if not grams:
            continue
        partners = set()
        for gram in grams:
            partners |= index[gram]
        partners.discard(i)
        for j in sorted(partners):
            if j < i:
                continue
            if _jaccard(grams, shingle_sets[j]) >= _NEAR_DUP_THRESHOLD:
                flagged.add(i)
                flagged.add(j)
    return sorted(flagged)


def _template_clusters(texts):
    """Group record indexes by masked template key, largest first."""
    clusters = defaultdict(list)
    for i, text in enumerate(texts):
        clusters[_mask_template(text)].append(i)
    return sorted(clusters.items(), key=lambda kv: -len(kv[1]))


def _metric_result(name, verdict, evidence, **values):
    result = {"metric": name, "verdict": verdict, "evidence": evidence}
    result.update(values)
    return result


def audit_dataset(records):
    """Audit training records for exact dups, near dups, template clusters.

    records: a list of dicts, each with a "text" string field.

    Returns a dict with the measurements, a per metric verdict of
    "pass", "review", or "unverified" with evidence, and the overall
    verdict. Anything that cannot be computed honestly is "unverified",
    never a pass.
    """
    if not isinstance(records, list):
        raise TypeError("records must be a list of dicts")
    texts = []
    for i, record in enumerate(records):
        if not isinstance(record, dict):
            raise TypeError("record %d must be a dict" % i)
        text = record.get("text")
        if not isinstance(text, str):
            raise TypeError('record %d needs a "text" string field' % i)
        texts.append(text)
    n = len(texts)
    if n < _MIN_RECORDS:
        reason = "only %d records, need at least %d to measure a rate" % (
            n,
            _MIN_RECORDS,
        )
        metrics = {
            "exact_duplicates": _metric_result(
                "exact_duplicates", "unverified", reason
            ),
            "near_duplicates": _metric_result(
                "near_duplicates", "unverified", reason
            ),
            "template_clusters": _metric_result(
                "template_clusters", "unverified", reason
            ),
        }
        return {
            "records": n,
            "metrics": metrics,
            "verdict": "unverified",
        }
    normalized = [_normalize(t) for t in texts]
    dup_rows = _exact_dup_rows(normalized)
    exact_rate = len(dup_rows) / n
    if exact_rate < _EXACT_DUP_REVIEW_AT:
        exact_verdict = "pass"
        exact_evidence = "%d exact duplicate rows (%.2f%%), under the 0.1%% review line" % (
            len(dup_rows),
            exact_rate * 100,
        )
    else:
        exact_verdict = "review"
        exact_evidence = "%d exact duplicate rows (%.2f%%), at or above the 0.1%% review line" % (
            len(dup_rows),
            exact_rate * 100,
        )
    near_rows = _near_dup_rows(normalized)
    near_rate = len(near_rows) / n
    if near_rate < _NEAR_DUP_REVIEW_AT:
        near_verdict = "pass"
        near_evidence = "%d near duplicate rows (%.2f%%), under the 1%% review line" % (
            len(near_rows),
            near_rate * 100,
        )
    else:
        near_verdict = "review"
        near_evidence = "%d near duplicate rows (%.2f%%), at or above the 1%% review line" % (
            len(near_rows),
            near_rate * 100,
        )
    clusters = _template_clusters(texts)
    top_sizes = [len(idxs) for _, idxs in clusters[:5]]
    top1_share = top_sizes[0] / n if top_sizes else 0.0
    # A cluster of one is not a template flood, just a unique record.
    # Without this guard no input under 21 records could ever pass,
    # since one record alone is 5 percent or more of a small set.
    if top_sizes and top_sizes[0] >= 2 and top1_share >= _TOP1_TEMPLATE_REVIEW_AT:
        template_verdict = "review"
        template_evidence = (
            "%d template clusters, largest repeated template holds %d "
            "records (%.2f%%), at or above the 5%% review line"
            % (len(clusters), top_sizes[0], top1_share * 100)
        )
    else:
        template_verdict = "pass"
        template_evidence = (
            "%d template clusters, no repeated template holds 5%% or more "
            "of records" % len(clusters)
        )
    verdicts = [exact_verdict, near_verdict, template_verdict]
    if "review" in verdicts:
        verdict = "review"
    elif "unverified" in verdicts:
        verdict = "unverified"
    else:
        verdict = "pass"
    return {
        "records": n,
        "exact_duplicate_rows": len(dup_rows),
        "exact_duplicate_rate": exact_rate,
        "near_duplicate_rows": len(near_rows),
        "near_duplicate_rate": near_rate,
        "template_cluster_count": len(clusters),
        "top_template_cluster_sizes": top_sizes,
        "top1_template_share": top1_share,
        "metrics": {
            "exact_duplicates": _metric_result(
                "exact_duplicates",
                exact_verdict,
                exact_evidence,
                rows=len(dup_rows),
                rate=exact_rate,
            ),
            "near_duplicates": _metric_result(
                "near_duplicates",
                near_verdict,
                near_evidence,
                rows=len(near_rows),
                rate=near_rate,
            ),
            "template_clusters": _metric_result(
                "template_clusters",
                template_verdict,
                template_evidence,
                clusters=len(clusters),
                top_sizes=top_sizes,
            ),
        },
        "verdict": verdict,
    }
