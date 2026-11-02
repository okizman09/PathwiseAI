"""Tests for Catalog v3 Slice C7: Creator Usage Signals.

Tests verify:
1. Step feedback recording:
   - POST /workflows/{id}/steps/{step_id}/finish records step_feedback when feedback_result is provided.
   - POST /workflows/{id}/steps/{step_id}/feedback records or updates feedback.
2. Public directory threshold rule:
   - Tools with < 10 feedbacks show used_in_workflows_count = None on public cards.
   - Tools with >= 10 feedbacks show used_in_workflows_count = count.
   - Public responses NEVER leak individual feedback notes.
3. Admin metrics:
   - GET /admin/tools/metrics requires admin privileges.
   - Returns correct per-tool success rates, feedback breakdown (worked/partly/didnt), and workflow counts.
"""
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.models.profile import Profile
from app.models.step_feedback import StepFeedback
from app.models.tool import Tool
from app.models.workflow import Workflow as DBWorkflow
from app.models.workflow import WorkflowStep as DBWorkflowStep
from app.schemas.tool import ToolStatus
from tests.test_auth import generate_token


@pytest.fixture
def c7_test_data():
    db = SessionLocal()

    # Clean up prior test data
    db.query(StepFeedback).delete()
    db.query(DBWorkflowStep).delete()
    db.query(DBWorkflow).delete()
    db.query(Tool).filter(Tool.name.like("C7_Test_%")).delete()
    db.query(Profile).filter(Profile.id.in_(["c7-user-1", "c7-admin-1"])).delete()
    db.commit()

    now = datetime.now(UTC)

    # 1. Profiles
    user = Profile(
        id="c7-user-1",
        email="c7user@example.com",
        role="creator",
    )
    admin = Profile(
        id="c7-admin-1",
        email="c7admin@example.com",
        role="admin",
    )
    db.add_all([user, admin])

    # 2. Tools:
    # Tool A: 12 feedbacks (>=10, should show badge)
    tool_a = Tool(
        name="C7_Test_Popular_Tool",
        url="https://popular.example.com",
        status=ToolStatus.VERIFIED.value,
        domain="software",
        jobs=["write_code"],
        link_status="ok",
        pricing_model="freemium",
        has_free_tier=True,
        verified_at=now,
    )
    # Tool B: 5 feedbacks (<10, should NOT show badge)
    tool_b = Tool(
        name="C7_Test_Emerging_Tool",
        url="https://emerging.example.com",
        status=ToolStatus.VERIFIED.value,
        domain="software",
        jobs=["review_code"],
        link_status="ok",
        pricing_model="freemium",
        has_free_tier=True,
        verified_at=now,
    )
    db.add_all([tool_a, tool_b])
    db.commit()
    db.refresh(tool_a)
    db.refresh(tool_b)

    # 3. Workflow for user
    wf = DBWorkflow(
        user_id="c7-user-1",
        title="C7 Test Workflow",
        brief={
            "what_being_made": "Web App",
            "purpose": "A test app for creator workflow",
            "target_audience": "Developers",
            "budget_preference": "flexible",
        },
    )
    db.add(wf)
    db.commit()
    db.refresh(wf)

    step1 = DBWorkflowStep(
        workflow_id=wf.id,
        position=1,
        kind="tool",
        job="Write core app code",
        primary_tool_id=tool_a.id,
        status="pending",
    )
    db.add(step1)
    db.commit()
    db.refresh(step1)

    # Add feedbacks for Tool A: 10 worked, 2 partly = 12 total across multiple workflows
    for i in range(10):
        db.add(
            StepFeedback(
                step_id=step1.id,
                workflow_id=wf.id,
                user_id=f"c7-mock-user-{i}",
                tool_id=tool_a.id,
                result="worked",
                note=f"Secret private user note {i}",
            )
        )
    for i in range(2):
        db.add(
            StepFeedback(
                step_id=step1.id,
                workflow_id=wf.id,
                user_id=f"c7-user-partly-{i}",
                tool_id=tool_a.id,
                result="partly",
                note="Had slight trouble with auth",
            )
        )

    # Add feedbacks for Tool B: 4 worked, 1 didnt = 5 total
    for i in range(4):
        db.add(
            StepFeedback(
                step_id=step1.id,
                workflow_id=wf.id,
                user_id=f"c7-user-b-{i}",
                tool_id=tool_b.id,
                result="worked",
                note="Worked nicely",
            )
        )
    db.add(
        StepFeedback(
            step_id=step1.id,
            workflow_id=wf.id,
            user_id="c7-user-b-didnt",
            tool_id=tool_b.id,
            result="didnt",
            note="Did not work at all",
        )
    )
    db.commit()

    yield {
        "user": user,
        "admin": admin,
        "tool_a": tool_a,
        "tool_b": tool_b,
        "workflow": wf,
        "step": step1,
    }

    # Clean up
    db.query(StepFeedback).delete()
    db.query(DBWorkflowStep).delete()
    db.query(DBWorkflow).delete()
    db.query(Tool).filter(Tool.name.like("C7_Test_%")).delete()
    db.query(Profile).filter(Profile.id.in_(["c7-user-1", "c7-admin-1"])).delete()
    db.commit()
    db.close()


def test_public_tools_used_in_workflows_threshold(client: TestClient, c7_test_data):
    """Public directory shows used_in_workflows_count only when >= 10, never leaking notes."""
    res = client.get("/api/v1/tools")
    assert res.status_code == 200
    data = res.json()

    tool_a_data = next((t for t in data if t["id"] == c7_test_data["tool_a"].id), None)
    tool_b_data = next((t for t in data if t["id"] == c7_test_data["tool_b"].id), None)

    assert tool_a_data is not None
    assert tool_b_data is not None

    # Tool A has 12 entries (>= 10) -> count exposed
    assert tool_a_data["used_in_workflows_count"] == 12

    # Tool B has 5 entries (< 10) -> count is None
    assert tool_b_data["used_in_workflows_count"] is None

    # Never leaks feedback notes in public response
    res_str = res.text
    assert "Secret private user note" not in res_str
    assert "Had slight trouble with auth" not in res_str


def test_submit_step_feedback_endpoint(client: TestClient, c7_test_data):
    """Creators can submit and update step feedback directly."""
    user_token = generate_token(subject="c7-user-1", email="c7user@example.com")
    headers = {"Authorization": f"Bearer {user_token}"}

    wf = c7_test_data["workflow"]
    res = client.post(
        f"/api/v1/workflows/{wf.id}/steps/step-1/feedback",
        json={"result": "worked", "note": "Finished effortlessly with Cursor!"},
        headers=headers,
    )
    assert res.status_code == 200
    fb_data = res.json()
    assert fb_data["result"] == "worked"
    assert fb_data["note"] == "Finished effortlessly with Cursor!"
    assert fb_data["tool_id"] == c7_test_data["tool_a"].id

    # Update the feedback
    res_update = client.post(
        f"/api/v1/workflows/{wf.id}/steps/step-1/feedback",
        json={"result": "partly", "note": "Adjusted prompt slightly"},
        headers=headers,
    )
    assert res_update.status_code == 200
    assert res_update.json()["result"] == "partly"
    assert res_update.json()["note"] == "Adjusted prompt slightly"


def test_step_finish_with_feedback_result(client: TestClient, c7_test_data):
    """Calling step finish with feedback_result records StepFeedback."""
    user_token = generate_token(subject="c7-user-1", email="c7user@example.com")
    headers = {"Authorization": f"Bearer {user_token}"}

    wf = c7_test_data["workflow"]
    step = c7_test_data["step"]

    res = client.post(
        f"/api/v1/workflows/{wf.id}/steps/step-1/finish",
        json={
            "note": "Code generated cleanly",
            "feedback_result": "worked",
        },
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["step"]["status"] == "done"

    # Verify feedback was stored
    db = SessionLocal()
    fb = db.query(StepFeedback).filter_by(step_id=step.id, user_id="c7-user-1").first()
    assert fb is not None
    assert fb.result == "worked"
    assert fb.note == "Code generated cleanly"
    db.close()


def test_admin_metrics_endpoint(client: TestClient, c7_test_data):
    """Admin metrics endpoint calculates correct success rates and feedback totals."""
    # 1. Unauthenticated fails with 401
    res_unauth = client.get("/api/v1/admin/tools/metrics")
    assert res_unauth.status_code == 401

    # 2. Non-admin fails with 403
    user_token = generate_token(subject="c7-user-1", email="c7user@example.com")
    res_user = client.get(
        "/api/v1/admin/tools/metrics",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert res_user.status_code == 403

    # 3. Admin succeeds
    admin_token = generate_token(subject="c7-admin-1", email="c7admin@example.com")
    res = client.get(
        "/api/v1/admin/tools/metrics",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    metrics = res.json()

    m_a = next((m for m in metrics if m["tool_id"] == c7_test_data["tool_a"].id), None)
    m_b = next((m for m in metrics if m["tool_id"] == c7_test_data["tool_b"].id), None)

    assert m_a is not None
    assert m_a["total_feedbacks"] == 12
    assert m_a["worked_count"] == 10
    assert m_a["partly_count"] == 2
    assert m_a["didnt_count"] == 0
    # success_rate = (10 + 0.5 * 2) / 12 * 100 = 11 / 12 * 100 = 91.7%
    assert m_a["success_rate_percent"] == 91.7

    assert m_b is not None
    assert m_b["total_feedbacks"] == 5
    assert m_b["worked_count"] == 4
    assert m_b["partly_count"] == 0
    assert m_b["didnt_count"] == 1
    # success_rate = 4 / 5 * 100 = 80.0%
    assert m_b["success_rate_percent"] == 80.0

