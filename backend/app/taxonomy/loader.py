"""Taxonomy loader and validator for Pathwise Catalog v3."""
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

TAXONOMY_FILE = Path(__file__).parent / "taxonomy.yaml"


@lru_cache(maxsize=1)
def load_taxonomy() -> dict[str, Any]:
    if not TAXONOMY_FILE.exists():
        raise FileNotFoundError(f"Taxonomy file not found at {TAXONOMY_FILE}")

    with open(TAXONOMY_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    domains_data = data.get("domains", {})
    if not domains_data:
        raise ValueError("Taxonomy file missing 'domains' definition.")

    # Validate each domain has label and jobs
    for d_slug, d_val in domains_data.items():
        if "label" not in d_val or "jobs" not in d_val:
            raise ValueError(f"Domain '{d_slug}' must define 'label' and 'jobs'.")

    return data


def get_taxonomy() -> dict[str, Any]:
    return load_taxonomy()


def get_valid_domains() -> list[str]:
    tax = get_taxonomy()
    return list(tax["domains"].keys())


def get_valid_jobs() -> list[str]:
    tax = get_taxonomy()
    jobs: list[str] = []
    for d_val in tax["domains"].values():
        jobs.extend(list(d_val["jobs"].keys()))
    return jobs


def get_jobs_for_domain(domain: str) -> list[str]:
    tax = get_taxonomy()
    if domain not in tax["domains"]:
        raise ValueError(f"Unknown domain: {domain}")
    return list(tax["domains"][domain]["jobs"].keys())


def get_domain_for_job(job: str) -> str | None:
    tax = get_taxonomy()
    for d_slug, d_val in tax["domains"].items():
        if job in d_val["jobs"]:
            return d_slug
    return None


def get_domain_label(domain: str) -> str:
    tax = get_taxonomy()
    if domain in tax["domains"]:
        return tax["domains"][domain]["label"]
    return domain.replace("_", " ").title()


def get_job_label(job: str) -> str:
    tax = get_taxonomy()
    for d_val in tax["domains"].values():
        if job in d_val["jobs"]:
            return d_val["jobs"][job]
    return job.replace("_", " ").capitalize()


def is_valid_domain(domain: str) -> bool:
    return domain in get_valid_domains()


def is_valid_job(job: str) -> bool:
    return job in get_valid_jobs()


def validate_domain(domain: str | None) -> str | None:
    if domain is None:
        return None
    valid = get_valid_domains()
    if domain not in valid:
        raise ValueError(f"Unknown domain '{domain}'. Must be one of: {', '.join(valid)}")
    return domain


def validate_jobs(jobs: list[str] | None) -> list[str]:
    if not jobs:
        return []
    valid = set(get_valid_jobs())
    invalid = [j for j in jobs if j not in valid]
    if invalid:
        raise ValueError(f"Unknown job slug(s): {', '.join(invalid)}. Allowed jobs: {', '.join(sorted(valid))}")
    return jobs


def get_taxonomy_payload() -> dict[str, Any]:
    """Return public API response format for GET /taxonomy."""
    tax = get_taxonomy()
    domains_list = []
    jobs_list = []
    domain_labels = {}
    job_labels = {}

    for d_slug, d_val in tax["domains"].items():
        domain_labels[d_slug] = d_val["label"]
        d_jobs = []
        for j_slug, j_label in d_val["jobs"].items():
            job_labels[j_slug] = j_label
            d_jobs.append(j_slug)
            jobs_list.append({
                "slug": j_slug,
                "label": j_label,
                "domain": d_slug,
            })
        domains_list.append({
            "slug": d_slug,
            "label": d_val["label"],
            "jobs": d_jobs,
        })

    return {
        "domains": domains_list,
        "jobs": jobs_list,
        "domain_labels": domain_labels,
        "job_labels": job_labels,
    }
