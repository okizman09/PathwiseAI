"""Script to populate missing taglines and best_for descriptions for tools in the database."""

import logging

from app.db import SessionLocal
from app.models.tool import Tool
from app.taxonomy.loader import get_taxonomy_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("populate_tool_taglines")

VERB_MAP = {
    "write": "writing",
    "debug": "debugging",
    "review": "reviewing",
    "plan": "planning",
    "build": "building",
    "automate": "automating",
    "design": "designing",
    "generate": "generating",
    "edit": "editing",
    "repurpose": "repurposing",
    "transcribe": "transcribing",
    "clean": "cleaning",
    "mix": "mixing",
    "master": "mastering",
    "compose": "composing",
    "isolate": "isolating",
    "draft": "drafting",
    "rewrite": "rewriting",
    "summarize": "summarizing",
    "optimize": "optimizing",
    "search": "searching",
    "extract": "extracting",
    "synthesize": "synthesizing",
    "fact_check": "fact-checking",
    "deploy": "deploying",
    "host": "hosting",
    "scale": "scaling",
    "manage": "managing",
    "track": "tracking",
    "schedule": "scheduling",
    "invoice": "invoicing",
    "make": "creating",
    "add": "adding",
    "set": "setting",
}

JOB_CUSTOM_PHRASES = {
    "write_code": "writing code",
    "debug_code": "debugging code",
    "review_code": "reviewing code",
    "write_tests": "writing tests",
    "write_docs": "writing documentation",
    "manage_code": "managing repositories and code",
    "plan_app": "planning architecture and applications",
    "build_website": "building websites",
    "build_web_app": "building web apps",
    "build_mobile_app": "building mobile apps",
    "build_landing_page": "building landing pages",
    "automate_workflow": "automating workflows",
    "design_ui": "designing user interfaces",
    "generate_image": "generating images",
    "edit_image": "editing images",
    "design_brand": "brand and asset design",
    "make_social_graphics": "creating social media graphics",
    "make_presentation": "creating presentations",
    "generate_video_clips": "generating video clips",
    "edit_video": "video editing",
    "add_captions": "generating subtitles and captions",
    "repurpose_clips": "repurposing video clips",
    "make_avatar_video": "creating AI avatar videos",
    "generate_music": "generating AI music",
    "generate_voiceover": "voice synthesis and voiceovers",
    "edit_audio": "audio editing and mastering",
    "transcribe_audio": "audio transcription",
    "clean_audio": "audio cleaning and enhancement",
    "isolate_tracks": "stem and track isolation",
    "draft_content": "drafting content and copy",
    "rewrite_content": "content rewriting and tone adjustment",
    "summarize_content": "summarizing long-form content",
    "optimize_seo": "SEO optimization",
    "search_papers": "searching scientific literature",
    "extract_data": "data extraction and research synthesis",
    "fact_check": "fact-checking and verification",
    "host_frontend": "hosting frontend applications",
    "host_backend": "hosting backend services",
    "set_up_database": "managing and scaling databases",
    "set_up_analytics": "setting up web analytics",
    "manage_invoicing": "invoicing and client payments",
    "track_time": "time tracking and productivity",
    "contract_management": "contract and proposal management",
}


def generate_tagline(tool_name: str, domain: str | None, jobs: list[str] | None, job_labels: dict[str, str]) -> str:
    valid_jobs = jobs or []
    if valid_jobs:
        phrases = []
        for j in valid_jobs[:3]:
            if j in JOB_CUSTOM_PHRASES:
                phrases.append(JOB_CUSTOM_PHRASES[j])
            else:
                raw = job_labels.get(j, j.replace("_", " "))
                words = raw.strip().split()
                first = words[0].lower()
                ing = VERB_MAP.get(first, first + "ing")
                phrases.append(" ".join([ing] + words[1:]))

        if len(phrases) == 1:
            actions = phrases[0]
        elif len(phrases) == 2:
            actions = f"{phrases[0]} and {phrases[1]}"
        else:
            actions = f"{phrases[0]}, {phrases[1]}, and {phrases[2]}"

        tagline = f"AI tool for {actions}."
        if len(tagline) > 88:
            # If too long, use top 2 jobs or concise format
            if len(phrases) >= 2:
                tagline = f"AI tool for {phrases[0]} and {phrases[1]}."
            if len(tagline) > 88:
                tagline = f"AI tool for {phrases[0]}."
        if len(tagline) > 88:
            tagline = tagline[:85].rstrip() + "..."
        return tagline

    if domain:
        return f"AI tool tailored for {domain.replace('_', ' ')}."[:88]
    return "Verified AI tool for creative workflows."


def run():
    tax = get_taxonomy_payload()
    job_labels = tax.get("job_labels", {})

    db = SessionLocal()
    try:
        tools = db.query(Tool).all()
        logger.info("Found %d total tools in database", len(tools))
        updated_count = 0

        for tool in tools:
            needs_update = False
            if not tool.tagline or tool.tagline.strip() == "" or tool.tagline == "Verified AI tool for creative workflows.":
                tool.tagline = generate_tagline(tool.name, tool.domain, tool.jobs, job_labels)
                needs_update = True

            if not tool.best_for or tool.best_for.strip() == "":
                domain_str = tool.domain.replace("_", " ") if tool.domain else "creators"
                tool.best_for = f"Creators and teams working in {domain_str} seeking verified AI workflows."
                needs_update = True

            if needs_update:
                updated_count += 1

        db.commit()
        logger.info("Successfully updated %d tools with informative taglines and best_for descriptions!", updated_count)
    finally:
        db.close()


if __name__ == "__main__":
    run()
