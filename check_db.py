from sqlalchemy import create_engine, text
from scripts.config import DATABASE_URL

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    jobs  = conn.execute(text("SELECT COUNT(*) FROM jobs;")).fetchone()[0]
    skills = conn.execute(text("SELECT COUNT(*) FROM skills;")).fetchone()[0]
    bridges = conn.execute(text("SELECT COUNT(*) FROM job_skills;")).fetchone()[0]

    print(f"jobs table:       {jobs} rows")
    print(f"skills table:     {skills} rows")
    print(f"job_skills table: {bridges} rows")

    print("\nSample jobs:")
    rows = conn.execute(text("SELECT title, company, city, salary_mid FROM jobs LIMIT 5;")).fetchall()
    for r in rows:
        print(f"  {r[0]:<35} {r[1]:<25} {r[2]:<15} {r[3]}")
