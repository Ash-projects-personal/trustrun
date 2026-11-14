"""Tests for trustrun.think_spend."""

import pytest

from trustrun.think_spend import (
    ACCURACY_FLOOR,
    HIDDEN_SHARE_BAR,
    VERDICT_BLOCK,
    VERDICT_PASS,
    VERDICT_REVIEW,
    call_cost,
    format_summary,
    hidden_cost,
    hidden_share,
    score_call_site,
    score_campaign,
)


def _call(site="summarize", visible=200, reasoning=1800, correct=True,
          difficulty="simple", effort="high", price=1.0):
    return {
        "call_site": site,
        "visible_tokens": visible,
        "reasoning_tokens": reasoning,
        "correct": correct,
        "difficulty": difficulty,
        "effort": effort,
        "price_per_million_output": price,
    }


def _site_calls(count=4, **kwargs):
    return [_call(**kwargs) for _ in range(count)]


# hidden_share

def test_hidden_share_basic():
    assert hidden_share(_call()) == pytest.approx(0.9)


def test_hidden_share_zero_reasoning():
    assert hidden_share(_call(reasoning=0)) == 0.0


def test_hidden_share_zero_total_is_none():
    assert hidden_share(_call(visible=0, reasoning=0)) is None


def test_hidden_share_devto_glm_median():
    # dev.to Oct 11 2026: GLM 5.3 Flash default, 2,483 billed,
    # 2,256 hidden, so 227 visible.
    assert hidden_share(_call(visible=227, reasoning=2256)) == pytest.approx(
        0.9086, abs=0.0001
    )


def test_hidden_share_devto_deepseek_median():
    # dev.to Oct 11 2026: DeepSeek V4.1 Flash default, 1,525
    # billed, 1,293 hidden, so 232 visible.
    assert hidden_share(_call(visible=232, reasoning=1293)) == pytest.approx(
        0.8479, abs=0.0001
    )


def test_hidden_share_rejects_negative_tokens():
    with pytest.raises(ValueError):
        hidden_share(_call(reasoning=-1))


def test_hidden_share_rejects_bad_effort():
    with pytest.raises(ValueError):
        hidden_share(_call(effort="turbo"))


def test_hidden_share_rejects_missing_key():
    call = _call()
    del call["correct"]
    with pytest.raises(ValueError):
        hidden_share(call)


def test_hidden_share_rejects_non_dict():
    with pytest.raises(ValueError):
        hidden_share("not a call")


def test_hidden_share_rejects_bad_difficulty():
    with pytest.raises(ValueError):
        hidden_share(_call(difficulty="medium"))


def test_hidden_share_rejects_zero_price():
    with pytest.raises(ValueError):
        hidden_share(_call(price=0))


# call_cost / hidden_cost

def test_call_cost_basic():
    assert call_cost(_call()) == pytest.approx(0.002)


def test_call_cost_priced():
    assert call_cost(_call(visible=1000, reasoning=4000, price=2.0)) == pytest.approx(
        0.01
    )


def test_call_cost_zero():
    assert call_cost(_call(visible=0, reasoning=0)) == 0.0


def test_hidden_cost_basic():
    assert hidden_cost(_call()) == pytest.approx(0.0018)


def test_hidden_cost_zero_reasoning():
    assert hidden_cost(_call(reasoning=0)) == 0.0


# score_call_site

def test_site_score_waste_site():
    site = score_call_site(_site_calls())
    assert site["call_site"] == "summarize"
    assert site["calls"] == 4
    assert site["accuracy"] == 1.0
    assert site["mean_hidden_share"] == pytest.approx(0.9)
    assert site["total_cost"] == pytest.approx(0.008)
    assert site["hidden_cost"] == pytest.approx(0.0072)
    assert site["cost_per_correct"] == pytest.approx(0.002)
    assert site["mean_reasoning_tokens"] == pytest.approx(1800.0)
    assert site["recommendation"]["recommendation"] == "downgrade_to_low"


def test_site_score_low_effort_clean():
    site = score_call_site(_site_calls(reasoning=0, effort="low"))
    assert site["mean_hidden_share"] == 0.0
    assert site["total_cost"] == pytest.approx(0.0008)
    assert site["cost_per_correct"] == pytest.approx(0.0002)
    assert site["recommendation"]["recommendation"] == "keep"
    assert site["recommendation"]["reason"] == "hidden share below bar"


def test_site_score_hard_keeps_effort():
    site = score_call_site(
        _site_calls(2, site="plan", visible=500, reasoning=4500,
                    difficulty="hard")
    )
    assert site["mean_hidden_share"] == pytest.approx(0.9)
    assert site["total_cost"] == pytest.approx(0.01)
    assert site["recommendation"]["recommendation"] == "keep"
    assert site["recommendation"]["reason"] == "hard tasks earn their thinking"


def test_site_score_accuracy_below_floor_keeps_effort():
    calls = [
        _call(correct=True),
        _call(correct=True),
        _call(correct=False),
        _call(correct=False),
    ]
    site = score_call_site(calls)
    assert site["accuracy"] == 0.5
    assert site["accuracy"] < ACCURACY_FLOOR
    assert site["recommendation"]["recommendation"] == "keep"
    assert site["recommendation"]["reason"] == "accuracy below floor; do not cut effort"


def test_site_score_share_below_bar_keeps_effort():
    site = score_call_site(_site_calls(visible=1800, reasoning=200))
    assert site["mean_hidden_share"] == pytest.approx(0.1)
    assert site["mean_hidden_share"] < HIDDEN_SHARE_BAR
    assert site["recommendation"]["recommendation"] == "keep"


def test_site_score_no_correct_cost_per_correct_none():
    site = score_call_site(_site_calls(2, correct=False))
    assert site["cost_per_correct"] is None
    assert site["accuracy"] == 0.0


def test_site_score_already_low_effort_keeps():
    site = score_call_site(_site_calls(effort="low"))
    assert site["recommendation"]["recommendation"] == "keep"
    assert site["recommendation"]["reason"] == "already at low effort"


def test_site_score_rejects_mixed_sites():
    with pytest.raises(ValueError):
        score_call_site([_call(site="a"), _call(site="b")])


def test_site_score_rejects_mixed_difficulty():
    with pytest.raises(ValueError):
        score_call_site(
            [_call(difficulty="simple"), _call(difficulty="hard")]
        )


def test_site_score_rejects_empty():
    with pytest.raises(ValueError):
        score_call_site([])


# score_campaign

def _main_fixture():
    calls = []
    calls += _site_calls(4, site="summarize")
    calls += _site_calls(4, site="extract", reasoning=0, effort="low")
    calls += _site_calls(
        2, site="plan", visible=500, reasoning=4500, difficulty="hard"
    )
    return calls


def test_campaign_review_main_fixture():
    campaign = score_campaign(_main_fixture())
    assert campaign["calls"] == 10
    assert campaign["accuracy"] == 1.0
    assert campaign["total_cost"] == pytest.approx(0.0188)
    assert campaign["hidden_cost"] == pytest.approx(0.0162)
    assert campaign["hidden_cost_share"] == pytest.approx(0.8617, abs=0.0001)
    assert campaign["cost_per_correct"] == pytest.approx(0.00188)
    assert campaign["waste_sites"] == ["summarize"]
    assert campaign["waste_hidden_cost"] == pytest.approx(0.0072)
    assert campaign["waste_share"] == pytest.approx(0.3830, abs=0.0001)
    assert campaign["tuning"]["saving_share"] is None
    assert campaign["tuning"]["tuning_wins"] is False
    assert campaign["verdict"] == VERDICT_REVIEW


def test_campaign_pass_no_waste():
    calls = _site_calls(4, site="extract", reasoning=0, effort="low")
    calls += _site_calls(
        2, site="plan", visible=500, reasoning=4500, difficulty="hard"
    )
    campaign = score_campaign(calls)
    assert campaign["waste_share"] == 0.0
    assert campaign["waste_sites"] == []
    assert campaign["verdict"] == VERDICT_PASS


def test_campaign_block_waste_dominates():
    calls = _site_calls(4, site="summarize")
    calls += [_call(site="extract", reasoning=0, effort="low")]
    campaign = score_campaign(calls)
    assert campaign["waste_share"] == pytest.approx(0.8780, abs=0.0001)
    assert campaign["verdict"] == VERDICT_BLOCK


def test_campaign_tuning_wins_with_baseline():
    calls = _main_fixture()
    calls += _site_calls(
        2, site="summarize", reasoning=100, effort="low"
    )
    campaign = score_campaign(calls)
    assert campaign["total_cost"] == pytest.approx(0.0194)
    assert campaign["waste_share"] == pytest.approx(0.3814, abs=0.0001)
    assert campaign["tuning"]["saving"] == pytest.approx(0.0068)
    assert campaign["tuning"]["saving_share"] == pytest.approx(
        0.7234, abs=0.0001
    )
    assert campaign["tuning"]["accuracy_delta"] == pytest.approx(0.0)
    assert campaign["tuning"]["tuning_wins"] is True
    assert campaign["verdict"] == VERDICT_REVIEW


def test_campaign_tuning_loses_when_accuracy_drops():
    # 19 correct high-effort calls keep the site above the floor
    # even with one wrong low-effort call: accuracy 19/20 = 0.95,
    # so the site stays waste and the accuracy delta is measured.
    calls = _site_calls(19, site="summarize")
    calls += [_call(site="summarize", reasoning=100, effort="low",
                    correct=False)]
    calls += _site_calls(4, site="extract", reasoning=0, effort="low")
    calls += _site_calls(
        2, site="plan", visible=500, reasoning=4500, difficulty="hard"
    )
    campaign = score_campaign(calls)
    assert campaign["tuning"]["accuracy_delta"] == pytest.approx(-1.0)
    assert campaign["tuning"]["tuning_wins"] is False


def test_campaign_empty_is_review():
    campaign = score_campaign([])
    assert campaign["verdict"] == VERDICT_REVIEW
    assert campaign["waste_share"] is None
    assert campaign["calls"] == 0


def test_campaign_zero_tokens_is_review():
    calls = [_call(visible=0, reasoning=0), _call(visible=0, reasoning=0)]
    campaign = score_campaign(calls)
    assert campaign["total_cost"] == 0.0
    assert campaign["verdict"] == VERDICT_REVIEW


def test_campaign_hard_sites_never_waste():
    calls = _site_calls(
        4, site="plan", visible=500, reasoning=4500, difficulty="hard"
    )
    campaign = score_campaign(calls)
    assert campaign["waste_sites"] == []
    assert campaign["verdict"] == VERDICT_PASS


def test_campaign_rejects_bad_floor():
    with pytest.raises(ValueError):
        score_campaign(_main_fixture(), accuracy_floor=1.5)


# format_summary

def test_format_summary_review():
    summary = format_summary(score_campaign(_main_fixture()))
    assert summary == (
        "ThinkSpend: 10 calls, 3 sites, cost $0.0188, hidden share "
        "0.8617, waste share 0.3830, tuning unproven, verdict REVIEW"
    )


def test_format_summary_pass():
    calls = _site_calls(4, site="extract", reasoning=0, effort="low")
    summary = format_summary(score_campaign(calls))
    assert summary == (
        "ThinkSpend: 4 calls, 1 sites, cost $0.0008, hidden share "
        "0.0000, waste share 0.0000, tuning unproven, verdict PASS"
    )
