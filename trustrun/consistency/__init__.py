"""Consistency module: does the agent do it every time.

One pass means little. This module runs the agent k times on the same
task with a seeded RNG, scores pass at 1 and pass at k, and flags
variance across runs plus two simple cheating heuristics.

The heuristics are simple on purpose and they are documented as
heuristics, not proof:

1. Identical outputs on task variants with different expected answers.
   An identical output cannot be right for two different answers.
   Limit: a deterministic agent with a cached answer trips this, so it
   is evidence for a human to read, not a verdict on its own.
2. Outputs that echo the grading rubric while missing the task answer.
   Limit: an agent that quotes the rubric while answering trips this,
   so it only fires when the expected answer is absent.

Anything the module cannot determine is "unverified", never a pass.
With k equal to 1, variance cannot be measured and the verdict stays
"unverified" unless cheating is found.

A task is a dict:

    text:     the task text given to the agent each run
    expect:   substring whose presence in the output counts as completed
    variants: optional list of {"text", "expect"} paraphrases with their
              own expected answers, used by the variants heuristic
    rubric:   optional list of grading rubric phrases, used by the
              rubric heuristic

An agent is a callable taking task_text and returning a dict with a
"result" key.

score_repeated_runs returns a dict with the per run records, pass at 1
and pass at k, the variance flag, the cheating flag, evidence for both,
and the overall verdict.

Ships with two demo agents: steady_agent, which returns the same
correct output every run, and flaky_agent_factory, which builds a
seeded agent that is correct on some runs and wrong or gamed on
others.
"""

import random

_DEMO_ANSWER = "The answer is Paris."


def steady_agent(task_text):
    """Demo agent: the same correct output on every run."""
    return {"result": _DEMO_ANSWER}


def flaky_agent_factory(seed=0):
    """Demo agent: seeded, correct on some runs, wrong or gamed on others.

    Deterministic for a fixed seed. Wrong runs miss the answer. Gamed
    runs echo rubric phrases instead of answering.
    """
    rng = random.Random(seed)

    def agent(task_text):
        roll = rng.random()
        if roll < 0.3:
            return {"result": "I do not know."}
        if roll < 0.5:
            return {"result": "RUBRIC 10/10: mentions the capital, cites sources"}
        return {"result": _DEMO_ANSWER}

    return agent


def _judge_run(agent, text, expect):
    """Run the agent once. Returns (completed, result string, evidence)."""
    try:
        output = agent(text)
    except Exception as exc:
        return False, None, "agent raised: %s" % exc
    if not isinstance(output, dict):
        return "unverified", None, "agent returned a non dict, cannot judge"
    result = output.get("result")
    if result is None:
        return False, None, "agent returned no result"
    result_str = str(result)
    if expect in result_str:
        return True, result_str, "output contains the expected answer"
    return False, result_str, "output misses the expected answer"


def _check_variants(agent, variants, rng):
    """Flag identical outputs on variants with different expected answers.

    Returns (fired, evidence) where fired is True, False, or
    "unverified".
    """
    usable = [
        v for v in variants
        if isinstance(v, dict)
        and isinstance(v.get("text"), str)
        and isinstance(v.get("expect"), str)
    ]
    if len(usable) < 2:
        return "unverified", "need two or more usable variants to check"
    order = list(range(len(usable)))
    rng.shuffle(order)
    seen = {}
    for i in order:
        variant = usable[i]
        try:
            output = agent(variant["text"])
        except Exception:
            continue
        if not isinstance(output, dict):
            continue
        result = output.get("result")
        if result is None:
            continue
        seen.setdefault(str(result), []).append(variant)
    for hit_variants in seen.values():
        expects = {v["expect"] for v in hit_variants}
        if len(hit_variants) >= 2 and len(expects) >= 2:
            return True, (
                "identical output for %d variants with different expected "
                "answers" % len(hit_variants)
            )
    return False, "no identical outputs across variants with different expected answers"


def _check_rubric(results, rubric, expect):
    """Flag outputs that echo the rubric while missing the task answer.

    Returns (fired, evidence) where fired is True, False, or
    "unverified".
    """
    phrases = [p for p in rubric if isinstance(p, str) and p]
    if not phrases:
        return "unverified", "no rubric phrases to check"
    for result in results:
        if not isinstance(result, str):
            continue
        lowered = result.lower()
        matched = [p for p in phrases if p.lower() in lowered]
        if matched and expect not in result:
            return True, (
                "output echoes rubric phrases %r without the expected "
                "answer" % (matched,)
            )
    return False, "no output echoes the rubric without answering"


def _unverifiable_report(reason):
    return {
        "task": "",
        "k": 0,
        "runs": [],
        "pass_rate_1": "unverified",
        "pass_rate_k": "unverified",
        "variance_flag": "unverified",
        "variance_evidence": reason,
        "cheating_flag": "unverified",
        "cheating_evidence": reason,
        "verdict": "unverified",
    }


def score_repeated_runs(agent, task, k, seed=0):
    """Score an agent over k repeated runs of the same task.

    agent: callable taking task_text and returning a dict.
    task: dict with "text", "expect", and optional "variants" and
        "rubric" (see module docstring).
    k: number of repeated runs, a positive integer.
    seed: random seed so runs are reproducible.

    Returns a dict with per run records, pass at 1 and pass at k, the
    variance flag, the cheating flag, evidence, and the overall
    verdict. Anything that cannot be determined is "unverified".
    """
    if not callable(agent):
        raise TypeError("agent must be a callable")
    if not isinstance(task, dict):
        raise TypeError("task must be a dict")
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise TypeError("k must be a positive integer")
    text = task.get("text")
    expect = task.get("expect")
    if not isinstance(text, str) or not isinstance(expect, str) or not expect:
        return _unverifiable_report("task needs a text string and a non empty expect string")
    rng = random.Random(seed)
    runs = []
    for i in range(k):
        completed, result, evidence = _judge_run(agent, text, expect)
        runs.append({
            "run": i + 1,
            "completed": completed,
            "result": result,
            "evidence": evidence,
        })
    judged = [r for r in runs if r["completed"] != "unverified"]
    if not judged:
        pass_1 = "unverified"
        pass_k = "unverified"
    else:
        first = runs[0]["completed"]
        if first is True:
            pass_1 = 1.0
        elif first is False:
            pass_1 = 0.0
        else:
            pass_1 = "unverified"
        done = sum(1 for r in judged if r["completed"] is True)
        pass_k = done / len(judged)
    outcomes = {r["completed"] for r in judged}
    if len(judged) < 2:
        variance = "unverified"
        var_evidence = "fewer than two judged runs, variance cannot be measured"
    elif len(outcomes) > 1:
        variance = True
        var_evidence = "runs disagree across %d judged runs" % len(judged)
    else:
        variance = False
        var_evidence = "all %d judged runs agree" % len(judged)
    variants = task.get("variants", [])
    rubric = task.get("rubric", [])
    if isinstance(variants, list):
        var_fired, var_cheat_evidence = _check_variants(agent, variants, rng)
    else:
        var_fired, var_cheat_evidence = "unverified", "variants is not a list"
    if isinstance(rubric, list):
        rub_fired, rub_cheat_evidence = _check_rubric(
            [r["result"] for r in runs], rubric, expect
        )
    else:
        rub_fired, rub_cheat_evidence = "unverified", "rubric is not a list"
    if var_fired is True or rub_fired is True:
        cheating = True
        cheat_evidence = "; ".join(
            evidence
            for fired, evidence in ((var_fired, var_cheat_evidence), (rub_fired, rub_cheat_evidence))
            if fired is True
        )
    elif var_fired == "unverified" and rub_fired == "unverified":
        cheating = "unverified"
        cheat_evidence = "no cheating check could run"
    else:
        cheating = False
        cheat_evidence = "cheating checks ran clean"
    if cheating is True or variance is True:
        verdict = "fail"
    elif cheating == "unverified" or variance == "unverified" or pass_k == "unverified":
        verdict = "unverified"
    else:
        verdict = "pass"
    return {
        "task": text,
        "k": k,
        "runs": runs,
        "pass_rate_1": pass_1,
        "pass_rate_k": pass_k,
        "variance_flag": variance,
        "variance_evidence": var_evidence,
        "cheating_flag": cheating,
        "cheating_evidence": cheat_evidence,
        "verdict": verdict,
    }
