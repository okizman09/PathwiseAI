"""Tests for the F0 feature flags (default off).

With FEATURE_LIVE_RUN off the run endpoint 404s and no step is marked
runnable; with FEATURE_META_SHOWCASE off the public tools list, the
ecosystem filter, and the planner shortlist all hide Meta tools.
"""
import pytest

from app.core.config import Settings, settings
from app.db import SessionLocal
from app.models.profile import Profile
from app.models.step_run import StepRun
from app.models.tool import Tool
from app.models.tool_gap import ToolGap
from app.models.workflow import Workflow, WorkflowStep
from app.schemas.brief import ProductBrief
from app.services.plan import (
    JobPlanningItem,
    LLMJobsPlan,
    LLMStepSynthesis,
    LLMWorkflowSynthesis,
    generate_workflow_plan,
)
from tests.test_auth import generate_token

USER_ID = "f0-user"
WF_ID = 9101
META_NAME = "F0 Meta Transcriber"
PLAIN_NAME = "F0 Plain Transcriber"


def _brief_dict():
    return {
        "what_being_made": "A test",
        "purpose": "Testing",
        "target_audience": "Devs",
        "constraints": [],
        "must_haves": [],
        "nice_to_haves": [],
        "assumptions": [],
        "skill_level": "beginner",
        "budget_preference": "flexible",
    }


@pytest.fixture
def flag_setup(client, monkeypatch):
    """One Meta + one plain verified tool, a user, and a workflow whose step
    points at the Meta tool. Both flags forced off."""
    db = SessionLocal()
    for n in (META_NAME, PLAIN_NAME):
        db.query(Tool).filter(Tool.name == n).delete()
    db.query(WorkflowStep).filter(WorkflowStep.workflow_id == WF_ID).delete(
        synchronize_session=False
    )
    db.query(Workflow).filter(Workflow.id == WF_ID).delete()
    db.query(Profile).filter(Profile.id == USER_ID).delete()
    db.commit()

    db.add(Profile(id=USER_ID, email="f0@test.com", role="user"))
    db.add(
        Tool(
            name=META_NAME,
            url="https://f0-meta.example.com",
            status="verified",
            link_status="ok",
            domain="audio",
            category="audio",
            jobs=["transcribe_audio"],
            ecosystem="meta",
            kind="runnable",
            model_id="f0-model-1",
            prompt_style={},
            pricing_model="paid",
        )
    )
    db.add(
        Tool(
            name=PLAIN_NAME,
            url="https://f0-plain.example.com",
            status="verified",
            link_status="ok",
            domain="audio",
            category="audio",
            jobs=["transcribe_audio"],
            prompt_style={},
            pricing_model="freemium",
            has_free_tier=True,
        )
    )
    db.commit()
    meta_id = db.query(Tool).filter(Tool.name == META_NAME).one().id
    plain_id = db.query(Tool).filter(Tool.name == PLAIN_NAME).one().id

    db.merge(Workflow(id=WF_ID, user_id=USER_ID, title="F0 WF", brief=_brief_dict()))
    db.commit()
    db.merge(
        WorkflowStep(
            workflow_id=WF_ID,
            position=1,
            job="transcribe",
            why_step="r",
            primary_tool_id=meta_id,
            alternative_tool_ids=[],
            job_tags=[],
            input_types=[],
            output_types=[],
            prompt="Transcribe this.",
            content_type="prompt",
        )
    )
    db.commit()
    db.close()

    monkeypatch.setattr(settings, "FEATURE_LIVE_RUN", False)
    monkeypatch.setattr(settings, "FEATURE_META_SHOWCASE", False)
    monkeypatch.setattr(
        settings, "SUPABASE_JWT_SECRET", "testsecretthatisatleast32characterslong"
    )
    token = generate_token(subject=USER_ID, email="f0@test.com", email_verified=True)
    yield {"token": token, "meta_id": meta_id, "plain_id": plain_id}

    db = SessionLocal()
    db.query(WorkflowStep).filter(WorkflowStep.workflow_id == WF_ID).delete(
        synchronize_session=False
    )
    db.query(Workflow).filter(Workflow.id == WF_ID).delete()
    db.query(Tool).filter(Tool.name.in_([META_NAME, PLAIN_NAME])).delete(
        synchronize_session=False
    )
    db.query(Profile).filter(Profile.id == USER_ID).delete()
    db.commit()
    db.close()


def test_feature_flags_default_off():
    """Code defaults are off (checked on the field, not the environment)."""
    assert Settings.model_fields["FEATURE_LIVE_RUN"].default is False
    assert Settings.model_fields["FEATURE_META_SHOWCASE"].default is False


@pytest.mark.asyncio
async def test_run_endpoint_returns_404_when_flag_off(client, flag_setup):
    headers = {"Authorization": f"Bearer {flag_setup['token']}"}
    db = SessionLocal()
    runs_before = db.query(StepRun).count()
    db.close()

    res = client.post(
        f"/api/v1/workflows/{WF_ID}/steps/step-1/run", json={}, headers=headers
    )

    assert res.status_code == 404
    db = SessionLocal()
    assert db.query(StepRun).count() == runs_before
    db.close()


@pytest.mark.asyncio
async def test_can_run_false_when_flag_off(client, flag_setup):
    """GET hydration goes through the same choke point as generation."""
    headers = {"Authorization": f"Bearer {flag_setup['token']}"}
    res = client.get(f"/api/v1/workflows/{WF_ID}", headers=headers)

    assert res.status_code == 200
    steps = res.json()["steps"]
    assert steps, "expected the seeded step"
    assert all(s["can_run"] is False for s in steps)


@pytest.mark.asyncio
async def test_tools_list_excludes_meta_when_flag_off(client, flag_setup):
    res = client.get("/api/v1/tools")

    assert res.status_code == 200
    names = [t["name"] for t in res.json()]
    assert PLAIN_NAME in names
    assert META_NAME not in names
    assert all(t.get("ecosystem") != "meta" for t in res.json())


@pytest.mark.asyncio
async def test_ecosystem_meta_filter_returns_empty_when_flag_off(client, flag_setup):
    res = client.get("/api/v1/tools", params={"ecosystem": "meta"})

    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_planner_shortlist_excludes_meta_when_flag_off(
    client, flag_setup, monkeypatch
):
    """End-to-end with a fake LLM: the synthesis context the planner sends
    contains no Meta tool when the showcase is off."""
    calls = []
    plain_id = flag_setup["plain_id"]

    async def fake_generate_structured(
        *, system, user, schema, temperature=0.2, max_output_tokens=None,
        reasoning_effort=None,
    ):
        calls.append({"system": system, "user": user, "schema": schema.__name__})
        if schema.__name__ == "LLMJobsPlan":
            return LLMJobsPlan(jobs=[JobPlanningItem(
                step_number=1, job="transcribe_audio", job_tags=[],
                input_types=["audio"], output_types=["text"],
                output_expected="Transcript",
            )])
        return LLMWorkflowSynthesis(title="F0 plan", steps=[LLMStepSynthesis(
            step_number=1, job="transcribe_audio", why_step="why",
            primary_tool_id=plain_id, alternative_tool_ids=[],
            prompt="Transcribe the audio.", output_expected="Transcript",
        )])

    monkeypatch.setattr(
        "app.services.plan.generate_structured", fake_generate_structured
    )
    db = SessionLocal()
    user = db.query(Profile).filter(Profile.id == USER_ID).one()
    brief = ProductBrief(
        **_brief_dict(),
        needs_commercial_use="unknown",
        detected_domains=["audio"],
    )

    result = await generate_workflow_plan(db, user, brief)

    synthesis = next(c for c in calls if c["schema"] == "LLMWorkflowSynthesis")
    assert '"ecosystem": "meta"' not in synthesis["user"]
    assert "f0-model-1" not in synthesis["user"]
    assert result.steps[0].primary_tool.name == PLAIN_NAME

    # Cleanup the generated workflow rows (tools/user are removed by flag_setup
    # only for its own seeds; the planner-created workflow needs its own pass).
    wf_ids = [
        w.id
        for w in db.query(Workflow).filter(Workflow.user_id == USER_ID).all()
        if w.id != WF_ID
    ]
    if wf_ids:
        db.query(WorkflowStep).filter(WorkflowStep.workflow_id.in_(wf_ids)).delete(
            synchronize_session=False
        )
        db.query(ToolGap).filter(ToolGap.workflow_id.in_(wf_ids)).delete(
            synchronize_session=False
        )
        db.query(Workflow).filter(Workflow.id.in_(wf_ids)).delete(
            synchronize_session=False
        )
        db.commit()
    db.close()
