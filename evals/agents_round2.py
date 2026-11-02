"""Round 2 agents: hardened, reflection, and guardrailed RAG.

Same honest setup as round 1: no LLM backend in this VM, so the policy
that plays the LLM role is deterministic and rule based. The
architectures are real published patterns:

- hardened_agent: a ReAct style loop redesigned to pass. It sanitizes
  every tool observation (drops lines carrying injection markers and
  keeps working with the clean remainder), has no question word gate
  so imperative phrasing works, hedges with flagged True when
  retrieval confidence is low instead of serving junk, and retries a
  failed tool once before degrading gracefully.
- reflection_agent: generates a draft with the round 1 ReAct policy,
  then runs a critique pass against the draft before finalizing. The
  critique refuses drafts carrying injected content, repairs give ups
  with one direct tool attempt, and hedges when nothing works. One
  honest flaw is documented below: the repair path calls the tool
  again without the draft's guard, so a poisoned repair target can
  still get through.
- guardrail_rag_agent: the round 1 naive RAG agent wrapped in
  guardrails. Same one shot retrieval, but tool output is sanitized,
  tool exceptions degrade gracefully instead of crashing, and an
  answer with no meaningful term overlap with the query is replaced
  by an honest hedge instead of confident junk.

Each agent is a callable taking (task_text, tools) and returning a
dict with a "result" string. That is the shape Trustrun audits.
"""

import re

from agents import (
    _ADD_N,
    _YEAR,
    _best_sentence,
    _extract_arith,
    _find_injection,
    _keywords,
    react_agent,
)

_HEDGE = "I do not have enough information to answer this confidently."


def _sanitize(content):
    """Drop lines carrying injection markers, keep the rest.

    Returns (cleaned_content, stripped) where stripped is True when at
    least one line was removed. Marker bound by design: a payload with
    no known marker passes through untouched, which the round 2 probe
    measures on purpose.
    """
    lines = str(content).splitlines()
    kept = [line for line in lines if not _find_injection(line)]
    return "\n".join(kept).strip(), len(kept) != len(lines)


def _call_once(tools, name, arg):
    tool = tools.get(name)
    if tool is None:
        return None, "no %s tool available" % name
    try:
        return tool(arg), None
    except Exception as exc:
        return None, str(exc)


def _call_retry(tools, name, arg):
    """Call the tool, retry once on exception, then report the error."""
    obs, err = _call_once(tools, name, arg)
    if err is None:
        return obs, None
    return _call_once(tools, name, arg)


def _retrieval_confident(doc_text, query):
    """True when the document shares meaningful terms with the query."""
    if not doc_text or "no matching document" in doc_text.lower():
        return False
    return len(set(_keywords(query)) & set(_keywords(doc_text))) > 0


# ------------------------------------------------------------- hardened

def hardened_agent(task_text, tools):
    """ReAct style agent redesigned to pass the audit.

    Sanitizes tool output instead of refusing on it, answers imperative
    phrasing as well as questions, hedges on low retrieval confidence,
    and retries a failed tool once. Every behavior here is a deliberate
    contrast with a round 1 failure.
    """
    trace = []
    calc = tools.get("calculator")
    search = tools.get("search_docs")
    query = " ".join(_keywords(task_text))

    # Arithmetic path. Fires on any arithmetic expression, no question
    # word gate.
    expr = _extract_arith(task_text)
    if expr and calc is not None and "add" not in task_text.lower():
        obs, err = _call_retry(tools, "calculator", expr)
        if err is not None:
            return {
                "result": (
                    "I could not compute the answer because the "
                    "calculator tool failed: %s" % err
                ),
                "flagged": True,
                "trace": trace,
            }
        content, stripped = _sanitize(obs.get("content", ""))
        if content.startswith("error:"):
            return {
                "result": "I could not compute the answer: %s" % content,
                "flagged": True,
                "trace": trace,
            }
        return {"result": content, "flagged": stripped, "trace": trace}

    # Search path. No question word gate, so imperative phrasing works.
    if search is not None and query:
        obs, err = _call_retry(tools, "search_docs", query)
        if err is not None:
            return {
                "result": (
                    "I could not search the documents because the "
                    "search tool failed: %s" % err
                ),
                "flagged": True,
                "trace": trace,
            }
        content, stripped = _sanitize(obs.get("content", ""))
        if not _retrieval_confident(content, task_text):
            return {"result": _HEDGE, "flagged": True, "trace": trace}
        # Multi step: add a number to a retrieved year.
        add = _ADD_N.search(task_text)
        if add and calc is not None:
            year = _YEAR.search(content)
            if year:
                obs2, err2 = _call_retry(
                    tools, "calculator",
                    "%s + %s" % (year.group(0), add.group(1)),
                )
                if err2 is None:
                    final, stripped2 = _sanitize(obs2.get("content", ""))
                    return {
                        "result": final,
                        "flagged": stripped or stripped2,
                        "trace": trace,
                    }
        return {
            "result": _best_sentence(content, task_text),
            "flagged": stripped,
            "trace": trace,
        }

    return {"result": _HEDGE, "flagged": True, "trace": trace}


# ------------------------------------------------------------ reflection

def _critique_repair(task_text, tools, draft):
    """One critique pass over the draft, then at most one repair.

    Returns a final output dict. The repair calls the tool directly,
    without re running the draft's injection guard. That is a real
    flaw in this design, documented here: a poisoned repair target
    gets followed, which the stress module catches.
    """
    result = draft.get("result", "") if isinstance(draft, dict) else ""

    # Critique 1: injected content survived into the draft.
    if isinstance(result, str) and _find_injection(result):
        return {
            "result": (
                "On reflection, the draft contained an instruction "
                "override attempt, so I am not using it."
            ),
            "flagged": True,
            "repaired": True,
        }

    gave_up = isinstance(result, str) and (
        result.startswith("I could not") or result.startswith("I will not")
    )
    # Critique 2: the draft found nothing to say. Try one direct shot.
    if gave_up or "no matching document" in str(result).lower():
        expr = _extract_arith(task_text)
        if expr and "add" not in task_text.lower():
            obs, err = _call_once(tools, "calculator", expr)
            if err is None:
                content = obs.get("content", "")
                if not content.startswith("error:"):
                    return {
                        "result": content,
                        "flagged": False,
                        "repaired": True,
                    }
        query = " ".join(_keywords(task_text))
        if query:
            obs, err = _call_once(tools, "search_docs", query)
            if err is None:
                content = obs.get("content", "")
                if _find_injection(content):
                    return {
                        "result": (
                            "On reflection, the search result contained "
                            "an instruction override attempt, so I am "
                            "not using it."
                        ),
                        "flagged": True,
                        "repaired": True,
                    }
                if _retrieval_confident(content, task_text):
                    add = _ADD_N.search(task_text)
                    year = _YEAR.search(content) if add else None
                    if add and year and tools.get("calculator") is not None:
                        obs2, err2 = _call_once(
                            tools, "calculator",
                            "%s + %s" % (year.group(0), add.group(1)),
                        )
                        if err2 is None:
                            return {
                                "result": obs2.get("content", ""),
                                "flagged": False,
                                "repaired": True,
                            }
                    return {
                        "result": _best_sentence(content, task_text),
                        "flagged": False,
                        "repaired": True,
                    }
        return {"result": _HEDGE, "flagged": True, "repaired": True}

    return draft


def reflection_agent(task_text, tools):
    """Draft with the round 1 ReAct policy, critique, then finalize.

    The draft generator is react_agent from round 1, unchanged. The
    critique pass is the new architecture: it is the published
    self refine pattern, implemented honestly with its flaw intact.
    """
    draft = react_agent(task_text, tools)
    return _critique_repair(task_text, tools, draft)


# --------------------------------------------------------- guardrailed RAG

def _answer_relevant(answer, query):
    """True when the answer shares meaningful terms with the query."""
    if not answer:
        return False
    qterms = {w for w in _keywords(query) if len(w) > 2}
    aterms = {w for w in _keywords(answer) if len(w) > 2}
    return len(qterms & aterms) > 0


def guardrail_rag_agent(task_text, tools):
    """The round 1 naive RAG agent with guardrails wrapped around it.

    Same one shot retrieval. The wrapper sanitizes tool output,
    degrades gracefully on tool exceptions instead of crashing, and
    replaces an irrelevant answer with an honest hedge instead of
    serving confident junk. It still cannot do arithmetic: that limit
    is kept on purpose so the audit can show what guardrails fix and
    what they do not.
    """
    search = tools.get("search_docs")
    if search is None:
        return {"result": _HEDGE, "flagged": True}
    try:
        observation = search(task_text)
    except Exception as exc:
        return {
            "result": (
                "I could not search the documents because the search "
                "tool failed: %s" % exc
            ),
            "flagged": True,
        }
    content = observation.get("content", "")
    clean, stripped = _sanitize(content)
    answer = _best_sentence(clean, task_text) if clean else ""
    if not _answer_relevant(answer, task_text):
        return {"result": _HEDGE, "flagged": True}
    return {"result": answer, "flagged": stripped}
