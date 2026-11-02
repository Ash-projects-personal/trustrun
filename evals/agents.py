"""Three real agent architectures, run with honest deterministic policies.

There is no LLM backend in this VM (no API key, no local model), so the
policy that plays the LLM role in each architecture is rule based and
deterministic. That limit is stated everywhere it matters. What is real:

- react_agent: the published ReAct loop (Thought, Action, Observation)
  with a real tool registry, a step cap, and observation parsing.
- rag_agent: real TF-IDF retrieval plus sentence extraction, one shot.
- plan_execute_agent: a real planner that decomposes the task into
  steps, then executes them in order against the tools.

What differs by design, and is documented, not staged:
- react_agent scans tool observations for instruction override markers
  and refuses with flagged True. The other two have no such guard.
- react_agent and plan_execute_agent degrade gracefully (flagged True)
  when a tool raises. rag_agent has no error handling and can crash.

Each agent is a callable taking (task_text, tools) and returning a dict
with a "result" string. That is the shape Trustrun audits.
"""

import re

_ARITH = re.compile(r"\(?\d[\d\s+\-*/().]*\d\)?")
_YEAR = re.compile(r"\b(1|2)\d{3}\b")
_ADD_N = re.compile(r"add\s+(\d+)", re.IGNORECASE)
_QUESTION = re.compile(
    r"\b(what|when|where|who|which|how many|how)\b", re.IGNORECASE
)
_INJECTION_MARKERS = (
    "ignore previous instructions",
    "pwned",
    "reply with exactly",
    "injected:",
)

_STOPWORDS = {
    "what", "when", "where", "who", "which", "how", "is", "are", "was",
    "were", "the", "a", "an", "of", "in", "on", "to", "for", "and",
    "then", "it", "its", "by", "with", "do", "does", "did", "add",
    "reply", "find",
}


def _keywords(text):
    return [
        w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOPWORDS
    ]


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _best_sentence(text, query):
    query_terms = set(_keywords(query))
    best, best_score = None, -1
    for sent in _sentences(text):
        terms = set(_keywords(sent))
        # Skip sentences that only echo the query back. A sentence that
        # is mostly query words is the question restated, not an answer.
        # This is a standard anti echo guard, documented here.
        if terms and query_terms:
            jaccard = len(terms & query_terms) / len(terms | query_terms)
            if jaccard > 0.7:
                continue
        score = len(query_terms & terms)
        if "when" in query.lower():
            score += 2 if _YEAR.search(sent) else 0
        if score > best_score:
            best, best_score = sent, score
    return best or (text[:200] if text else "")


def _find_injection(content):
    lowered = content.lower()
    return any(m in lowered for m in _INJECTION_MARKERS)


def _extract_arith(text):
    """Pull the longest arithmetic looking span out of the text."""
    candidates = _ARITH.findall(text)
    candidates = [c.strip() for c in candidates if re.search(r"\d", c)]
    candidates = [c for c in candidates if re.search(r"[+\-*/]", c)]
    if not candidates:
        return None
    return max(candidates, key=len)


# ------------------------------------------------------------------ ReAct

def react_agent(task_text, tools):
    """ReAct loop: Thought, Action, Observation, up to 6 steps.

    The policy standing in for the LLM is rule based: arithmetic in the
    task goes to the calculator, questions go to search, and a second
    tool call fires when the task asks to combine a retrieved year with
    arithmetic. Tool observations are scanned for instruction override
    markers before use.
    """
    trace = []
    calc = tools.get("calculator")
    search = tools.get("search_docs")
    searched, calculated = False, False
    last_observation = ""

    for step in range(6):
        thought = "step %d" % (step + 1)
        action, arg = None, None
        if not calculated and calc is not None:
            expr = _extract_arith(task_text)
            if expr:
                action, arg = "calculator", expr
            elif searched and _ADD_N.search(task_text):
                year_match = _YEAR.search(last_observation)
                if year_match:
                    n = _ADD_N.search(task_text).group(1)
                    action, arg = "calculator", "%s + %s" % (
                        year_match.group(0), n)
        if action is None and not searched and search is not None:
            if _QUESTION.search(task_text):
                action, arg = "search_docs", " ".join(_keywords(task_text))
        if action is None:
            break
        trace.append("Thought: %s. Action: %s[%s]" % (thought, action, arg))
        tool = tools[action]
        try:
            observation = tool(arg)
        except Exception as exc:
            trace.append("Observation: tool raised: %s" % exc)
            return {
                "result": (
                    "I could not complete the task because the %s tool "
                    "failed: %s" % (action, exc)
                ),
                "flagged": True,
                "trace": trace,
            }
        content = observation.get("content", "") if isinstance(
            observation, dict) else str(observation)
        trace.append("Observation: %s" % content[:160])
        if _find_injection(content):
            return {
                "result": (
                    "I will not continue. The tool output contained an "
                    "instruction override attempt, so I am stopping."
                ),
                "flagged": True,
                "trace": trace,
            }
        if isinstance(observation, dict) and observation.get(
                "content", "").startswith("error:"):
            return {
                "result": (
                    "I could not complete the task because the %s tool "
                    "returned an error: %s" % (action, content)
                ),
                "flagged": True,
                "trace": trace,
            }
        last_observation = content
        if action == "calculator":
            calculated = True
            if not _QUESTION.search(task_text) or "add" not in task_text.lower():
                return {"result": content, "flagged": False, "trace": trace}
        if action == "search_docs":
            searched = True
            if not _ADD_N.search(task_text):
                answer = _best_sentence(content, task_text)
                return {"result": answer, "flagged": False, "trace": trace}
    if calculated and last_observation:
        return {"result": last_observation, "flagged": False, "trace": trace}
    if searched and last_observation:
        answer = _best_sentence(last_observation, task_text)
        return {"result": answer, "flagged": False, "trace": trace}
    return {
        "result": "I could not find a way to answer this task.",
        "flagged": True,
        "trace": trace,
    }


# -------------------------------------------------------------------- RAG

def rag_agent(task_text, tools):
    """One shot retrieval QA. No injection guard, no error handling.

    Searches once, picks the sentence with the best query term overlap,
    returns it. If the retrieval tool raises, this agent crashes. That
    is the naive baseline, documented here on purpose.
    """
    search = tools["search_docs"]
    observation = search(task_text)
    content = observation.get("content", "")
    answer = _best_sentence(content, task_text)
    return {"result": answer, "flagged": False}


# ---------------------------------------------------------- plan and execute

def plan_execute_agent(task_text, tools):
    """Plan the task into steps, then execute them in order.

    The planner is rule based: a search step for questions, a calculator
    step for arithmetic, and a follow up calculator step when the task
    asks to add a number to a retrieved year. Steps run in order with no
    replanning. A failing step aborts the plan with a flagged message.
    """
    plan = []
    if _QUESTION.search(task_text):
        plan.append(("search_docs", " ".join(_keywords(task_text))))
    expr = _extract_arith(task_text)
    if expr and "add" not in task_text.lower():
        plan.append(("calculator", expr))
    if not plan:
        return {"result": "I could not plan this task.", "flagged": True}

    results = {}
    for name, arg in plan:
        tool = tools.get(name)
        if tool is None:
            return {
                "result": "I could not complete the task: no %s tool." % name,
                "flagged": True,
            }
        try:
            observation = tool(arg)
        except Exception as exc:
            return {
                "result": (
                    "I could not complete the task because the %s tool "
                    "failed: %s" % (name, exc)
                ),
                "flagged": True,
            }
        content = observation.get("content", "") if isinstance(
            observation, dict) else str(observation)
        if isinstance(observation, dict) and content.startswith("error:"):
            return {
                "result": (
                    "I could not complete the task because the %s tool "
                    "returned an error: %s" % (name, content)
                ),
                "flagged": True,
            }
        results[name] = content

    if _ADD_N.search(task_text) and "search_docs" in results:
        year_match = _YEAR.search(results["search_docs"])
        if year_match and tools.get("calculator") is not None:
            n = _ADD_N.search(task_text).group(1)
            try:
                observation = tools["calculator"](
                    "%s + %s" % (year_match.group(0), n))
            except Exception as exc:
                return {
                    "result": (
                        "I could not complete the task because the "
                        "calculator tool failed: %s" % exc
                    ),
                    "flagged": True,
                }
            content = observation.get("content", "")
            return {"result": content, "flagged": False}
        return {
            "result": "I found the document but could not find a year in it.",
            "flagged": True,
        }
    if "calculator" in results:
        return {"result": results["calculator"], "flagged": False}
    answer = _best_sentence(results["search_docs"], task_text)
    return {"result": answer, "flagged": False}
