"""Multi-trial contract judging: the JudgeRedesign (TRUSTRUN-JudgeRedesign).

Single-trial LLM-as-judge verdicts are noisy. Yagubyan (arXiv:2606.13685,
verified against the arXiv abstract 2026-11-06) measured pairwise
preferences flipping 13.6% of the time on average, cross-judge agreement
of only 76% (kappa 0.51), and found 11 repeated trials are needed for a
majority vote to recover the 50-trial reference verdict with 95%
probability on average (15 for high-variance questions). This module
implements that prescription for Trustrun's contract judge: repeated
trials, position randomization, majority vote, and chance-corrected
agreement reported next to raw agreement.

Design rules, each with a named source:

- Trials: at least 11 rounds per judge-kind claim (Yagubyan 2606.13685).
  A round runs every panel judge once on the claim.
- Panel: trials run a panel of judge callables from different families,
  and per-family agreement is reported. The panel is a measurement
  device, not a claimed accuracy gain: Carro et al. (arXiv:2610.28539,
  verified 2026-11-06) found multi-judge protocols do not significantly
  improve group accuracy for LLM judges.
- No debate: judges never deliberate with each other. Carro et al.
  (2610.28539) found debate gives weaker LLM judges no comparable gains
  and can reduce accuracy, so there is no debate step here on purpose.
- Binary criteria: exact/contains/numeric claims are binary-verifiable
  atoms by construction and are judged once, deterministically; only
  judge-kind claims go through trials. The report states binary
  coverage: the share of claims judged by binary atoms.
- Tool access: judges receive a tools mapping in their context, so a
  judge can re-run a check instead of judging from text alone.
- Kappa: Fleiss' kappa across the contract's judge-kind claims, with
  trials (rounds x panel judges) as raters, reported alongside raw
  agreement. Kappa is computed across claims, never within one claim:
  with a single subject Fleiss' kappa collapses to -1/(n-1) for any
  disagreement, so a one-claim kappa would be a meaningless number.
  Kappa is None when there is only one judge-kind claim, when every
  trial agrees on every claim (a single category, chance agreement 1.0),
  or when no judge-kind claim ran.

Note on a withdrawn source: the queue's kappa-deflation figure
(33-41pp, Norman/Rivera/Hughes arXiv:2606.19544) is NOT cited here.
That paper was withdrawn by arXiv Admin (checked 2026-11-06). Kappa
reporting stands on the standard chance-correction argument and on
Yagubyan's live kappa 0.51 figure.
"""

import inspect
import random

MIN_TRIALS = 11

CATEGORIES = ("pass", "fail", "unverified")

_BINARY_KINDS = ("exact", "contains", "numeric")


def binary_coverage(contract):
    """Share of a contract's claims judged by binary-verifiable atoms.

    exact/contains/numeric claims are binary atoms by construction;
    judge-kind claims are not. Returns 1.0 for a contract with no
    claims, and 0.0 when no claim is binary.
    """
    claims = (contract or {}).get("claims", []) or []
    if not claims:
        return 1.0
    binary = sum(1 for c in claims if c.get("kind", "exact") in _BINARY_KINDS)
    return binary / len(claims)


def _decision_to_category(decision):
    if decision is True:
        return "pass"
    if decision is False:
        return "fail"
    return "unverified"


def majority_vote(votes):
    """Majority category of a vote list, with its share.

    A tie resolves to "unverified", never to a pass: a tied judge is an
    undecided judge. An empty vote list is unverified with share 0.0.
    """
    if not votes:
        return "unverified", 0.0
    counts = {category: votes.count(category) for category in CATEGORIES}
    top = max(counts.values())
    winners = [c for c, n in counts.items() if n == top]
    if len(winners) != 1:
        return "unverified", top / len(votes)
    return winners[0], top / len(votes)


def fleiss_kappa(ratings):
    """Fleiss' kappa over subjects rated by the same raters.

    ratings: a list of subjects; each subject is a list of category
    strings, one per rater. Every subject must have the same number of
    raters, and there must be at least two subjects: with one subject
    the statistic collapses to -1/(n-1) for any disagreement, which is
    an artifact, not a measurement. Returns None when agreement is
    perfect across a single category (chance agreement 1.0, kappa
    undefined) or when the inputs cannot support a kappa.
    """
    subjects = [list(r) for r in ratings]
    if len(subjects) < 2:
        return None
    n_raters = len(subjects[0])
    if n_raters < 2:
        return None
    if any(len(s) != n_raters for s in subjects):
        raise ValueError("every subject needs the same number of ratings")
    if any(r not in CATEGORIES for s in subjects for r in s):
        raise ValueError("ratings must be pass/fail/unverified")
    n_subjects = len(subjects)
    total = n_subjects * n_raters
    category_totals = {c: 0 for c in CATEGORIES}
    p_sum = 0.0
    for subject in subjects:
        counts = {c: subject.count(c) for c in CATEGORIES}
        for c in CATEGORIES:
            category_totals[c] += counts[c]
        p_sum += sum(n * (n - 1) for n in counts.values()) / (n_raters * (n_raters - 1))
    p_bar = p_sum / n_subjects
    p_e = sum((category_totals[c] / total) ** 2 for c in CATEGORIES)
    if p_e >= 1.0:
        return None
    return (p_bar - p_e) / (1.0 - p_e)


def _judge_name(judge, index):
    name = getattr(judge, "__name__", None)
    if isinstance(name, str) and name:
        return name
    return "judge-%d" % index


def call_judge(judge, value, claim, output, context):
    """Call a judge with its context when it accepts one.

    Legacy judges take (value, claim, output). New judges may take a
    fourth argument, a context dict with trial, position, judge name,
    and tools. Arity is read from the signature; when the signature
    cannot be read, the four-argument call is tried first and a
    TypeError falls back to three arguments.
    """
    try:
        params = list(inspect.signature(judge).parameters.values())
    except (TypeError, ValueError):
        params = None
    if params is not None:
        kinds = [p.kind for p in params]
        n_positional = sum(
            1 for k in kinds
            if k in (inspect.Parameter.POSITIONAL_ONLY,
                     inspect.Parameter.POSITIONAL_OR_KEYWORD)
        )
        has_var = inspect.Parameter.VAR_POSITIONAL in kinds
        if n_positional >= 4 or has_var:
            return judge(value, claim, output, context)
        return judge(value, claim, output)
    try:
        return judge(value, claim, output, context)
    except TypeError:
        return judge(value, claim, output)


def judge_claim_trials(claim, value, output, trials=MIN_TRIALS,
                       judges=None, tools=None, seed=0, rng=None):
    """Judge one claim over repeated trials with position randomization.

    claim: a judge-kind claim dict. value: the recorded output value.
    judges: one callable or a list of callables; defaults to the
    claim's own "judge". tools: an optional mapping of tools the judge
    may call, handed to it in its context. seed: fixes the position
    draws so a run is reproducible. rng: an optional shared
    random.Random, used when one call judges several claims so the
    position draws stay independent across claims.

    Each round runs every panel judge once, with an independently drawn
    position (0 or 1) per (round, judge). A judge that raises, or
    returns a bad shape, records "unverified" for that trial instead
    of crashing the audit: multi-trial judging is explicitly about
    noisy judges, and one noisy trial must not void the other trials.

    Returns the per-claim trial record: verdict, majority share, flip
    rate (1 - majority share), raw agreement, the vote list, per-judge
    breakdowns, and the per-trial evidence.
    """
    if trials < 1:
        raise ValueError("trials must be at least 1")
    panel = judges
    if panel is None:
        panel = claim.get("judge")
    if callable(panel):
        panel = [panel]
    if not panel:
        return {
            "verdict": "unverified",
            "trials": trials,
            "votes": [],
            "majority_share": 0.0,
            "flip_rate": 0.0,
            "raw_agreement": 0.0,
            "kappa": None,
            "per_judge": {},
            "family_agreement": None,
            "evidence": ["judge claim needs a callable judge, cannot judge"],
        }
    tools = tools or {}
    if rng is None:
        rng = random.Random(seed)
    votes = []
    evidence = []
    per_judge = {}
    family_rounds = []
    for round_index in range(trials):
        round_votes = []
        for judge_index, judge in enumerate(panel):
            name = _judge_name(judge, judge_index)
            context = {
                "trial": round_index,
                "trials": trials,
                "position": rng.randint(0, 1),
                "judge_index": judge_index,
                "judge_name": name,
                "tools": tools,
            }
            try:
                result = call_judge(judge, value, claim, output, context)
            except Exception as exc:  # noqa: BLE001 - one noisy trial
                result = (None, "judge raised %s: %s" % (type(exc).__name__, exc))
            if not isinstance(result, tuple) or len(result) != 2:
                decision, note = None, "judge returned a bad shape, cannot judge"
            else:
                decision, note = result
            category = _decision_to_category(decision)
            votes.append(category)
            round_votes.append(category)
            evidence.append("trial %d %s: %s" % (round_index, name, note))
            entry = per_judge.setdefault(name, {"pass": 0, "fail": 0, "unverified": 0})
            entry[category] += 1
        family_rounds.append(len(set(round_votes)) == 1)
    verdict, share = majority_vote(votes)
    if len(panel) > 1:
        family_agreement = sum(1 for ok in family_rounds if ok) / len(family_rounds)
    else:
        family_agreement = None
    return {
        "verdict": verdict,
        "trials": trials,
        "votes": votes,
        "majority_share": share,
        "flip_rate": 1.0 - share,
        "raw_agreement": share,
        "kappa": None,  # kappa needs several claims; set by the caller
        "per_judge": per_judge,
        "family_agreement": family_agreement,
        "evidence": evidence,
    }
