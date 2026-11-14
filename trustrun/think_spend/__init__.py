"""ThinkSpend: audit hidden reasoning-token spend per call site.

Reasoning models bill for thinking the user never sees. The
evidence is now measured three ways. Routes of Reasoning (Wang,
Fayyaz, Peng, arXiv:2611.05919, Nov 4, 2026): selectively editing
MoE router scores at inference cuts generated tokens by a median
of 30.4% and up to 63.3% across four models and four benchmarks,
with accuracy dropping by at most 0.5 percentage points. Concise-9B
(Lorup, arXiv:2611.02278, Nov 1, 2026): 54 to 64% of Qwen3.5-9B
thinking tokens come after the answer is already fixed, and the
concise-trained model generates 0.66x the tokens at accuracy
equivalent within 1 point. A practitioner measurement (dev.to,
Oct 11, 2026, median of 3 runs): on simple tasks 82 to 91% of
billed output tokens were hidden thinking on defaults, and
reasoning_effort low cut cost 69 to 91%; per-model medians include
GLM 5.3 Flash default 2,483 billed tokens with 2,256 hidden
versus 232 billed with 0 hidden at low effort, and DeepSeek V4.1
Flash default 1,525 billed with 1,293 hidden. OptimalThinkingBench
(arXiv:2508.13141, Oct 2025) is the benchmark for this axis: 33
models, none optimally thinks, best score o3 at 72.7%.

What is new here is the auditor, not the observation that
reasoning costs money. OptimalThinkingBench is a benchmark: it
scores models, it does not audit a team's own agent. Routes of
Reasoning, Self-Route (30 to 55% token reduction at under 2%
accuracy loss, arXiv:2505.20664), Concise-9B, and ThinkJev are
methods and papers: they show how to cut thinking, they do not
ship a per-call-site audit. The dev.to measurement is a one-off
script per model, not a receipt, and it carries no accuracy
guard. Cost dashboards report spend; no shipped tool found
attributes hidden thinking tokens per call site, scores cost
per correct task, and returns an effort recommendation guarded
by the site's own accuracy, as a receipt inside an agent audit
report. That fused auditor plus receipt is the new piece.
Distinct from SilentDrop (a sequential-testing regression
detector over outcome labels) and from the contract judge (which
scores whether the work is right, not what it cost): this scores
what the right work cost.

A call is one recorded model call with the usage fields the
provider reports: visible tokens, reasoning tokens (from
usage.completion_tokens_details.reasoning_tokens, billed at the
output rate), whether the answer was correct against the team's
own ground truth, the call site, the difficulty the team assigned
(simple or hard), the effort setting, and the output price per
million tokens. A call site is a waste site when it is simple,
its accuracy is at or above the floor, and its mean hidden share
is at or above the bar: the agent already answers correctly and
still spends most of its tokens thinking. The campaign receipt
reports total cost, hidden cost, cost per correct task, the waste
share of the bill, and the tuning estimate: where a site already
has low-effort calls, the saving from moving its default-effort
calls to the observed low-effort reasoning level, and whether
that saving meets the win bar (at least 50% off simple-site cost
with accuracy loss at most 1 point, the queue's bar). The verdict
bars are Trustrun's chosen bars, documented here: PASS when no
waste site exists; BLOCK when waste is half or more of the bill;
otherwise REVIEW. An empty campaign, or one with zero total cost,
is REVIEW: there is nothing to score, so it is unscored, never
passed.

Honest limits, read before quoting any number from this module:
reasoning-token counts are provider-reported, never independently
measured; a provider that under-reports them makes the waste
look smaller than it is. The module measures hidden-token share,
not slack: the Concise-9B slack share (thinking after the answer
is fixed) needs trace-level forced readouts and cannot be read
from usage fields. A downgrade recommendation is about the
recorded calls, not a promise: cutting effort on a site whose
accuracy was measured on few calls can lose accuracy the receipt
does not see. The labeled cases in the verify script are fixed
call traces with hand-computed scores, including the dev.to
per-model medians as inputs; they are not production traces.
"""

VERDICT_BLOCK = "BLOCK"
VERDICT_REVIEW = "REVIEW"
VERDICT_PASS = "PASS"

# Effort levels accepted, the union of the provider scales
# (OpenAI none/minimal/low/medium/high/xhigh/max, Anthropic
# low/medium/high/xhigh/max, Meta minimal/low/medium/high).
EFFORT_LEVELS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")

# Effort levels that count as already tuned for a site.
LOW_EFFORT_LEVELS = ("none", "minimal", "low")

# Rank used to find the highest effort present at a site.
_EFFORT_RANK = {level: index for index, level in enumerate(EFFORT_LEVELS)}

# Trustrun's chosen bars (not the papers').
ACCURACY_FLOOR = 0.90
HIDDEN_SHARE_BAR = 0.50
WASTE_SHARE_BLOCK = 0.50
WIN_SAVING_SHARE = 0.50
WIN_ACCURACY_LOSS = 0.01


def _check_call(call):
    if not isinstance(call, dict):
        raise ValueError("call must be a dict")
    for key in (
        "call_site",
        "visible_tokens",
        "reasoning_tokens",
        "correct",
        "difficulty",
        "effort",
        "price_per_million_output",
    ):
        if call.get(key) is None:
            raise ValueError("call is missing %s" % key)
    if not isinstance(call["call_site"], str):
        raise ValueError("call_site must be a string")
    for key in ("visible_tokens", "reasoning_tokens"):
        value = call[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("%s must be an int" % key)
        if value < 0:
            raise ValueError("%s must not be negative" % key)
    if not isinstance(call["correct"], bool):
        raise ValueError("correct must be a bool")
    if call["difficulty"] not in ("simple", "hard"):
        raise ValueError("difficulty must be 'simple' or 'hard'")
    if call["effort"] not in EFFORT_LEVELS:
        raise ValueError("effort must be one of %s" % (EFFORT_LEVELS,))
    price = call["price_per_million_output"]
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        raise ValueError("price_per_million_output must be a number")
    if price <= 0:
        raise ValueError("price_per_million_output must be positive")


def hidden_share(call):
    """Share of a call's tokens that were hidden thinking.

    Returns None when the call has zero tokens in total.
    """
    _check_call(call)
    total = call["visible_tokens"] + call["reasoning_tokens"]
    if total == 0:
        return None
    return call["reasoning_tokens"] / total


def call_cost(call):
    """Cost of one call in dollars (reasoning billed at output rate)."""
    _check_call(call)
    total = call["visible_tokens"] + call["reasoning_tokens"]
    return total * call["price_per_million_output"] / 1000000.0


def hidden_cost(call):
    """Cost of one call's hidden thinking tokens in dollars."""
    _check_call(call)
    return call["reasoning_tokens"] * call["price_per_million_output"] / 1000000.0


def _rate(numerator, denominator):
    if denominator == 0:
        return None
    return numerator / denominator


def _recommendation(site):
    """Effort recommendation for one scored call site.

    Downgrade to low only on a simple site that is already
    accurate and still spends most of its tokens thinking, and
    only when its current effort is above low. Hard sites keep
    their effort: the thinking earns its cost there. A site
    below the accuracy floor keeps its effort too: cutting
    thinking on a site that is already wrong risks more wrong
    answers, and the receipt must not recommend that.
    """
    if site["difficulty"] != "simple":
        return {
            "recommendation": "keep",
            "reason": "hard tasks earn their thinking",
        }
    if site["accuracy"] is None or site["accuracy"] < ACCURACY_FLOOR:
        return {
            "recommendation": "keep",
            "reason": "accuracy below floor; do not cut effort",
        }
    if (
        site["mean_hidden_share"] is None
        or site["mean_hidden_share"] < HIDDEN_SHARE_BAR
    ):
        return {
            "recommendation": "keep",
            "reason": "hidden share below bar",
        }
    if site["highest_effort"] in LOW_EFFORT_LEVELS:
        return {
            "recommendation": "keep",
            "reason": "already at low effort",
        }
    return {
        "recommendation": "downgrade_to_low",
        "reason": "simple, accurate, most tokens hidden",
    }


def score_call_site(calls):
    """Score one call site's recorded calls.

    All calls must share one call_site and one difficulty.
    Returns accuracy, mean hidden share, total and hidden cost,
    cost per correct task, mean reasoning tokens, and the effort
    recommendation. Cost per correct task is None when nothing
    was correct; mean hidden share is None when every call has
    zero tokens.
    """
    if not isinstance(calls, list):
        raise ValueError("calls must be a list")
    if not calls:
        raise ValueError("calls must not be empty")
    for call in calls:
        _check_call(call)
    sites = {call["call_site"] for call in calls}
    if len(sites) != 1:
        raise ValueError("calls must share one call_site")
    difficulties = {call["difficulty"] for call in calls}
    if len(difficulties) != 1:
        raise ValueError("calls must share one difficulty")
    correct = sum(1 for call in calls if call["correct"])
    shares = [hidden_share(call) for call in calls]
    shares = [share for share in shares if share is not None]
    mean_share = sum(shares) / len(shares) if shares else None
    total_cost = sum(call_cost(call) for call in calls)
    hidden_total = sum(hidden_cost(call) for call in calls)
    cost_per_correct = _rate(total_cost, correct)
    mean_reasoning = sum(
        call["reasoning_tokens"] for call in calls
    ) / len(calls)
    highest_effort = max(
        (call["effort"] for call in calls),
        key=lambda level: _EFFORT_RANK[level],
    )
    site = {
        "call_site": calls[0]["call_site"],
        "difficulty": calls[0]["difficulty"],
        "calls": len(calls),
        "accuracy": correct / len(calls),
        "mean_hidden_share": mean_share,
        "total_cost": total_cost,
        "hidden_cost": hidden_total,
        "cost_per_correct": cost_per_correct,
        "mean_reasoning_tokens": mean_reasoning,
        "highest_effort": highest_effort,
    }
    site["recommendation"] = _recommendation(site)
    return site


def _tuning_estimate(sites, calls):
    """Saving from moving waste sites to their observed low level.

    For each waste site with low-effort calls, the tuned reasoning
    level is the mean reasoning tokens of those low-effort calls,
    and the saving is the excess reasoning on the site's other
    calls. Returns the saving, the simple-site cost it is measured
    against, the saving share, the accuracy delta between the
    site's low-effort and other calls, and whether the win bar is
    met. All None/False when no waste site has a low-effort
    baseline: a saving with no observed baseline is not estimated
    from a paper, it is reported as unknown.
    """
    waste_sites = [site for site in sites if site["is_waste"]]
    saving = 0.0
    baseline_seen = False
    low_correct = 0
    low_calls = 0
    other_correct = 0
    other_calls = 0
    for site in waste_sites:
        site_calls = [
            call for call in calls if call["call_site"] == site["call_site"]
        ]
        low = [
            call for call in site_calls if call["effort"] in LOW_EFFORT_LEVELS
        ]
        other = [
            call
            for call in site_calls
            if call["effort"] not in LOW_EFFORT_LEVELS
        ]
        if not low or not other:
            continue
        baseline_seen = True
        tuned = sum(call["reasoning_tokens"] for call in low) / len(low)
        for call in other:
            excess = call["reasoning_tokens"] - tuned
            if excess > 0:
                saving += excess * call["price_per_million_output"] / 1000000.0
        low_correct += sum(1 for call in low if call["correct"])
        low_calls += len(low)
        other_correct += sum(1 for call in other if call["correct"])
        other_calls += len(other)
    simple_cost = sum(
        site["total_cost"] for site in sites if site["difficulty"] == "simple"
    )
    if not baseline_seen:
        return {
            "saving": None,
            "simple_cost": simple_cost,
            "saving_share": None,
            "accuracy_delta": None,
            "tuning_wins": False,
        }
    saving_share = _rate(saving, simple_cost)
    low_accuracy = _rate(low_correct, low_calls)
    other_accuracy = _rate(other_correct, other_calls)
    if low_accuracy is None or other_accuracy is None:
        accuracy_delta = None
    else:
        accuracy_delta = low_accuracy - other_accuracy
    tuning_wins = (
        saving_share is not None
        and saving_share >= WIN_SAVING_SHARE
        and accuracy_delta is not None
        and accuracy_delta >= -WIN_ACCURACY_LOSS
    )
    return {
        "saving": saving,
        "simple_cost": simple_cost,
        "saving_share": saving_share,
        "accuracy_delta": accuracy_delta,
        "tuning_wins": tuning_wins,
    }


def score_campaign(calls, accuracy_floor=ACCURACY_FLOOR,
                   hidden_share_bar=HIDDEN_SHARE_BAR):
    """Score a campaign of recorded calls across call sites.

    Reports per-site scores, totals, the waste share of the bill,
    and the tuning estimate. Verdict PASS when no waste site
    exists; BLOCK when waste is half or more of the bill;
    otherwise REVIEW. An empty campaign, or one with zero total
    cost, is REVIEW.
    """
    if not isinstance(calls, list):
        raise ValueError("calls must be a list")
    if not (0.0 < accuracy_floor <= 1.0):
        raise ValueError("accuracy_floor must be in (0, 1]")
    if not (0.0 < hidden_share_bar < 1.0):
        raise ValueError("hidden_share_bar must be in (0, 1)")
    if not calls:
        return {
            "sites": [],
            "calls": 0,
            "accuracy": None,
            "total_cost": 0.0,
            "hidden_cost": 0.0,
            "hidden_cost_share": None,
            "cost_per_correct": None,
            "waste_sites": [],
            "waste_hidden_cost": 0.0,
            "waste_share": None,
            "tuning": _tuning_estimate([], calls),
            "verdict": VERDICT_REVIEW,
        }
    for call in calls:
        _check_call(call)
    grouped = {}
    for call in calls:
        grouped.setdefault(call["call_site"], []).append(call)
    sites = []
    for name in sorted(grouped):
        site = score_call_site(grouped[name])
        site["is_waste"] = (
            site["difficulty"] == "simple"
            and site["accuracy"] is not None
            and site["accuracy"] >= accuracy_floor
            and site["mean_hidden_share"] is not None
            and site["mean_hidden_share"] >= hidden_share_bar
        )
        sites.append(site)
    correct = sum(1 for call in calls if call["correct"])
    total_cost = sum(call_cost(call) for call in calls)
    hidden_total = sum(hidden_cost(call) for call in calls)
    waste_hidden = sum(
        site["hidden_cost"] for site in sites if site["is_waste"]
    )
    waste_share = _rate(waste_hidden, total_cost)
    tuning = _tuning_estimate(sites, calls)
    if total_cost == 0 or waste_share is None:
        verdict = VERDICT_REVIEW
    elif waste_share >= WASTE_SHARE_BLOCK:
        verdict = VERDICT_BLOCK
    elif waste_share == 0.0:
        verdict = VERDICT_PASS
    else:
        verdict = VERDICT_REVIEW
    return {
        "sites": sites,
        "calls": len(calls),
        "accuracy": correct / len(calls),
        "total_cost": total_cost,
        "hidden_cost": hidden_total,
        "hidden_cost_share": _rate(hidden_total, total_cost),
        "cost_per_correct": _rate(total_cost, correct),
        "waste_sites": [
            site["call_site"] for site in sites if site["is_waste"]
        ],
        "waste_hidden_cost": waste_hidden,
        "waste_share": waste_share,
        "tuning": tuning,
        "verdict": verdict,
    }


def format_summary(campaign):
    """One-line human summary of a scored campaign."""
    total_cost = campaign["total_cost"]
    hidden_share_value = campaign["hidden_cost_share"]
    hidden_text = (
        "%.4f" % hidden_share_value if hidden_share_value is not None else "n/a"
    )
    waste_share = campaign["waste_share"]
    waste_text = "%.4f" % waste_share if waste_share is not None else "n/a"
    tuning = campaign["tuning"]
    tuning_text = (
        "tuning wins"
        if tuning["tuning_wins"]
        else "tuning unproven"
        if tuning["saving_share"] is None
        else "tuning loses"
    )
    return (
        "ThinkSpend: %d calls, %d sites, cost $%.4f, hidden share %s, "
        "waste share %s, %s, verdict %s"
        % (
            campaign["calls"],
            len(campaign["sites"]),
            total_cost,
            hidden_text,
            waste_text,
            tuning_text,
            campaign["verdict"],
        )
    )
