import logging
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import create_engine, text

from scripts.config import DATABASE_URL

log = logging.getLogger(__name__)

def run(days_back: int = 30) -> None:
    engine = create_engine(DATABASE_URL)
    since  = (date.today() - timedelta(days=days_back)).isoformat()

    print(f"\n{'═' * 50}")
    print(f"  JOB MARKET REPORT  |  last {days_back} days")
    print(f"  Generated: {date.today()}")
    print(f"{'═' * 50}")

    with engine.connect() as conn:
        df = pd.read_sql(text("""
            SELECT s.name AS skill, COUNT(*) AS job_count
            FROM job_skills js
            JOIN skills s ON s.id = js.skill_id
            JOIN jobs   j ON j.id = js.job_id
            WHERE j.scraped_at >= :since
            GROUP BY s.name ORDER BY job_count DESC LIMIT 20;
        """), conn, params={"since": since})

        print("\n  Top In-Demand Skills")
        print("  " + "─" * 40)
        for _, r in df.iterrows():
            bar = "█" * min(int(r.job_count / 3), 25)
            print(f"  {r.skill:<20} {bar} {r.job_count}")

    print(f"\n{'═' * 50}\n")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
EOF