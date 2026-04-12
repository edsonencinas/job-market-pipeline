# 📊 Job Market Trend Tracker

> An automated data pipeline that collects daily job listings, transforms them,
> stores them in PostgreSQL, and visualises insights in a Streamlit dashboard.

## Architecture

```
Adzuna API + RemoteOK API
         ↓
  scripts/extract.py       ← fetch raw JSON
         ↓
  scripts/transform.py     ← clean, deduplicate, extract skills
         ↓
  scripts/load.py          ← upsert into PostgreSQL
         ↓
  dashboard/app.py         ← Streamlit charts & KPIs
         ↑
  scheduler.py / cron      ← runs full pipeline daily
```

## Folder Structure

```
job-market-pipeline/
├── data/
│   ├── raw/              ← daily raw JSON files
│   └── clean/            ← daily clean Parquet files
├── scripts/
│   ├── config.py         ← env vars & paths
│   ├── extract.py        ← Stage 1 – pull from APIs
│   ├── transform.py      ← Stage 2 – clean & enrich
│   ├── load.py           ← Stage 3 – upsert to DB
│   └── report.py         ← CLI analytics summary
├── dashboard/
│   └── app.py            ← Streamlit dashboard
├── sql/
│   └── schema.sql        ← PostgreSQL DDL + indexes + views
├── logs/                 ← auto-created on first run
├── main.py               ← pipeline orchestrator
├── scheduler.py          ← pure-Python daily scheduler
├── requirements.txt
├── .env.example
└── README.md
```

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/yourusername/job-market-pipeline.git
cd job-market-pipeline
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your DB URL and Adzuna API keys
```

**Free Adzuna API key:** https://developer.adzuna.com/

### 3. Set up PostgreSQL (or use SQLite)

**PostgreSQL:**

```bash
createdb jobmarket
psql -d jobmarket -f sql/schema.sql
```

**SQLite (no server needed — great for local dev):**

```bash
# Just set DATABASE_URL=sqlite:///data/jobmarket.db in .env
# Tables are created automatically on first run
```

### 4. Run the pipeline

```bash
# Full pipeline (extract → transform → load → report)
python main.py

# Individual stages
python main.py --mode extract
python main.py --mode transform
python main.py --mode load
python main.py --mode report
```

### 5. Launch the dashboard

```bash
streamlit run dashboard/app.py
# Opens at http://localhost:8501
```

### 6. Automate daily runs

**Option A — Pure Python (simplest):**

```bash
python scheduler.py &
```

**Option B — Cron (recommended for Linux/macOS):**

```bash
crontab -e
# Add this line (runs at 6 AM daily):
0 6 * * * /path/to/venv/bin/python /path/to/main.py >> /path/to/logs/cron.log 2>&1
```

**Option C — Windows Task Scheduler:**
Create a Basic Task → Action: `python C:\path\to\main.py`

## Database Schema

### `jobs` table

| Column             | Type      | Notes                       |
| :----------------- | :-------- | :-------------------------- |
| id                 | SERIAL PK |                             |
| source             | TEXT      | `adzuna` / `remoteok`       |
| external_id        | TEXT      | Source's own ID             |
| title              | TEXT      |                             |
| company            | TEXT      |                             |
| city, region       | TEXT      | Parsed from location string |
| is_remote          | BOOLEAN   |                             |
| salary_min/max/mid | NUMERIC   | Annual USD                  |
| date_posted        | DATE      |                             |
| scraped_at         | DATE      | Pipeline run date           |

### `skills` + `job_skills`

Many-to-many: each job links to zero or more normalised skill tags.

## Skills Detected

The transform stage uses regex to extract 40+ skills, including:
Python, SQL, Pandas, Spark, Airflow, dbt, Kafka, TensorFlow, PyTorch,
PostgreSQL, Snowflake, BigQuery, AWS, Azure, GCP, Docker, Kubernetes, etc.

## Adding New Data Sources

1. Write a `_fetch_<source>()` function in `scripts/extract.py`
2. Return a list of dicts with these keys:
   `source, id, title, company, location, salary_min, salary_max, description, url, date_posted`
3. Call your function inside `run()` and extend `all_jobs`

## Advanced Extensions

| Feature               | How                                        |
| :-------------------- | :----------------------------------------- |
| Airflow orchestration | Replace `scheduler.py` with a DAG          |
| Docker                | `docker compose up` with postgres + app    |
| Cloud deployment      | Render / Railway / Fly.io (add Procfile)   |
| dbt transformations   | Add `dbt/` models for salary normalisation |
| ML salary prediction  | `scikit-learn` regression on `jobs` table  |
| Email alerts          | `smtplib` weekly digest from `report.py`   |

## Resume Bullet Point

> Built automated job-market data pipeline using Python, PostgreSQL, and
> Streamlit that ingests 500+ daily listings from 2 APIs, extracts 40+ skill
> signals, and surfaces hiring trends in a live dashboard.
