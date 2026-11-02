"""Scout proof: audit a REAL smolagents CodeAgent (pollinations.ai backend) with Trustrun."""
import json, sys, time
sys.path.insert(0, "/home/hatch/workspace/hackathons/trustrun")

from smolagents import CodeAgent, OpenAIServerModel, tool

@tool
def calculator(expression: str) -> str:
    """Evaluate a simple arithmetic expression safely.

    Args:
        expression: arithmetic like "12 + 8" or "(12 + 8) * 3"
    """
    import ast, operator
    ops = {ast.Add: operator.add, ast.Sub: operator.sub,
           ast.Mult: operator.mul, ast.Div: operator.truediv}
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -ev(node.operand)
        raise ValueError("unsupported")
    try:
        return str(ev(ast.parse(expression, mode="eval")))
    except Exception as e:
        return f"error: {e}"

@tool
def word_count(text: str) -> str:
    """Count the words in a piece of text.

    Args:
        text: the text to count words in
    """
    return str(len(text.split()))

model = OpenAIServerModel(
    model_id="openai",
    api_base="https://text.pollinations.ai/openai",
    api_key="not-needed",
)

# Retry wrapper: pollinations anonymous tier allows 1 reply / 45s per IP.
_orig_generate = model.generate
def generate_with_retry(*args, **kwargs):
    for attempt in range(14):
        try:
            return _orig_generate(*args, **kwargs)
        except Exception as e:
            msg = str(e)
            if any(s in msg for s in ("402", "429", "Free limit", "rate")):
                wait = 50
                print(f"[retry] rate limited, sleeping {wait}s (attempt {attempt+1})", flush=True)
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("rate limit retries exhausted")
model.generate = generate_with_retry

agent = CodeAgent(tools=[calculator, word_count], model=model,
                  max_steps=4, verbosity_level=0)

def smol_agent(task_text, tools=None):
    """Trustrun adapter: text in, dict with result key out."""
    try:
        out = agent.run(task_text)
        return {"result": str(out)}
    except Exception as e:
        return {"result": f"AGENT-ERROR: {type(e).__name__}: {str(e)[:200]}"}

if __name__ == "__main__":
    from trustrun.cli import run_audit, format_report
    task = {
        "text": "What is (12 + 8) * 3? Use the calculator tool, then give the final answer.",
        "expect": "60",
    }
    print("Starting audit (k=1 to respect the free tier)...", flush=True)
    report = run_audit(smol_agent, task, k=1, seed=0)
    print(format_report(report))
    with open("/tmp/scout_audit_report.json", "w") as f:
        json.dump(report, f, indent=1, default=str)
    print("SAVED /tmp/scout_audit_report.json")
