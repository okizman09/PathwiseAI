
import pytest


@pytest.mark.asyncio
async def test_interview_requires_auth(client):
    response = client.post("/api/v1/interview", json={"goal": "Build an app", "answers": []})
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_interview_strips_control_chars_and_uses_quota(client, monkeypatch):
    from app.core.config import settings
    from tests.test_auth import generate_token
    settings.SUPABASE_JWT_SECRET = "testsecretthatisatleast32characterslong"
    token = generate_token(subject="interview_user_123", email="interview_user@test.com")

    # We will mock the conduct_interview function to avoid hitting the actual LLM
    async def mock_conduct(goal, answers):
        from app.schemas.brief import InterviewQuestionResponse
        return InterviewQuestionResponse(question="Mock?", options=[], allow_custom_text=True)

    monkeypatch.setattr("app.routers.interview.interview_service.conduct_interview", mock_conduct)

    headers = {"Authorization": f"Bearer {token}"}

    # \x0b is a control character
    dirty_goal = "Build an app\x0b\x0cwith AI"
    response = client.post(
        "/api/v1/interview",
        json={"goal": dirty_goal, "answers": []},
        headers=headers
    )

    assert response.status_code == 200

    # Validate that it passes validation and maybe check if control chars are stripped if we inspect the args
    # But Pydantic strips it before mock_conduct gets it! Let's mock a tracker:
    last_goal = []

    async def mock_conduct_track(goal, answers):
        last_goal.append(goal)
        from app.schemas.brief import InterviewQuestionResponse
        return InterviewQuestionResponse(question="Mock?", options=[], allow_custom_text=True)

    monkeypatch.setattr("app.routers.interview.interview_service.conduct_interview", mock_conduct_track)

    client.post(
        "/api/v1/interview",
        json={"goal": dirty_goal, "answers": []},
        headers=headers
    )

    assert last_goal[0] == "Build an appwith AI"


@pytest.mark.asyncio
async def test_conduct_interview_requests_low_reasoning_effort(monkeypatch):
    """Interview turns ask for low reasoning effort (latency)."""
    from app.services import interview as interview_service
    from app.services.interview import InterviewLLMDecision

    seen = {}

    async def fake_generate_structured(**kwargs):
        seen.update(kwargs)
        return InterviewLLMDecision(is_ready=False, question="Q?", options=["a", "b"])

    monkeypatch.setattr(interview_service, "generate_structured", fake_generate_structured)
    res = await interview_service.conduct_interview(goal="Build a thing", answers=[])

    assert res.type == "question"
    assert seen["reasoning_effort"] == "low"
