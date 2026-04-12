"""
Job Market Trend Tracker - Main Pipeline Orchestrator
Run: python main.py [--mode full|extract|transform|load|report]
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# ── Logging setup ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path("logs") / f"pipeline_{datetime.today().date()}.log"),
    ],
)
log = logging.getLogger(__name__)


def run_pipeline(mode: str = "full") -> None:
    """Execute one or more pipeline stages."""
    log.info("═" * 60)
    log.info(f"Job Market Pipeline  |  mode={mode}  |  {datetime.now()}")
    log.info("═" * 60)

    try:
        if mode in ("full", "extract"):
            log.info("▶ STAGE 1 — Extract")
            from scripts.extract import run as extract_run
            raw_path = extract_run()
            log.info(f"   Saved raw data → {raw_path}")

        if mode in ("full", "transform"):
            log.info("▶ STAGE 2 — Transform")
            from scripts.transform import run as transform_run
            clean_path = transform_run()
            log.info(f"   Saved clean data → {clean_path}")

        if mode in ("full", "load"):
            log.info("▶ STAGE 3 — Load")
            from scripts.load import run as load_run
            rows = load_run()
            log.info(f"   Inserted/updated {rows} rows")

        if mode in ("full", "report"):
            log.info("▶ STAGE 4 — Report")
            from scripts.report import run as report_run
            report_run()
            log.info("   Report generated")

        log.info("✔ Pipeline finished successfully")

    except Exception as exc:
        log.exception(f"✘ Pipeline failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    # ── Ensure log directory exists ────────────────────────────
    Path("logs").mkdir(exist_ok=True)

    parser = argparse.ArgumentParser(description="Job Market Pipeline")
    parser.add_argument(
        "--mode",
        choices=["full", "extract", "transform", "load", "report"],
        default="full",
        help="Which stage(s) to run (default: full)",
    )
    args = parser.parse_args()
    run_pipeline(args.mode)
