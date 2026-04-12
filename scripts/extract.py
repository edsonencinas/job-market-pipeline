"""
scripts/extract.py
──────────────────
Pull raw job listings from:
  • Adzuna API (paid, free tier available)
  • RemoteOK  API (free, no key needed)

Output: data/raw/jobs_YYYY-MM-DD.json
"""

import json
import logging
import os
import time
from datetime import date
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from typing import List, Dict  # Add this import at the top of your file

load_dotenv()
log = logging.getLogger(__name__)

RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ── API Config ─────────────────────────────────────────────────
ADZUNA_APP_ID  = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")
ADZUNA_BASE    = "https://api.adzuna.com/v1/api/jobs"

REMOTEOK_BASE  = "https://remoteok.com/api"

# Keywords that narrow results to tech/data roles
SEARCH_TERMS = [
    "data engineer",
    "python developer",
    "data analyst",
    "machine learning engineer",
    "backend developer",
]


# ─────────────────────────────────────────────────────────────
# Adzuna
# ─────────────────────────────────────────────────────────────
def _fetch_adzuna(term: str, country: str = "us", pages: int = 3) -> List[Dict]:
    """Fetch up to `pages` pages of Adzuna results for `term`."""
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        log.warning("Adzuna credentials missing — skipping Adzuna source")
        return []

    results: List[Dict] = []
    for page in range(1, pages + 1):
        url = (
            f"{ADZUNA_BASE}/{country}/search/{page}"
            f"?app_id={ADZUNA_APP_ID}&app_key={ADZUNA_APP_KEY}"
            f"&results_per_page=50&what={term.replace(' ', '+')}"
            "&content-type=application/json"
        )
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            jobs = resp.json().get("results", [])
            for job in jobs:
                results.append({
                    "source":       "adzuna",
                    "id":           str(job.get("id")),
                    "title":        job.get("title", ""),
                    "company":      job.get("company", {}).get("display_name", ""),
                    "location":     job.get("location", {}).get("display_name", ""),
                    "salary_min":   job.get("salary_min"),
                    "salary_max":   job.get("salary_max"),
                    "description":  job.get("description", ""),
                    "url":          job.get("redirect_url", ""),
                    "date_posted":  job.get("created", ""),
                    "search_term":  term,
                })
            log.debug(f"  Adzuna page {page}: {len(jobs)} jobs")
            time.sleep(0.5)
        except requests.RequestException as exc:
            log.warning(f"  Adzuna request failed (term={term}, page={page}): {exc}")

    return results


# ─────────────────────────────────────────────────────────────
# RemoteOK
# ─────────────────────────────────────────────────────────────
def _fetch_remoteok() -> List[dict]:
    """Fetch all current listings from RemoteOK's public API."""
    try:
        resp = requests.get(
            REMOTEOK_BASE,
            headers={"User-Agent": "job-market-pipeline/1.0"},
            timeout=20,
        )
        resp.raise_for_status()
        raw = resp.json()
        # First element is metadata — skip it
        jobs_raw = [j for j in raw if isinstance(j, dict) and "id" in j][:]
    except Exception as exc:
        log.warning(f"RemoteOK request failed: {exc}")
        return []

    results = []
    for job in jobs_raw:
        results.append({
            "source":      "remoteok",
            "id":          str(job.get("id")),
            "title":       job.get("position", ""),
            "company":     job.get("company", ""),
            "location":    "Remote",
            "salary_min":  job.get("salary_min"),
            "salary_max":  job.get("salary_max"),
            "description": job.get("description", ""),
            "url":         job.get("url", ""),
            "date_posted": job.get("date", ""),
            "tags":        job.get("tags", []),
            "search_term": "remoteok-global",
        })

    log.info(f"  RemoteOK: {len(results)} jobs fetched")
    return results


# ─────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────
def run() -> Path:
    """Execute extraction and persist raw JSON. Returns output path."""
    all_jobs: list[dict[str, Any]] = []

    # --- Adzuna (multi-term) ---
    for term in SEARCH_TERMS:
        log.info(f"  Adzuna → '{term}'")
        jobs = _fetch_adzuna(term)
        all_jobs.extend(jobs)
        time.sleep(1)

    # --- RemoteOK ---
    log.info("  RemoteOK → global feed")
    all_jobs.extend(_fetch_remoteok())

    # --- Persist ---
    out_path = RAW_DIR / f"jobs_{date.today()}.json"
    out_path.write_text(json.dumps(all_jobs, indent=2, ensure_ascii=False))
    log.info(f"  Total extracted: {len(all_jobs)} records → {out_path}")
    return out_path


# ── Quick test ─────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    path = run()
    print(f"Done: {path}")
