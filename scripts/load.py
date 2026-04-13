"""
scripts/load.py
───────────────
Upsert clean Parquet data into PostgreSQL.

Tables created on first run:
  jobs         — one row per unique listing
  skills       — skill name lookup
  job_skills   — many-to-many bridge

Set DATABASE_URL in .env:
  DATABASE_URL=postgresql://user:password@localhost:5432/jobmarket

SQLite fallback for local dev:
  DATABASE_URL=sqlite:///data/jobmarket.db
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from scripts.config import DATABASE_URL

log = logging.getLogger(__name__)

CLEAN_DIR = Path("data/clean")

# ─────────────────────────────────────────────────────────────
# DDL
# ─────────────────────────────────────────────────────────────
_CREATE_JOBS = """
CREATE TABLE IF NOT EXISTS jobs (
    id           SERIAL PRIMARY KEY,
    source       TEXT NOT NULL,
    external_id  TEXT NOT NULL,
    title        TEXT,
    company      TEXT,
    city         TEXT,
    region       TEXT,
    country      TEXT,
    is_remote    BOOLEAN DEFAULT FALSE,
    salary_min   NUMERIC(12,2),
    salary_max   NUMERIC(12,2),
    salary_mid   NUMERIC(12,2),
    url          TEXT,
    date_posted  DATE,
    scraped_at   DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (source, external_id)
);
"""

_CREATE_SKILLS = """
CREATE TABLE IF NOT EXISTS skills (
    id    SERIAL PRIMARY KEY,
    name  TEXT UNIQUE NOT NULL
);
"""

_CREATE_JOB_SKILLS = """
CREATE TABLE IF NOT EXISTS job_skills (
    job_id   INTEGER REFERENCES jobs(id)   ON DELETE CASCADE,
    skill_id INTEGER REFERENCES skills(id) ON DELETE CASCADE,
    PRIMARY KEY (job_id, skill_id)
);
"""


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _ensure_tables(conn) -> None:
    conn.execute(text(_CREATE_JOBS))
    conn.execute(text(_CREATE_SKILLS))
    conn.execute(text(_CREATE_JOB_SKILLS))
    conn.commit()

def _upsert_job(conn, row: pd.Series) -> Optional[int]:
    """
    Insert job if (source, external_id) is new.
    Returns the internal job id (new or existing).
    """
    # Check if already exists
    existing = conn.execute(
        text("SELECT id FROM jobs WHERE source = :source AND external_id = :external_id;"),
        {"source": row.get("source"), "external_id": str(row.get("id"))}
    ).fetchone()

    if existing:
        return None  # already in DB, skip

    # Insert new row
    conn.execute(text("""
        INSERT INTO jobs
            (source, external_id, title, company, city, region, country,
             is_remote, salary_min, salary_max, salary_mid, url, date_posted)
        VALUES
            (:source, :external_id, :title, :company, :city, :region, :country,
             :is_remote, :salary_min, :salary_max, :salary_mid, :url, :date_posted);
    """), {
        "source":      row.get("source"),
        "external_id": str(row.get("id")),
        "title":       row.get("title"),
        "company":     row.get("company"),
        "city":        row.get("city"),
        "region":      row.get("region"),
        "country":     row.get("country"),
        "is_remote":   bool(row.get("is_remote", False)),
        "salary_min":  row.get("salary_min") or None,
        "salary_max":  row.get("salary_max") or None,
        "salary_mid":  row.get("salary_mid") or None,
        "url":         row.get("url"),
        "date_posted": row.get("date_posted") or None,
    })

    # Get the id of the row we just inserted
    job_id = conn.execute(
        text("SELECT id FROM jobs WHERE source = :source AND external_id = :external_id;"),
        {"source": row.get("source"), "external_id": str(row.get("id"))}
    ).fetchone()[0]

    return job_id # None = already existed

def _get_or_create_skill(conn, name: str, cache: Dict[str, int]) -> int:
    if name in cache:
        return cache[name]

    # Insert if not exists
    conn.execute(
        text("INSERT OR IGNORE INTO skills (name) VALUES (:n);"),
        {"n": name},
    )

    # Always fetch the id separately
    skill_id = conn.execute(
        text("SELECT id FROM skills WHERE name = :n;"),
        {"n": name},
    ).fetchone()[0]

    cache[name] = skill_id
    return skill_id


def _link_skills(conn, job_id: int, skills: List[str], cache: Dict[str, int]) -> None:
    for skill_name in skills:
        skill_id = _get_or_create_skill(conn, skill_name, cache)
        conn.execute(
            text("""
                INSERT INTO job_skills (job_id, skill_id)
                VALUES (:j, :s)
                ON CONFLICT DO NOTHING;
            """),
            {"j": job_id, "s": skill_id},
        )


# ─────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────
def _latest_clean_file() -> Path:
    files = sorted(CLEAN_DIR.glob("jobs_*.parquet"), reverse=True)
    if not files:
        raise FileNotFoundError(f"No clean files found in {CLEAN_DIR}")
    return files[0]

def run() -> int:
    engine = create_engine(DATABASE_URL, echo=False)
    clean_path = _latest_clean_file()
    df = pd.read_parquet(clean_path)
    log.info(f"  Loading {len(df)} rows from {clean_path}")

    new_rows = 0
    skill_cache: Dict[str, int] = {}

    with engine.connect() as conn:
        _ensure_tables(conn)

        for _, row in df.iterrows():
            try:
                with conn.begin():
                    job_id = _upsert_job(conn, row)
                    if job_id is not None:
                        new_rows += 1
                        # Fix: convert numpy array → plain Python list
                        skills = row.get("skills")
                        if skills is None:
                            skills = []
                        elif isinstance(skills, str):
                            skills = [s for s in skills.split(",") if s]
                        else:
                            skills = list(skills)  # handles numpy arrays
                        _link_skills(conn, job_id, skills, skill_cache)
            except Exception as e:
                log.warning(f"  Skipping row due to error: {e}")
                continue

    log.info(f"  Inserted {new_rows} new jobs ({len(df) - new_rows} duplicates skipped)")
    return new_rows

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(f"Loaded {run()} new rows")
