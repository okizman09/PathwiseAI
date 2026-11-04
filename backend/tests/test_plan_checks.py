"""Offline pytest for the planner smoke checks (hackathon T7).

Applies the same checks as scripts/smoke_plan.py to a fake LLM plus targeted
unit cases, so CI stays offline.
"""
import pytest

from app.db import SessionLocal
from app.models.profile import Profile
from app.models.tool import Tool
from app.models.tool_gap import ToolGap
from app.models.workflow import Workflow as DBWorkflow
from app.models.workflow import WorkflowStep as DBWorkflowStep
from app.schemas.brief import ProductBrief
from app.schemas.workflow import ToolShortCard, WorkflowResponse, WorkflowStep
from app.services.plan import (
    JobPlanningItem,
    LLMJobsPlan,
    LLMStepSynthesis,
    LLMWorkflowSynthesis,
    generate_workflow_plan,
)
from app.services.planner.checks import check_plan

META_ID = "muse-voice-transcribe-1.0"
META_NAME = "T7 Meta Transcriber"
PLAIN_NAME = "T7 Plain Transcriber"
USER_ID = "t7-user"


def _card(tool_id, name, ecosystem=None):
    return ToolShortCard(id=tool_id, name=name, go_path=f"/go/{tool_id}",
                         ecosystem=ecosystem)


def _step(n, job, tool, prompt="Do the thing."):
    return WorkflowStep(step_id=f"step-{n}", step_number=n, job=job,
                        why_step="why", primary_tool=tool, prompt=prompt,
                        output_expected="Out")


def _brief():
    return ProductBrief(
        what_being_made="Voice notes tool", purpose="Turn voice notes into orders",
        target_audience="Shop owners", constraints=[], must_haves=[],
        nice_to_haves=[], assumptions=[], skill_level="intermediate",
        budget_preference="flexible", needs_commercial_use="unknown",
        detected_domains=["audio"],
    )


@pytest.fixture
def seeded_db(client):
    db = SessionLocal()
    try:
        for n in (META_NAME, PLAIN_NAME):
            db.query(Tool).filter(Tool.name == n).delete()
        db.query(Profile).filter(Profile.id == USER_ID).delete()
        db.commit()
        db.add(Tool(
            name=META_NAME, url="https://t7-meta.example.com", status="verified",
            link_status="unknown", domain="audio", category="audio",
            jobs=["transcribe_audio"], ecosystem="meta", kind="runnable",
            model_id=META_ID, prompt_style={}, pricing_model="paid",
        ))
        db.add(Tool(
            name=PLAIN_NAME, url="https://t7-plain.example.com", status="verified",
            link_status="unknown", domain="audio", category="audio",
            jobs=["transcribe_audio"], prompt_style={}, pricing_model="freemium",
            has_free_tier=True,
        ))
        db.add(Profile(id=USER_ID, email="t7@test.com", role="user"))
        db.commit()
        yield db
    finally:
        wf_ids = [w.id for w in db.query(DBWorkflow).filter(DBWorkflow.user_id == USER_ID).all()]
        if wf_ids:
            db.query(DBWorkflowStep).filter(DBWorkflowStep.workflow_id.in_(wf_ids)).delete(synchronize_session=False)
            db.query(ToolGap).filter(ToolGap.workflow_id.in_(wf_ids)).delete(synchronize_session=False)
            db.query(DBWorkflow).filter(DBWorkflow.user_id == USER_ID).delete(synchronize_session=False)
        db.query(Tool).filter(Tool.name.in_([META_NAME, PLAIN_NAME])).delete(synchronize_session=False)
        db.query(Profile).filter(Profile.id == USER_ID).delete()
        db.commit()
        db.close()


@pytest.mark.asyncio
async def test_checks_pass_on_good_fake_plan(seeded_db, monkeypatch):
    """End-to-end with a fake LLM: a good plan passes all checks incl. extras."""
    meta_id = seeded_db.query(Tool).filter(Tool.name == META_NAME).one().id

    async def fake_generate_structured(
        *, system, user, schema, temperature=0.2, max_output_tokens=None, reasoning_effort=None
    ):
        if schema.__name__ == "LLMJobsPlan":
            return LLMJobsPlan(jobs=[JobPlanningItem(
                step_number=1, job="transcribe_audio", job_tags=[],
                input_types=["audio"], output_types=["text"], output_expected="Transcript")])
        return LLMWorkflowSynthesis(title="T7 plan", steps=[LLMStepSynthesis(
            step_number=1, job="transcribe_audio", why_step="why",
            primary_tool_id=meta_id, alternative_tool_ids=[],
            prompt=f"Transcribe with {META_ID}.", output_expected="Transcript")])

    monkeypatch.setattr("app.services.plan.generate_structured", fake_generate_structured)
    user = seeded_db.query(Profile).filter(Profile.id == USER_ID).one()

    plan = await generate_workflow_plan(seeded_db, user, _brief())
    known_models = {r[0] for r in seeded_db.query(Tool.model_id).filter(Tool.model_id.isnot(None)).all()}
    known_tools = {r[0] for r in seeded_db.query(Tool.id).all()}

    assert check_plan(plan, known_model_ids=known_models, known_tool_ids=known_tools,
                      require_transcribe_step=True, require_meta_card=True) == []


def _response(steps):
    return WorkflowResponse.model_construct(id=1, title="t", steps=steps, created_at="now")


def test_check_rejects_step_count():
    assert any("1-6" in f for f in check_plan(
        _response([]), known_model_ids=set(), known_tool_ids=set()))
    many = [WorkflowStep.model_construct(step_id=f"s{i}", step_number=i, job=f"j{i}",
                                         kind="tool", primary_tool=_card(i, f"t{i}"),
                                         prompt="p") for i in range(1, 8)]
    assert any("1-6" in f for f in check_plan(
        _response(many), known_model_ids=set(), known_tool_ids=set(range(1, 8))))


def test_check_rejects_missing_tool_and_empty_prompt():
    gap = WorkflowStep(step_id="step-1", step_number=1, job="x", why_step="w",
                       kind="no_tool", primary_tool=None, prompt=None,
                       output_expected="o")
    failures = check_plan(_response([gap]), known_model_ids=set(), known_tool_ids=set())
    assert any("no catalog tool" in f for f in failures)
    assert any("empty prompt" in f for f in failures)

    ghost = _step(1, "x", _card(999, "ghost"), prompt="  ")
    failures = check_plan(_response([ghost]), known_model_ids=set(), known_tool_ids={1})
    assert any("no catalog tool" in f for f in failures)
    assert any("empty prompt" in f for f in failures)


def test_check_rejects_duplicate_jobs():
    steps = [_step(1, "same_job", _card(1, "a")), _step(2, "same_job", _card(2, "b"))]
    failures = check_plan(_response(steps), known_model_ids=set(), known_tool_ids={1, 2})
    assert any("duplicate" in f for f in failures)


def test_check_rejects_unknown_model_ids_only():
    step = _step(1, "x", _card(1, "a"), prompt=f"Use {META_ID} not muse-bogus-1.")
    failures = check_plan(_response([step]), known_model_ids={META_ID}, known_tool_ids={1})
    assert len(failures) == 1 and "muse-bogus-1" in failures[0]


def test_check_extras():
    step = _step(1, "other_job", _card(1, "a"))
    failures = check_plan(_response([step]), known_model_ids=set(), known_tool_ids={1},
                          require_transcribe_step=True, require_meta_card=True)
    assert any("transcribe_audio" in f for f in failures)
    assert any("Meta card" in f for f in failures)


def test_check_steps_content():
    good = _step(1, "deploy_backend", _card(1, "a"), prompt="")
    good.content_type = "steps"
    good.action_steps = ["Run npm run deploy."]
    assert check_plan(_response([good]), known_model_ids=set(),
                      known_tool_ids={1}) == []

    bad = _step(1, "deploy_backend", _card(1, "a"), prompt="")
    bad.content_type = "steps"
    bad.action_steps = []
    failures = check_plan(_response([bad]), known_model_ids=set(), known_tool_ids={1})
    assert any("action_steps" in f for f in failures)


def _fake_plan_with_step(monkeypatch, job, primary_tool_id, prompt, content_type,
                         action_steps):
    async def fake_generate_structured(
        *, system, user, schema, temperature=0.2, max_output_tokens=None, reasoning_effort=None
    ):
        if schema.__name__ == "LLMJobsPlan":
            return LLMJobsPlan(jobs=[JobPlanningItem(
                step_number=1, job=job, job_tags=[],
                input_types=["audio"], output_types=["text"], output_expected="Transcript")])
        return LLMWorkflowSynthesis(title="T7 norm", steps=[LLMStepSynthesis(
            step_number=1, job=job, why_step="why",
            primary_tool_id=primary_tool_id, alternative_tool_ids=[],
            prompt=prompt, content_type=content_type, action_steps=action_steps,
            output_expected="Transcript")])

    monkeypatch.setattr("app.services.plan.generate_structured", fake_generate_structured)


def _known_ids(db):
    models = {r[0] for r in db.query(Tool.model_id).filter(Tool.model_id.isnot(None)).all()}
    tools = {r[0] for r in db.query(Tool.id).all()}
    return models, tools


@pytest.mark.asyncio
async def test_steps_tag_with_only_prompt_coerces_to_prompt(seeded_db, monkeypatch):
    """Regression: a 'steps'-tagged synthesis holding only a prompt must come
    back as a prompt step, otherwise a runnable step silently loses Run."""
    meta_id = seeded_db.query(Tool).filter(Tool.name == META_NAME).one().id
    _fake_plan_with_step(monkeypatch, "transcribe_audio", meta_id,
                         f"Transcribe with {META_ID}.", "steps", [])
    user = seeded_db.query(Profile).filter(Profile.id == USER_ID).one()

    plan = await generate_workflow_plan(seeded_db, user, _brief())

    assert plan.steps[0].content_type == "prompt"
    models, tools = _known_ids(seeded_db)
    assert check_plan(plan, known_model_ids=models, known_tool_ids=tools) == []


@pytest.mark.asyncio
async def test_prompt_tag_with_only_actions_coerces_to_steps(seeded_db, monkeypatch):
    """Symmetric case: a 'prompt'-tagged synthesis holding only setup actions
    must come back as a steps step instead of an empty prompt block."""
    meta_id = seeded_db.query(Tool).filter(Tool.name == META_NAME).one().id
    _fake_plan_with_step(monkeypatch, "transcribe_audio", meta_id,
                         "  ", "prompt", ["Run the transcription job."])
    user = seeded_db.query(Profile).filter(Profile.id == USER_ID).one()

    plan = await generate_workflow_plan(seeded_db, user, _brief())

    assert plan.steps[0].content_type == "steps"
    models, tools = _known_ids(seeded_db)
    assert check_plan(plan, known_model_ids=models, known_tool_ids=tools) == []
