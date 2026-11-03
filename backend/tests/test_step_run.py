"""Tests for live step runs (T9): ownership, quota, eligibility, persistence."""

import pytest

from app.core.config import settings
from app.core.errors import UserFacingError
from app.db import SessionLocal
from app.models.profile import Profile
from app.models.step_run import StepRun
from app.models.tool import Tool
from app.models.usage import UsageDaily
from app.models.workflow import Workflow, WorkflowStep
from app.services.llm import TextResult
from tests.test_auth import generate_token


def _reset_step_run_usage() -> None:
    """Clear user_A's step_run quota (usage rows persist across tests in one DB)."""
    db = SessionLocal()
    db.query(UsageDaily).filter_by(user_id="user_A", kind="step_run").delete()
    db.commit()
    db.close()


@pytest.fixture
def mock_run_setup(client, monkeypatch):
    db = SessionLocal()
    u1 = Profile(id="user_A", email="a@test.com", role="user")
    u2 = Profile(id="user_B", email="b@test.com", role="user")

    runnable = Tool(
        id=11, name="Spark", url="https://meta.ai", status="verified", link_status="ok",
        category="software", ecosystem="meta", kind="runnable",
        model_id="muse-spark-1.3", jobs=["draft_content"],
    )
    plain = Tool(
        id=12, name="Plain Tool", url="https://plain.com", status="verified",
        link_status="ok", category="design", jobs=["edit_image"],
    )

    db.merge(u1)
    db.merge(u2)
    db.merge(runnable)
    db.merge(plain)
    db.commit()

    wf = Workflow(id=11, user_id="user_A", title="Run WF", brief={
        "what_being_made": "A test",
        "purpose": "Testing",
        "target_audience": "Devs",
        "constraints": [],
        "must_haves": [],
        "nice_to_haves": [],
        "assumptions": [],
        "skill_level": "beginner",
        "budget_preference": "flexible",
    })
    db.merge(wf)
    db.commit()

    db.merge(WorkflowStep(workflow_id=11, position=1, job="draft", why_step="r",
                          primary_tool_id=11, alternative_tool_ids=[], job_tags=[],
                          input_types=[], output_types=[], prompt="Summarize: hello",
                          content_type="prompt"))
    db.merge(WorkflowStep(workflow_id=11, position=2, job="draw", why_step="r",
                          primary_tool_id=12, alternative_tool_ids=[], job_tags=[],
                          input_types=[], output_types=[], prompt="Draw: cat",
                          content_type="prompt"))
    db.merge(WorkflowStep(workflow_id=11, position=3, job="setup", why_step="r",
                          primary_tool_id=11, alternative_tool_ids=[], job_tags=[],
                          input_types=[], output_types=[], prompt=None,
                          content_type="steps", action_steps=["Do the thing"]))
    db.commit()
    db.close()

    monkeypatch.setattr(settings, "RUN_STEPS_PER_DAY", 10)
    settings.SUPABASE_JWT_SECRET = "testsecretthatisatleast32characterslong"
    token_a = generate_token(subject="user_A", email="a@test.com", email_verified=True)
    token_b = generate_token(subject="user_B", email="b@test.com", email_verified=True)

    return {"token_a": token_a, "token_b": token_b}


def _fake_ok(seen):
    async def _run(*, system, user, model, max_output_tokens, timeout):
        seen.update({"model": model, "timeout": timeout, "user": user,
                     "max_output_tokens": max_output_tokens})
        return TextResult(text="OUT", model=model, input_tokens=5, output_tokens=7)

    return _run


@pytest.mark.asyncio
async def test_another_users_step_run_returns_404(client, mock_run_setup):
    headers = {"Authorization": f"Bearer {mock_run_setup['token_b']}"}
    res = client.post("/api/v1/workflows/11/steps/step-1/run", json={}, headers=headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_non_runnable_tool_rejected(client, mock_run_setup):
    headers = {"Authorization": f"Bearer {mock_run_setup['token_a']}"}
    res = client.post("/api/v1/workflows/11/steps/step-2/run", json={}, headers=headers)
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_steps_content_rejected(client, mock_run_setup):
    headers = {"Authorization": f"Bearer {mock_run_setup['token_a']}"}
    res = client.post("/api/v1/workflows/11/steps/step-3/run", json={}, headers=headers)
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_successful_run_saved_equals_returned(client, mock_run_setup, monkeypatch):
    headers = {"Authorization": f"Bearer {mock_run_setup['token_a']}"}
    seen: dict = {}
    monkeypatch.setattr("app.services.run.generate_text", _fake_ok(seen))

    res = client.post("/api/v1/workflows/11/steps/step-1/run", json={}, headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["output_text"] == "OUT"
    assert body["model_id"] == "muse-spark-1.3"
    assert body["status"] == "completed"
    assert seen["model"] == "muse-spark-1.3"
    assert seen["timeout"] == float(settings.RUN_TIMEOUT_SECONDS)
    assert seen["user"] == "Summarize: hello"

    db = SessionLocal()
    row = db.query(StepRun).filter_by(id=body["run_id"]).first()
    assert row is not None
    assert row.output_text == body["output_text"]
    assert row.model_id == body["model_id"]
    assert row.input_tokens == 5 and row.output_tokens == 7
    assert row.status == "completed"
    db.close()


@pytest.mark.asyncio
async def test_prompt_override_used(client, mock_run_setup, monkeypatch):
    headers = {"Authorization": f"Bearer {mock_run_setup['token_a']}"}
    seen: dict = {}
    monkeypatch.setattr("app.services.run.generate_text", _fake_ok(seen))

    res = client.post(
        "/api/v1/workflows/11/steps/step-1/run",
        json={"prompt": "Custom prompt"},
        headers=headers,
    )
    assert res.status_code == 200
    assert seen["user"] == "Custom prompt"


@pytest.mark.asyncio
async def test_quota_exceeded_returns_429(client, mock_run_setup, monkeypatch):
    headers = {"Authorization": f"Bearer {mock_run_setup['token_a']}"}
    _reset_step_run_usage()
    monkeypatch.setattr(settings, "RUN_STEPS_PER_DAY", 1)
    monkeypatch.setattr("app.services.run.generate_text", _fake_ok({}))

    first = client.post("/api/v1/workflows/11/steps/step-1/run", json={}, headers=headers)
    assert first.status_code == 200
    second = client.post("/api/v1/workflows/11/steps/step-1/run", json={}, headers=headers)
    assert second.status_code == 429


@pytest.mark.asyncio
async def test_provider_failure_persists_failed_and_refunds(client, mock_run_setup, monkeypatch):
    headers = {"Authorization": f"Bearer {mock_run_setup['token_a']}"}
    _reset_step_run_usage()
    monkeypatch.setattr(settings, "RUN_STEPS_PER_DAY", 1)

    async def _fail(**kwargs):
        raise UserFacingError("The AI service is unavailable. Please try again.",
                              status_code=502, code="llm_unavailable")

    monkeypatch.setattr("app.services.run.generate_text", _fail)
    failed = client.post("/api/v1/workflows/11/steps/step-1/run", json={}, headers=headers)
    assert failed.status_code == 502

    db = SessionLocal()
    row = db.query(StepRun).order_by(StepRun.id.desc()).first()
    assert row.status == "failed"
    assert row.error_code == "llm_unavailable"
    db.close()

    monkeypatch.setattr("app.services.run.generate_text", _fake_ok({}))
    retry = client.post("/api/v1/workflows/11/steps/step-1/run", json={}, headers=headers)
    assert retry.status_code == 200
