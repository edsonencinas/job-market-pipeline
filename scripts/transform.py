"""
scripts/transform.py
────────────────────
Clean and enrich raw job data:
  • Deduplicate by (source, id)
  • Standardise salaries to annual USD
  • Normalise locations → (city, region, is_remote)
  • Extract skills from title + description
  • Parse dates to ISO 8601

Input:  data/raw/jobs_YYYY-MM-DD.json  (most recent)
Output: data/clean/jobs_YYYY-MM-DD.parquet
"""

import json
import logging
import re
from typing import Dict, List, Optional, Tuple
from datetime import date, datetime
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

RAW_DIR   = Path("data/raw")
CLEAN_DIR = Path("data/clean")
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

# ── Skill keyword dictionary ───────────────────────────────────
# Format: "normalised_name": [regex_patterns]
SKILL_PATTERNS: Dict[str, List[str]] = {
    # Languages
    "python":      [r"\bpython\b"],
    "sql":         [r"\bsql\b", r"\bt-sql\b", r"\bpl/sql\b"],
    "r":           [r"\br programming\b", r"\blanguage r\b"],
    "scala":       [r"\bscala\b"],
    "java":        [r"\bjava\b(?!script)"],
    "javascript":  [r"\bjavascript\b", r"\bjs\b"],
    "typescript":  [r"\btypescript\b", r"\bts\b"],
    "go":          [r"\bgolang\b", r"\b(?<!\w)go(?!\w)"],
    "rust":        [r"\brust\b"],
    "c++":         [r"\bc\+\+\b", r"\bcpp\b"],
    # Data / ML
    "pandas":      [r"\bpandas\b"],
    "numpy":       [r"\bnumpy\b"],
    "spark":       [r"\bapache spark\b", r"\bpyspark\b", r"\bspark\b"],
    "kafka":       [r"\bkafka\b"],
    "airflow":     [r"\bairflow\b"],
    "dbt":         [r"\bdbt\b"],
    "tensorflow":  [r"\btensorflow\b", r"\btf\b"],
    "pytorch":     [r"\bpytorch\b"],
    "scikit-learn":[r"\bscikit[\-\s]?learn\b", r"\bsklearn\b"],
    "llm":         [r"\bllm\b", r"\blarge language model\b"],
    # Databases
    "postgresql":  [r"\bpostgresql\b", r"\bpostgres\b"],
    "mysql":       [r"\bmysql\b"],
    "mongodb":     [r"\bmongodb\b"],
    "redis":       [r"\bredis\b"],
    "snowflake":   [r"\bsnowflake\b"],
    "bigquery":    [r"\bbigquery\b"],
    "redshift":    [r"\bredshift\b"],
    "elasticsearch":[r"\belasticsearch\b"],
    # Cloud / DevOps
    "aws":         [r"\baws\b", r"\bamazon web services\b"],
    "azure":       [r"\bazure\b"],
    "gcp":         [r"\bgcp\b", r"\bgoogle cloud\b"],
    "docker":      [r"\bdocker\b"],
    "kubernetes":  [r"\bkubernetes\b", r"\bk8s\b"],
    "terraform":   [r"\bterraform\b"],
    "ci/cd":       [r"\bci/cd\b", r"\bgithub actions\b", r"\bjenkins\b"],
    # APIs / Web
    "rest api":    [r"\brest api\b", r"\brestful\b"],
    "graphql":     [r"\bgraphql\b"],
    "fastapi":     [r"\bfastapi\b"],
    "django":      [r"\bdjango\b"],
    "flask":       [r"\bflask\b"],
}

# ── Compiled regexes (compile once) ───────────────────────────
_SKILL_RE = {
    skill: re.compile("|".join(patterns), re.IGNORECASE)
    for skill, patterns in SKILL_PATTERNS.items()
}

# ── Remote keywords ───────────────────────────────────────────
_REMOTE_RE = re.compile(r"\bremote\b", re.IGNORECASE)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def extract_skills(text: str) -> List[str]:
    """Return sorted list of skill names found in `text`."""
    if not isinstance(text, str):
        return []
    return sorted(skill for skill, pattern in _SKILL_RE.items() if pattern.search(text))


def standardise_salary(row: pd.Series) -> Tuple[Optional[float], Optional[float]]:
    """
    Return (annual_min, annual_max) in USD.
    Adzuna salaries are already annual; RemoteOK uses None when absent.
    """
    lo, hi = row.get("salary_min"), row.get("salary_max")
    try:
        lo = float(lo) if lo else None
        hi = float(hi) if hi else None
    except (TypeError, ValueError):
        return None, None

    # Heuristic: monthly salary if < 1000 * 12 = 12k (unlikely annual)
    # Most APIs return annual, so we only fix clearly monthly values
    for val in (lo, hi):
        if val is not None and val < 5_000:
            lo = lo * 12 if lo else None
            hi = hi * 12 if hi else None
            break

    return lo, hi


def parse_date(raw_date: Optional[str]) -> Optional[str]:
    """Try common date formats; return ISO 8601 string or None."""
    if not raw_date:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw_date[:19], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def normalise_location(location: Optional[str]) -> dict:
    """
    Return dict with keys: city, region, country, is_remote
    Best-effort; no geocoding API required.
    """
    if not location:
        return {"city": None, "region": None, "country": None, "is_remote": False}

    is_remote = bool(_REMOTE_RE.search(location))

    # Strip trailing country abbreviations like ", US" or ", GB"
    parts = [p.strip() for p in location.split(",")]
    city   = parts[0] if len(parts) >= 1 else None
    region = parts[1] if len(parts) >= 2 else None
    country = parts[-1] if len(parts) >= 3 else None

    return {
        "city":      city or None,
        "region":    region or None,
        "country":   country or None,
        "is_remote": is_remote,
    }


# ─────────────────────────────────────────────────────────────
# Main transform
# ─────────────────────────────────────────────────────────────
def _latest_raw_file() -> Path:
    """Find the most recently created raw JSON file."""
    files = sorted(RAW_DIR.glob("jobs_*.json"), reverse=True)
    if not files:
        raise FileNotFoundError(f"No raw files found in {RAW_DIR}")
    return files[0]


def run() -> Path:
    """Transform raw → clean. Returns output parquet path."""
    raw_path = _latest_raw_file()
    log.info(f"  Reading {raw_path}")

    with raw_path.open() as f:
        records = json.load(f)

    df = pd.DataFrame(records)
    log.info(f"  Loaded {len(df)} raw records")

    # ── 1. Deduplicate ────────────────────────────────────────
    before = len(df)
    df = df.drop_duplicates(subset=["source", "id"])
    log.info(f"  Deduplication: {before} → {len(df)} rows")

    # ── 2. Parse dates ────────────────────────────────────────
    df["date_posted"] = df["date_posted"].apply(parse_date)

    # ── 3. Standardise salaries ───────────────────────────────
    salaries = df.apply(standardise_salary, axis=1, result_type="expand")
    df["salary_min"] = salaries[0]
    df["salary_max"] = salaries[1]
    df["salary_mid"] = df[["salary_min", "salary_max"]].mean(axis=1)

    # ── 4. Normalise location ─────────────────────────────────
    loc_df = df["location"].apply(normalise_location).apply(pd.Series)
    df = pd.concat([df.drop(columns=["location"]), loc_df], axis=1)

    # ── 5. Combine title + description for skill extraction ───
    search_text = (
        df["title"].fillna("") + " "
        + df["description"].fillna("") + " "
        + df.get("tags", pd.Series([""] * len(df))).apply(
            lambda t: " ".join(t) if isinstance(t, list) else ""
        )
    )
    df["skills"] = search_text.apply(extract_skills)
    df["skills_str"] = df["skills"].apply(lambda s: ",".join(s))

    # ── 6. Clean text fields ──────────────────────────────────
    df["title"]   = df["title"].str.strip().str[:255]
    df["company"] = df["company"].str.strip().str[:255]

    # ── 7. Filter: keep only rows with a title ────────────────
    df = df[df["title"].notna() & (df["title"] != "")]
    log.info(f"  After cleaning: {len(df)} rows")

    # ── 8. Persist ────────────────────────────────────────────
    out_path = CLEAN_DIR / f"jobs_{date.today()}.parquet"
    df.to_parquet(out_path, index=False)
    log.info(f"  Written → {out_path}")
    return out_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(run())
