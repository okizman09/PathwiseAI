from pydantic import BaseModel, Field

from app.schemas.brief import (
    InterviewAnswer,
    InterviewQuestionResponse,
    InterviewReadyResponse,
    InterviewResponse,
    ProductBrief,
)
from app.services.llm import generate_structured


class InterviewLLMDecision(BaseModel):
    is_ready: bool = Field(
        description="Set to True if the goal and answers provide sufficient clarity for the product brief, or if 5 turns have completed."
    )
    question: str | None = Field(
        default=None,
        description="The next targeted question to ask the user if is_ready is False. Ask only one question at a time.",
    )
    options: list[str] | None = Field(
        default_factory=list,
        description="3-4 helpful multiple choice chip options for the user to quickly select.",
    )
    brief: ProductBrief | None = Field(
        default=None,
        description="The synthesized product brief if is_ready is True.",
    )


async def conduct_interview(
    goal: str,
    answers: list[InterviewAnswer],
) -> InterviewResponse:
    """Run interview turn with the Meta model. Returns either the next question or finalized brief."""

    turns_count = len(answers)
    force_ready = turns_count >= 5

    system_instruction = (
        "You are Pathwise AI's Product Interviewer for creators, developers, and freelancers.\n"
        "Your mission is to gather context to create an actionable, accurate Product Brief across 9 creator domains.\n\n"
        "Creator Domains: software, builders, design, video, audio, writing, research, deploy_backend, freelance_ops.\n\n"
        "Rules:\n"
        "1. First, detect the primary creator domain(s) from the user's goal and store in brief.detected_domains.\n"
        "2. Ask domain-aware clarifying questions:\n"
        "   - video: video length, style, voiceover vs on-camera narration\n"
        "   - audio: genre, vocals or instrumental, stems/mixing\n"
        "   - software: language/stack, architecture, deployment target\n"
        "   - builders: app type (full-stack app, landing page, SaaS, internal tool, e-commerce)\n"
        "   - writing: target audience, channel/format (blog, email newsletter, technical docs, script, book)\n"
        "   - design: use case, brand guidelines (social graphics, logo/brand, UI mockup, slides)\n"
        "   - research: research scope, sources, output format (summary, report, knowledge base)\n"
        "   - deploy_backend: cloud host, database, authentication provider\n"
        "   - freelance_ops: operations need (invoicing, proposals, client scheduling, contracts)\n"
        "3. ALWAYS capture in the Product Brief (if not already known from the goal or answers):\n"
        "   - budget_preference: 'free_only' | 'low' | 'flexible'\n"
        "   - skill_level: 'beginner' | 'intermediate' | 'advanced'\n"
        "   - needs_commercial_use: 'yes' | 'no' | 'unknown'\n"
        "4. 0-5 QUESTION RULE: If the user's initial goal answers enough of these to proceed, skip redundant questions and return is_ready=True immediately. Maximum 5 total questions.\n"
        "5. Ask at most ONE question per turn. Keep questions concise and focused.\n"
        "6. Provide 3-4 quick-select chip options with each question.\n"
        "7. NEVER invent features. Use only what the user states or reasonable default assumptions based on the context.\n"
        + (
            "8. IMPORTANT: 5 questions have already been completed. You MUST set is_ready=True and produce the final Product Brief now."
            if force_ready
            else ""
        )
    )

    conversation_history = [f"Initial User Goal: {goal}"]
    for idx, item in enumerate(answers, 1):
        conversation_history.append(
            f"Question {idx}: {item.question}\nUser Answer: {item.answer}"
        )

    prompt = (
        "Review the conversation history and decide whether to ask the next clarifying question "
        "or finalize the Product Brief.\n\n"
        + "\n\n".join(conversation_history)
        + "\n\nProvide the response strictly conforming to the JSON schema."
    )

    decision = await generate_structured(
        system=system_instruction,
        user=prompt,
        schema=InterviewLLMDecision,
        temperature=0.3,
    )

    if decision.is_ready and decision.brief:
        return InterviewReadyResponse(type="ready", brief=decision.brief)

    if decision.question:
        return InterviewQuestionResponse(
            type="question",
            question=decision.question,
            options=decision.options or [],
            allow_custom_text=True,
        )

    if decision.brief:
        return InterviewReadyResponse(type="ready", brief=decision.brief)

    raise ValueError("LLM returned an invalid response without a question or product brief.")
