"""Tests for the data module. All deterministic, hand made inputs."""

import pytest

from trustrun.data import audit_dataset


def _recs(texts):
    return [{"text": t} for t in texts]


def test_clean_dataset_passes():
    texts = [
        "The quick brown fox jumps over the lazy dog near the riverbank.",
        "Quantum computers use qubits that exist in superposition states.",
        "Baking sourdough requires patience, flour, water, and salt.",
        "The harbor lighthouse guided ships through the foggy night.",
        "Machine translation struggles with idioms and cultural context.",
        "Coral reefs support a quarter of all marine species alive today.",
        "The old library smelled of paper dust and quiet afternoons.",
        "Satellites in low orbit circle the earth roughly every 90 minutes.",
        "My grandmother grew tomatoes bigger than softballs every summer.",
        "The violinist tuned her strings before the concert hall emptied.",
        "Desert nights drop below freezing despite the daytime heat.",
        "Ancient trade routes carried silk, spices, and ideas westward.",
    ]
    report = audit_dataset(_recs(texts))
    assert report["records"] == 12
    assert report["exact_duplicate_rows"] == 0
    assert report["near_duplicate_rows"] == 0
    assert report["metrics"]["exact_duplicates"]["verdict"] == "pass"
    assert report["metrics"]["near_duplicates"]["verdict"] == "pass"
    assert report["metrics"]["template_clusters"]["verdict"] == "pass"
    assert report["verdict"] == "pass"


def test_exact_duplicates_flagged():
    texts = ["Alpha beta gamma delta epsilon zeta eta theta."] * 2
    texts += [
        "A completely different sentence about oak trees and rain.",
        "Another unrelated line on the migration of arctic terns.",
        "Fresh wording here about bicycle repair and spare chains.",
        "One more unique entry concerning lighthouse keepers.",
        "Distinct text about the history of paper money in China.",
        "Unique words on deep sea vents and tube worms.",
        "A final separate note about alpine meadows in spring.",
        "Still unique content about glassblowing techniques.",
        "More distinct phrasing about urban beekeeping trends.",
        "Last unique line on the acoustics of concert halls.",
    ]
    report = audit_dataset(_recs(texts))
    assert report["records"] == 12
    assert report["exact_duplicate_rows"] == 1
    assert report["exact_duplicate_rate"] == pytest.approx(1 / 12)
    assert report["metrics"]["exact_duplicates"]["verdict"] == "review"
    assert report["verdict"] == "review"


def test_exact_duplicate_normalization():
    texts = ["  Hello   WORLD  ", "hello world", "hello  world"]
    texts += ["Unique filler sentence number %d about rivers." % i for i in range(9)]
    report = audit_dataset(_recs(texts))
    assert report["exact_duplicate_rows"] == 2


def test_near_duplicates_flagged():
    base = (
        "The research team spent three years collecting water samples "
        "from remote mountain lakes across the northern ranges, then "
        "analyzed mineral content in the university laboratory."
    )
    variant = base + " very recently indeed."
    texts = [base, variant]
    texts += ["Unique filler sentence number %d about deserts." % i for i in range(10)]
    report = audit_dataset(_recs(texts))
    assert report["near_duplicate_rows"] == 2
    assert report["near_duplicate_rate"] == pytest.approx(2 / 12)
    assert report["metrics"]["near_duplicates"]["verdict"] == "review"
    assert report["verdict"] == "review"


def test_near_duplicate_needs_shared_fivegram():
    texts = [
        "Zebra xylophone quantum waffle juggles seven purple moons.",
        "Totally different words with no overlap at all here now.",
    ]
    texts += ["Unique filler sentence number %d about forests." % i for i in range(10)]
    report = audit_dataset(_recs(texts))
    assert report["near_duplicate_rows"] == 0
    assert report["metrics"]["near_duplicates"]["verdict"] == "pass"


def test_template_clustering():
    texts = [
        "Write a summary of Apple",
        "Write a summary of Google",
        "Write a summary of Tesla",
        "Write a summary of Amazon",
        "Write a summary of Meta",
        "Explain how photosynthesis converts light into sugar.",
        "Describe the water cycle in three clear paragraphs.",
        "List five causes of the fall of the Roman Empire.",
        "What is the capital of Burkina Faso and why does it matter.",
        "Draft a polite email declining a meeting invitation.",
        "Compare electric cars with hybrid cars for city driving.",
        "Summarize the plot of a novel you have never read.",
    ]
    report = audit_dataset(_recs(texts))
    assert report["template_cluster_count"] == 8
    assert report["top_template_cluster_sizes"][0] == 5
    assert report["top1_template_share"] == pytest.approx(5 / 12)
    assert report["metrics"]["template_clusters"]["verdict"] == "review"
    assert report["metrics"]["exact_duplicates"]["verdict"] == "pass"
    assert report["verdict"] == "review"


def test_template_masking_merges_numbered_variants():
    texts = ["Summarize article 12 for me please now", "Summarize article 99 for me please now"]
    texts += [
        "The old mill wheel turned slowly in the autumn creek.",
        "Geese flew south in a ragged V over the cornfields.",
        "She kept her keys on a hook beside the front door.",
        "Thunder rolled across the valley long after the lightning.",
        "The baker dusted flour over the wooden countertop.",
        "Children chased fireflies along the garden fence.",
        "A red bicycle leaned against the brick schoolhouse.",
        "The tide left shells scattered on the wet sand.",
        "He repaired the fence with wire and stubborn patience.",
        "Morning fog hid the far shore of the lake.",
    ]
    report = audit_dataset(_recs(texts))
    assert report["top_template_cluster_sizes"][0] == 2


def test_tiny_input_is_unverified():
    report = audit_dataset(_recs(["one", "two", "three"]))
    assert report["verdict"] == "unverified"
    for metric in report["metrics"].values():
        assert metric["verdict"] == "unverified"


def test_empty_input_is_unverified():
    report = audit_dataset([])
    assert report["records"] == 0
    assert report["verdict"] == "unverified"


def test_determinism():
    texts = ["Write a summary of Apple", "Write a summary of Google"]
    texts += ["Unique filler sentence number %d about plains." % i for i in range(10)]
    first = audit_dataset(_recs(texts))
    second = audit_dataset(_recs(texts))
    assert first == second


def test_exact_dup_threshold_boundary():
    texts = ["Filler sentence number %d with distinct words here." % i for i in range(999)]
    texts.append("Filler sentence number 0 with distinct words here.")
    report = audit_dataset(_recs(texts))
    assert report["records"] == 1000
    assert report["exact_duplicate_rows"] == 1
    assert report["metrics"]["exact_duplicates"]["verdict"] == "review"
    texts2 = ["Filler sentence number %d with distinct words here." % i for i in range(1000)]
    texts2.append("Filler sentence number 0 with distinct words here.")
    report2 = audit_dataset(_recs(texts2))
    assert report2["metrics"]["exact_duplicates"]["verdict"] == "pass"


def test_bad_inputs_raise_typeerror():
    with pytest.raises(TypeError):
        audit_dataset("not a list")
    with pytest.raises(TypeError):
        audit_dataset([{"text": "ok"}, "not a dict"] + [{"text": "x%d" % i} for i in range(10)])
    with pytest.raises(TypeError):
        audit_dataset([{"no_text": "x"}] + [{"text": "y%d" % i} for i in range(10)])
    with pytest.raises(TypeError):
        audit_dataset([{"text": 123}] + [{"text": "y%d" % i} for i in range(10)])
