"""
scripts/alert.py
────────────────
Sends email alert via Resend when new trending skills appear.
Called automatically by main.py after each pipeline run.
"""

import logging
import os
from datetime import date, timedelta
from typing import List, Set

import resend
from sqlalchemy import create_engine, text

from scripts.config import DATABASE_URL

log = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "")
EMAIL_SENDER   = "onboarding@resend.dev"


# ─────────────────────────────────────────────────────────────
# Queries
# ─────────────────────────────────────────────────────────────
def _get_top_skills(since: str, limit: int = 10) -> List[str]:
    """Return top N skill names for the given period."""
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT s.name
            FROM job_skills js
            JOIN skills s ON s.id = js.skill_id
            JOIN jobs   j ON j.id = js.job_id
            WHERE j.scraped_at >= :since
            GROUP BY s.name
            ORDER BY COUNT(*) DESC
            LIMIT :limit;
        """), {"since": since, "limit": limit}).fetchall()
    return [r[0] for r in rows]

# ─────────────────────────────────────────────────────────────
# Email builder
# ─────────────────────────────────────────────────────────────
def _build_email(new_skills: List[str], top_skills: List[str]) -> str:
    """Build HTML email body."""
    new_items = "".join(
        f"<li><strong>{s}</strong></li>"
        for s in new_skills
    )
    top_items = "".join(
        f"<li>"
        f"{'<strong>' if s in new_skills else ''}"
        f"{i+1}. {s}"
        f"{'</strong> &larr; NEW' if s in new_skills else ''}"
        f"</li>"
        for i, s in enumerate(top_skills)
    )

    return f"""
    <html>
    <body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;">

        <h2 style="color:#2563eb;">Job Market Alert</h2>
        <p style="color:#555;">
            New trending skills detected in today's job listings.
        </p>

        <div style="background:#f0f7ff;border-left:4px solid #2563eb;
                    padding:12px 16px;margin:16px 0;border-radius:4px;">
            <strong>New skills in top 10:</strong>
            <ul style="margin:8px 0 0;">{new_items}</ul>
        </div>

        <p><strong>Today's full top 10:</strong></p>
        <ol style="line-height:1.8;">{top_items}</ol>

        <hr style="margin:24px 0;border:none;border-top:1px solid #eee;">
        <p style="color:#aaa;font-size:12px;">
            Job Market Pipeline · {date.today()} · Powered by Resend
        </p>

    </body>
    </html>
    """

# ─────────────────────────────────────────────────────────────
# Send email
# ─────────────────────────────────────────────────────────────
def _send_email(subject: str, html_body: str) -> None:
    """Send HTML email via Resend."""
    if not RESEND_API_KEY:
        log.warning("RESEND_API_KEY not set — skipping alert")
        return

    if not EMAIL_RECEIVER:
        log.warning("EMAIL_RECEIVER not set — skipping alert")
        return

    resend.api_key = RESEND_API_KEY

    params = {
        "from":    EMAIL_SENDER,
        "to":      [EMAIL_RECEIVER],
        "subject": subject,
        "html":    html_body,
    }

    response = resend.Emails.send(params)
    log.info(f"Alert email sent — id: {response['id']}")

# ─────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────
def check_and_alert() -> None:
    """
    Compare today's top skills with yesterday's.
    Send email alert if new skills appear in top 10.
    """
    today     = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    today_skills     = _get_top_skills(since=today,     limit=10)
    yesterday_skills = _get_top_skills(since=yesterday, limit=10)

    today_set:     Set[str] = set(today_skills)
    yesterday_set: Set[str] = set(yesterday_skills)

    new_skills = list(today_set - yesterday_set)

    log.info(f"Today's top skills:     {today_skills}")
    log.info(f"Yesterday's top skills: {yesterday_skills}")
    log.info(f"New skills detected:    {new_skills}")

    if new_skills:
        html = _build_email(new_skills, today_skills)
        _send_email(
            subject=f"Job Market Alert — {len(new_skills)} new trending skill(s) today",
            html_body=html,
        )
    else:
        log.info("No new trending skills today — no alert sent")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    check_and_alert()