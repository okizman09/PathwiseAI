"""Tests for Catalog v3 Slice C5: Interview and Planner for Any Creator.

Tests verify:
1. Budget filtering (hard rule): 'free_only' strictly excludes paid-only tools.
2. Commercial use rule:
   - 'free_only' + 'needs_commercial_use: yes' strictly excludes tools where commercial_use_on_free is False.
   - Non-free_only + 'needs_commercial_use: yes' keeps tool but attaches commercial warning.
3. Stale pricing rule:
   - Tools with pricing_checked_at older than 60 days receive -3 penalty and a freshness warning.
4. Pick bonus and skill fit:
   - is_pick=True adds +10 points.
   - skill_level matching adds +5 points.
5. Cost summary calculation:
   - 100% free workflow produces mode='free', estimated_monthly_usd=0.
   - Workflow with paid tools produces mode='may_cost' with estimated_monthly_usd.
6. Step free_tier_note and warnings:
   - Steps contain populated free_tier_note and propagated warnings.
7. Empty shortlist fallback:
   - When no tool matches under free_only, step kind is 'no_tool' with standard catalog message.
"""
from datetime import UTC, datetime, timedelta

import pytest

from app.models.tool import Tool
from app.schemas.brief import ProductBrief
from app.schemas.workflow import ToolShortCard, WorkflowStep
from app.services.plan import JobPlanningItem, compute_cost_summary, compute_free_tier_note
from app.services.planner.scoring import score_single_tool, shortlist_and_score


@pytest.fixture
def base_brief():
    return ProductBrief(
        what_being_made="YouTube Video Series",
        purpose="Educational tech tutorials",
        target_audience="Developers and students",
        constraints=[],
        must_haves=[],
        nice_to_haves=[],
        assumptions=[],
        skill_level="intermediate",
        budget_preference="flexible",
        needs_commercial_use="unknown",
        detected_domains=["video", "audio"],
    )


@pytest.fixture
def video_job():
    return JobPlanningItem(
        step_number=1,
        job="Edit video clips and timeline",
        job_tags=["edit_video"],
        input_types=["video"],
        output_types=["video"],
        output_expected="Exported MP4 cut",
    )


def test_free_only_hard_rule_excludes_paid_only_tool(base_brief, video_job):
    """free_only budget strictly excludes tools with no verified free tier."""
    base_brief.budget_preference = "free_only"

    paid_tool = Tool(
        id=1,
        name="Paid Video Studio",
        status="verified",
        link_status="ok",
        jobs=["edit_video"],
        domain="video",
        pricing_model="paid",
        has_free_tier=False,
        starting_price_monthly_usd=30.0,
    )

    free_tool = Tool(
        id=2,
        name="Free Cut Editor",
        status="verified",
        link_status="ok",
        jobs=["edit_video"],
        domain="video",
        pricing_model="freemium",
        has_free_tier=True,
        free_tier_summary="10 free exports/month",
    )

    candidates = shortlist_and_score([paid_tool, free_tool], video_job, [], base_brief)
    assert len(candidates) == 1
    assert candidates[0].id == 2
    assert candidates[0].name == "Free Cut Editor"


def test_commercial_use_under_free_only_strictly_excludes_non_commercial(base_brief, video_job):
    """free_only + needs_commercial_use='yes' excludes tools where commercial_use_on_free=False."""
    base_brief.budget_preference = "free_only"
    base_brief.needs_commercial_use = "yes"

    personal_free_tool = Tool(
        id=1,
        name="Personal Use Only Editor",
        status="verified",
        link_status="ok",
        jobs=["edit_video"],
        domain="video",
        pricing_model="freemium",
        has_free_tier=True,
        commercial_use_on_free=False,
    )

    commercial_free_tool = Tool(
        id=2,
        name="Commercial Friendly Editor",
        status="verified",
        link_status="ok",
        jobs=["edit_video"],
        domain="video",
        pricing_model="freemium",
        has_free_tier=True,
        commercial_use_on_free=True,
    )

    candidates = shortlist_and_score([personal_free_tool, commercial_free_tool], video_job, [], base_brief)
    assert len(candidates) == 1
    assert candidates[0].id == 2
    assert candidates[0].name == "Commercial Friendly Editor"


def test_commercial_use_with_flexible_budget_attaches_warning(base_brief, video_job):
    """needs_commercial_use='yes' with non-free budget keeps tool but attaches warning."""
    base_brief.budget_preference = "flexible"
    base_brief.needs_commercial_use = "yes"

    personal_free_tool = Tool(
        id=1,
        name="Personal Use Freemium Tool",
        status="verified",
        link_status="ok",
        jobs=["edit_video"],
        domain="video",
        pricing_model="freemium",
        has_free_tier=True,
        commercial_use_on_free=False,
        starting_price_monthly_usd=15.0,
    )

    scored = score_single_tool(personal_free_tool, video_job, [], base_brief)
    assert scored is not None
    score, warnings = scored
    assert any("Commercial use requires a paid license" in w for w in warnings)


def test_stale_pricing_applies_penalty_and_warning(base_brief, video_job):
    """pricing_checked_at older than 60 days loses 3 points and gets pricing warning."""
    now = datetime.now(UTC)
    stale_date = now - timedelta(days=90)
    fresh_date = now - timedelta(days=10)

    stale_tool = Tool(
        id=1,
        name="Stale Tool",
        status="verified",
        link_status="ok",
        jobs=["edit_video"],
        domain="video",
        pricing_model="freemium",
        has_free_tier=True,
        pricing_checked_at=stale_date,
    )

    fresh_tool = Tool(
        id=2,
        name="Fresh Tool",
        status="verified",
        link_status="ok",
        jobs=["edit_video"],
        domain="video",
        pricing_model="freemium",
        has_free_tier=True,
        pricing_checked_at=fresh_date,
    )

    stale_scored = score_single_tool(stale_tool, video_job, [], base_brief, now=now)
    fresh_scored = score_single_tool(fresh_tool, video_job, [], base_brief, now=now)

    assert stale_scored is not None and fresh_scored is not None
    stale_score, stale_warnings = stale_scored
    fresh_score, fresh_warnings = fresh_scored
    # Stale has penalty of 3 points
    assert stale_score == fresh_score - 3
    assert any("pricing may have changed" in w for w in stale_warnings)
    assert not any("pricing may have changed" in w for w in fresh_warnings)


def test_pick_bonus_and_skill_fit(base_brief, video_job):
    """is_pick grants +10 pts; skill fit grants +5 pts."""
    base_brief.skill_level = "beginner"

    regular_tool = Tool(
        id=1,
        name="Standard Editor",
        status="verified",
        link_status="ok",
        jobs=["edit_video"],
        domain="video",
        is_pick=False,
        skill_level="intermediate",
        pricing_model="freemium",
        has_free_tier=True,
    )

    pick_beginner_tool = Tool(
        id=2,
        name="Pick Beginner Editor",
        status="verified",
        link_status="ok",
        jobs=["edit_video"],
        domain="video",
        is_pick=True,
        skill_level="beginner",
        pricing_model="freemium",
        has_free_tier=True,
    )

    reg_scored = score_single_tool(regular_tool, video_job, [], base_brief)
    pick_scored = score_single_tool(pick_beginner_tool, video_job, [], base_brief)

    assert reg_scored is not None and pick_scored is not None
    reg_score, _ = reg_scored
    pick_score, _ = pick_scored
    # pick (+10) + skill fit (+5) = +15 difference
    assert pick_score == reg_score + 15


def test_compute_cost_summary_all_free(base_brief):
    """All tools free produces mode='free' and 0 USD estimate."""
    t1 = ToolShortCard(id=1, name="T1", url="https://t1.com", go_path="/api/v1/tools/1/go", pricing_model="free", has_free_tier=True, starting_price_monthly_usd=0)
    t2 = ToolShortCard(id=2, name="T2", url="https://t2.com", go_path="/api/v1/tools/2/go", pricing_model="freemium", has_free_tier=True, starting_price_monthly_usd=20)

    step1 = WorkflowStep(step_id="step-1", step_number=1, job="Job 1", why_step="Why 1", primary_tool=t1, output_expected="Out 1")
    step2 = WorkflowStep(step_id="step-2", step_number=2, job="Job 2", why_step="Why 2", primary_tool=t2, output_expected="Out 2")

    base_brief.budget_preference = "free_only"
    summary = compute_cost_summary([step1, step2], base_brief)
    assert summary.mode == "free"
    assert summary.estimated_monthly_usd == 0
    assert "free tier or are open source" in summary.notes[0].lower()


def test_compute_cost_summary_with_paid(base_brief):
    """Paid tools result in mode='may_cost' and estimated starting sum."""
    t1 = ToolShortCard(id=1, name="T1", url="https://t1.com", go_path="/api/v1/tools/1/go", pricing_model="paid", has_free_tier=False, starting_price_monthly_usd=25.0)
    t2 = ToolShortCard(id=2, name="T2", url="https://t2.com", go_path="/api/v1/tools/2/go", pricing_model="freemium", has_free_tier=True, starting_price_monthly_usd=15.0)

    step1 = WorkflowStep(step_id="step-1", step_number=1, job="Job 1", why_step="Why 1", primary_tool=t1, output_expected="Out 1")
    step2 = WorkflowStep(step_id="step-2", step_number=2, job="Job 2", why_step="Why 2", primary_tool=t2, output_expected="Out 2")

    base_brief.budget_preference = "flexible"
    summary = compute_cost_summary([step1, step2], base_brief)
    assert summary.mode == "may_cost"
    assert summary.estimated_monthly_usd == 25.0
    assert any("T1" in n for n in summary.notes)


def test_compute_free_tier_note(base_brief):
    """compute_free_tier_note correctly formats summary and limits."""
    t_summary_only = Tool(
        name="ToolA",
        pricing_model="freemium",
        has_free_tier=True,
        free_tier_summary="Free tier includes 3 exports per day.",
        credit_card_required=False,
        commercial_use_on_free=True,
    )
    note_a, warnings_a = compute_free_tier_note(t_summary_only, base_brief)
    assert "Free tier includes 3 exports per day." in note_a
    assert "No credit card required." in note_a
    assert "Commercial use permitted." in note_a

    t_paid = Tool(name="ToolC", pricing_model="paid", has_free_tier=False)
    note_c, warnings_c = compute_free_tier_note(t_paid, base_brief)
    assert "Paid tool" in note_c
    assert "No free tier" in note_c


def test_empty_shortlist_under_free_only(base_brief, video_job):
    """When only paid tools exist for a job and user is free_only, shortlist is empty."""
    base_brief.budget_preference = "free_only"
    paid_tool = Tool(
        id=99,
        name="Super Expensive Editor",
        status="verified",
        link_status="ok",
        jobs=["edit_video"],
        domain="video",
        pricing_model="paid",
        has_free_tier=False,
    )
    candidates = shortlist_and_score([paid_tool], video_job, [], base_brief)
    assert len(candidates) == 0
