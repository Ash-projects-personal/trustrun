# MKA tasks (vendored)

The 10 public showcase tasks of Google DeepMind's Multimodal
Knowledge Agent benchmark (MKA, Nov 10, 2026), vendored from
Hugging Face dataset `google/multimodal-knowledge-agent`
(Apache 2.0), dataset revision
`46bce7ab8768f661750bd1016ec8cbdc517740b5`, fetched 2026-11-12.

`tasks.json` holds, per task: id, vertical, domain, role, goal,
prompt, input-file names, and the rubric criteria (description,
weight, grading target). Total: 10 tasks, 835 criteria.

Only `metadata.json` and `rubrics.json` are vendored (re-fetch with
`fetch_mka.py`, which asserts the 10-task / 835-criterion counts).
The input files themselves (images, CAD blueprints, rasters,
spreadsheets) are NOT vendored: they are load-bearing visual
artifacts the text-only pipeline cannot read, so the runner lists
them by name only and records them as unprocessed. The 200-task
full set stays private by design (anti-leakage) and is not here.
