"""Contract-target calibration: measure how well Trustrun's contract
judge recovers maintainer-grade verdicts on a labeled corpus.

The target instrument is Cognition's FrontierCode 2.0 (2026-11): 132
private tasks, graded by whether the agent's changes merged into the
maintainer repository, OpenAI Opus 5.5 at 45.5% pass, Claude Sonnet 4.5
at 33.6%. FrontierCode is private, so Trustrun cannot calibrate
against it directly; this module calibrates the same judge machinery
on Trustrun's own labeled eval corpus instead, and records the gap.

A calibration pair is a dict with:
  "id": a label for the pair.
  "claim": a judge-kind claim dict (statement + kind "judge").
  "value": the recorded output value for the claim.
  "output": the full output dict the judge sees.
  "expected": the maintainer-grade verdict, "pass", "fail", or
    "unverified".

calibrate_judge runs each pair through judge_claim_trials with the
given panel and trials, then reports:
  agreement: share of pairs whose majority verdict equals expected.
  agreement_decided: the same share over pairs whose expected verdict
    is "pass" or "fail" only.
  mean_flip_rate: mean per-pair flip rate (1 - majority share).
  kappa: Fleiss' kappa across the pairs' vote lists (None with fewer
    than two pairs, or when the vote lists are unusable).
  pairs: the per-pair record (verdict, votes, flip rate, expected).

Nothing here invents a verdict: every expected value comes from the
caller's labeled corpus, and every vote comes from a real judge call.
"""

from trustrun.contract.judge import fleiss_kappa, judge_claim_trials

EXPECTED_VERDICTS = ("pass", "fail", "unverified")


def calibrate_judge(pairs, trials=11, judges=None, seed=0):
    """Calibrate the contract judge against labeled verdict pairs.

    pairs: a list of pair dicts (see module docstring).
    trials: repeated judging rounds per pair (default 11, the
      JudgeRedesign minimum).
    judges: an optional panel of judge callables overriding each
      pair's own claim judge.
    seed: fixes the position draws so a run is reproducible.

    Returns the calibration report dict. An empty pair list returns
    n 0 with agreement and kappa None.
    """
    if not isinstance(pairs, list):
        raise TypeError("pairs must be a list")
    if isinstance(trials, bool) or not isinstance(trials, int) or trials < 1:
        raise TypeError("trials must be a positive integer")
    for pair in pairs:
        if not isinstance(pair, dict):
            raise TypeError("each pair must be a dict")
        if pair.get("expected") not in EXPECTED_VERDICTS:
            raise ValueError(
                "pair %r needs expected in %r, got %r"
                % (pair.get("id", "?"), EXPECTED_VERDICTS, pair.get("expected"))
            )
        if not isinstance(pair.get("claim"), dict):
            raise TypeError("pair %r needs a claim dict" % pair.get("id", "?"))
    import random

    rng = random.Random(seed)
    records = []
    vote_lists = []
    for pair in pairs:
        record = judge_claim_trials(
            pair["claim"], pair.get("value"), pair.get("output", {}),
            trials=trials, judges=judges, rng=rng,
        )
        verdict = record["verdict"]
        expected = pair["expected"]
        records.append({
            "id": pair.get("id", "?"),
            "expected": expected,
            "verdict": verdict,
            "agree": verdict == expected,
            "trials": record["trials"],
            "n_votes": len(record["votes"]),
            "flip_rate": record["flip_rate"],
            "majority_share": record["majority_share"],
            "votes": record["votes"],
        })
        if record["votes"]:
            vote_lists.append(record["votes"])
    n = len(records)
    if n == 0:
        return {
            "n": 0,
            "agreement": None,
            "agreement_decided": None,
            "mean_flip_rate": None,
            "kappa": None,
            "pairs": [],
        }
    agreement = sum(1 for r in records if r["agree"]) / n
    decided = [r for r in records if r["expected"] in ("pass", "fail")]
    if decided:
        agreement_decided = sum(1 for r in decided if r["agree"]) / len(decided)
    else:
        agreement_decided = None
    mean_flip = sum(r["flip_rate"] for r in records) / n
    if len(vote_lists) >= 2:
        try:
            kappa = fleiss_kappa(vote_lists)
        except (TypeError, ValueError):
            kappa = None
    else:
        kappa = None
    return {
        "n": n,
        "agreement": agreement,
        "agreement_decided": agreement_decided,
        "mean_flip_rate": mean_flip,
        "kappa": kappa,
        "pairs": records,
    }
