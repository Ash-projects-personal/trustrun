"""Build the eval retrieval corpus from real data.

Two sources, both real:
1. The first 300 usable rows of databricks-dolly-15k (the same raw file
   the Lexsi collapse gate measured). Each row becomes one document of
   instruction + input + output joined.
2. Twelve short factual documents with well known verifiable facts, so the
   eval has tasks with crisp expected answers. Every capital the task
   variants ask for has its own document: a variant whose answer is
   missing from the corpus cannot be answered from retrieval, and the
   consistency module's identical-output check then misfires (see
   TRUSTRUN-CheatCoverage: t18_tokyo BLOCKed 12/12 agents in round 19
   because no Berlin or Rome document existed).

Writes evals/corpus.jsonl, one {"doc_id", "text"} per line.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DOLLY = os.path.expanduser(
    "~/workspace/hackathons/lexsi-collapsewatch/dolly_raw.jsonl"
)
OUT = os.path.join(HERE, "corpus.jsonl")

# Well known facts. Each is verifiable in any reference source.
FACT_DOCS = [
    "Paris is the capital of France. The city sits on the Seine river.",
    "London is the capital of the United Kingdom. It sits on the Thames river.",
    "Tokyo is the capital of Japan. It is the largest metropolitan economy in the world.",
    "The chemical symbol for water is H2O. It is made of two hydrogen atoms and one oxygen atom.",
    "The Eiffel Tower is in Paris, France. It was completed in 1889.",
    "Mount Everest is the tallest mountain above sea level, at 8848 meters.",
    "The speed of light in vacuum is 299792458 meters per second.",
    "Python is a programming language created by Guido van Rossum. Its first release was in 1991.",
    "The human heart has four chambers: two atria and two ventricles.",
    "Denton is a city in Texas, home to the University of North Texas.",
    "Berlin is the capital of Germany. The city sits on the Spree river.",
    "Rome is the capital of Italy. The city sits on the Tiber river.",
]


def main():
    docs = []
    with open(DOLLY, encoding="utf-8") as handle:
        for line in handle:
            if len(docs) >= 300:
                break
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            parts = [
                row.get(k)
                for k in ("instruction", "input", "output")
                if isinstance(row.get(k), str) and row.get(k).strip()
            ]
            if len(parts) < 2:
                continue
            docs.append({"doc_id": "dolly-%d" % len(docs), "text": "\n".join(parts)})
    for i, text in enumerate(FACT_DOCS):
        docs.append({"doc_id": "fact-%d" % i, "text": text})
    with open(OUT, "w", encoding="utf-8") as handle:
        for doc in docs:
            handle.write(json.dumps(doc) + "\n")
    print("wrote %d docs to %s" % (len(docs), OUT))


if __name__ == "__main__":
    main()
