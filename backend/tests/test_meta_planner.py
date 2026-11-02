"""Tests for the Meta-aware planner (hackathon T6).

generate_workflow_plan runs with a fake LLM: Meta tool-context fields and
the invented model-ID post-check are covered without network calls.
"""
import pytest

from app.db import SessionLocal
from app.models.profile import Profile
from app.models.tool import Tool
from app.models.tool_gap import ToolGap
from app.models.workflow import Workflow as DBWorkflow
from app.models.workflow import WorkflowStep as DBWorkflowStep
from app.schemas.brief import ProductBrief
from app.services.plan import (
    JobPlanningItem,
    LLMJobsPlan,
    LLMStepSynthesis,
    LLMWorkflowSynthesis,
    _strip_unknown_model_ids,
    generate_workflow_plan,
)

META_ID = "muse-voice-transcribe-1.0"
FAKE_ID = "muse-fake-9.9"
META_NAME = "T6 Meta Transcriber"
PLAIN_NAME = "T6 Plain Transcriber"
USER_ID = "t6-user"


def _make_brief():
    return ProductBrief(
        what_being_made="Voice notes tool",
        purpose="Turn voice notes into orders",
        target_audience="Shop owners",
        constraints=[],
        must_haves=[],
        nice_to_haves=[],
        assumptions=[],
        skill_level="intermediate",
        budget_preference="flexible",
        needs_commercial_use="unknown",
        detected_domains=["audio"],
    )


@pytest.fixture
def seeded_db(client):
    """DB with one Meta and one plain verified tool plus a user; cleans up after."""
    db = SessionLocal()
    try:
        for n in (META_NAME, PLAIN_NAME):
            db.query(Tool).filter(Tool.name == n).delete()
        db.query(Profile).filter(Profile.id == USER_ID).delete()
        db.commit()
        db.add(Tool(
            name=META_NAME,
            url="https://t6-meta.example.com",
            status="verified",
            link_status="unknown",
            domain="audio",
            category="audio",
            jobs=["transcribe_audio"],
            ecosystem="meta",
            kind="runnable",
            model_id=META_ID,
            api_snippet="snippet",
            prompt_style={},
            pricing_model="paid",
        ))
        db.add(Tool(
            name=PLAIN_NAME,
            url="https://t6-plain.example.com",
            status="verified",
            link_status="unknown",
            domain="audio",
            category="audio",
            jobs=["transcribe_audio"],
            prompt_style={},
            pricing_model="freemium",
            has_free_tier=True,
        ))
        db.add(Profile(id=USER_ID, email="t6@test.com", role="user"))
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


def _fake_llm(calls, meta_tool_id, synthesis_prompt):
    async def fake_generate_structured(*, system, user, schema, temperature=0.2, max_output_tokens=None):
        calls.append({"system": system, "user": user, "schema": schema.__name__})
        if schema.__name__ == "LLMJobsPlan":
            return LLMJobsPlan(jobs=[JobPlanningItem(
                step_number=1,
                job="transcribe_audio",
                job_tags=[],
                input_types=["audio"],
                output_types=["text"],
                output_expected="Transcript",
            )])
        return LLMWorkflowSynthesis(title="T6 plan", steps=[LLMStepSynthesis(
            step_number=1,
            job="transcribe_audio",
            why_step="why",
            primary_tool_id=meta_tool_id,
            alternative_tool_ids=[],
            prompt=synthesis_prompt,
            output_expected="Transcript",
        )])
    return fake_generate_structured


@pytest.mark.asyncio
async def test_synthesis_context_carries_meta_fields_and_rules(seeded_db, monkeypatch):
    """Meta shortlist entries include ecosystem/kind/model_id; rules reach the prompt."""
    calls = []
    meta_id = seeded_db.query(Tool).filter(Tool.name == META_NAME).one().id
    monkeypatch.setattr(
        "app.services.plan.generate_structured",
        _fake_llm(calls, meta_id, "Transcribe the audio."),
    )
    user = seeded_db.query(Profile).filter(Profile.id == USER_ID).one()

    result = await generate_workflow_plan(seeded_db, user, _make_brief())

    assert len(result.steps) == 1
    synthesis = next(c for c in calls if c["schema"] == "LLMWorkflowSynthesis")
    assert '"ecosystem": "meta"' in synthesis["user"]
    assert '"kind": "runnable"' in synthesis["user"]
    assert f'"model_id": "{META_ID}"' in synthesis["user"]
    assert synthesis["user"].count('"model_id"') == 1  # plain tool has no such key
    assert "Never invent a model ID" in synthesis["system"]
    assert "with the expected output format" in synthesis["system"]


@pytest.mark.asyncio
async def test_invented_model_ids_stripped_and_flagged(seeded_db, monkeypatch):
    """Catalog IDs survive; invented muse-/sam- IDs are stripped with a warning."""
    calls = []
    meta_id = seeded_db.query(Tool).filter(Tool.name == META_NAME).one().id
    monkeypatch.setattr(
        "app.services.plan.generate_structured",
        _fake_llm(calls, meta_id, f"Use {META_ID}, never {FAKE_ID} or sam-bogus-2."),
    )
    user = seeded_db.query(Profile).filter(Profile.id == USER_ID).one()

    result = await generate_workflow_plan(seeded_db, user, _make_brief())

    prompt = result.steps[0].prompt
    assert META_ID in prompt
    assert FAKE_ID not in prompt
    assert "sam-bogus-2" not in prompt
    assert any("Removed unrecognized model reference(s)" in w for w in result.steps[0].warnings)


def test_strip_unknown_model_ids_unit():
    """Punctuation preserved, known IDs kept, unknown stripped."""
    cleaned, removed = _strip_unknown_model_ids(
        "Use muse-keep-1.0, not muse-drop-2. (Also sam-drop.)",
        {"muse-keep-1.0"},
    )
    assert cleaned == "Use muse-keep-1.0, not . (Also .)"
    assert sorted(removed) == ["muse-drop-2", "sam-drop"]
    assert _strip_unknown_model_ids("", {"a"}) == ("", [])


@pytest.mark.asyncio
async def test_plan_persists_steps_content(seeded_db, monkeypatch):
    """A steps-type synthesized step round-trips through the response and DB."""
    from app.services.plan import generate_workflow_plan

    meta_id = seeded_db.query(Tool).filter(Tool.name == META_NAME).one().id
    calls = []

    async def fake_generate_structured(*, system, user, schema, temperature=0.2, max_output_tokens=None):
        calls.append({"system": system, "schema": schema.__name__})
        if schema.__name__ == "LLMJobsPlan":
            return LLMJobsPlan(jobs=[JobPlanningItem(
                step_number=1, job="transcribe_audio", job_tags=[],
                input_types=["audio"], output_types=["text"], output_expected="Transcript")])
        return LLMWorkflowSynthesis(title="T plan", steps=[LLMStepSynthesis(
            step_number=1, job="transcribe_audio", why_step="why",
            primary_tool_id=meta_id, alternative_tool_ids=[],
            prompt="", content_type="steps",
            action_steps=["Install the CLI.", "Run transcribe."],
            output_expected="Transcript")])

    monkeypatch.setattr("app.services.plan.generate_structured", fake_generate_structured)
    user = seeded_db.query(Profile).filter(Profile.id == USER_ID).one()

    from app.schemas.brief import ProductBrief
    brief = ProductBrief(
        what_being_made="m", purpose="p", target_audience="a", constraints=[],
        must_haves=[], nice_to_haves=[], assumptions=[], skill_level="intermediate",
        budget_preference="flexible", needs_commercial_use="unknown",
        detected_domains=["audio"],
    )
    result = await generate_workflow_plan(seeded_db, user, brief)

    synthesis = next(c for c in calls if c["schema"] == "LLMWorkflowSynthesis")
    assert "CONTENT FORMAT" in synthesis["system"]
    assert result.steps[0].content_type == "steps"
    assert result.steps[0].action_steps == ["Install the CLI.", "Run transcribe."]
    row = seeded_db.query(DBWorkflowStep).filter(
        DBWorkflowStep.workflow_id == result.id).one()
    assert row.content_type == "steps"
    assert row.action_steps == ["Install the CLI.", "Run transcribe."]


@pytest.mark.asyncio
async def test_regenerate_preserves_steps_format(monkeypatch):
    """Regenerate on a steps-type step revises the steps, keeping the format."""
    from app.schemas.tool import PromptStyleSchema
    from app.schemas.workflow import ToolShortCard, WorkflowStep
    from app.services.prompts import StepPromptRewriteResponse, regenerate_step_prompt

    step = WorkflowStep(
        step_id="step-1", step_number=1, job="deploy_backend", why_step="w",
        primary_tool=ToolShortCard(
            id=1, name="T", go_path="/go/1",
            prompt_style=PromptStyleSchema(technique="t", format="f", rules=[], example="ex")),
        prompt="", content_type="steps", action_steps=["Old step."],
        output_expected="o")

    async def fake_llm(*, system, user, schema, temperature=0.2, max_output_tokens=None):
        assert "SETUP STEPS" in system
        assert "Old step." in user
        return StepPromptRewriteResponse(
            prompt="", content_type="steps",
            action_steps=["New step 1.", "New step 2."], technique="t")

    monkeypatch.setattr("app.services.prompts.generate_structured", fake_llm)
    updated = await regenerate_step_prompt(step, feedback="clearer")

    assert updated.content_type == "steps"
    assert updated.action_steps == ["New step 1.", "New step 2."]
    assert updated.prompt == ""
