# 📊 Job Market Trend Tracker

> Automated data pipeline that collects daily job listings from Adzuna and RemoteOK APIs, extracts in-demand skills, stores data in PostgreSQL, and visualises hiring trends in a Streamlit dashboard.

---

## Live Architecture

```
Adzuna API + RemoteOK API
         ↓
  scripts/extract.py       ← fetch raw JSON → data/raw/
         ↓
  scripts/transform.py     ← clean, deduplicate, extract skills → data/clean/
         ↓
  scripts/load.py          ← upsert into PostgreSQL (Supabase)
         ↓
  dashboard/app.py         ← Streamlit charts & KPIs
         ↑
  Render Cron Job          ← runs full pipeline daily at 06:00 UTC
```

---

## Tech Stack

| Layer           | Local         | Production                |
| :-------------- | :------------ | :------------------------ |
| Language        | Python 3.8    | Python 3.8                |
| Data processing | Pandas 2.0.3  | Pandas 2.0.3              |
| Database        | SQLite        | Supabase PostgreSQL       |
| ORM             | SQLAlchemy    | SQLAlchemy                |
| Dashboard       | Streamlit     | Streamlit Community Cloud |
| Scheduler       | Manual / cron | Render Cron Job           |
| Version control | Git           | GitHub                    |

---

## Folder Structure

```
job-market-pipeline/
├── scripts/
│   ├── __init__.py
│   ├── config.py         ← env vars & paths
│   ├── extract.py        ← Stage 1 — pull from APIs
│   ├── transform.py      ← Stage 2 — clean & enrich
│   ├── load.py           ← Stage 3 — upsert to DB
│   └── report.py         ← CLI analytics summary
├── dashboard/
│   └── app.py            ← Streamlit dashboard
├── sql/
│   └── schema.sql        ← PostgreSQL DDL + indexes + views
├── logs/                 ← auto-created on first run
├── main.py               ← pipeline orchestrator
├── scheduler.py          ← pure-Python daily scheduler
├── render.yaml           ← Render cron job config
├── runtime.txt           ← Python 3.8 for Render
├── requirements.txt
├── .env.example
└── README.md
```

---

## Quick Start (Local)

### 1. Clone and install

```bash
git clone https://github.com/yourusername/job-market-pipeline.git
cd job-market-pipeline
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set DATABASE_URL, ADZUNA_APP_ID, ADZUNA_APP_KEY
```

For local development use SQLite — no server needed:

```
DATABASE_URL=sqlite:///data/jobmarket.db
```

### 3. Create required folders

```bash
mkdir -p data/raw data/clean logs
```

### 4. Run the pipeline

```bash
# Full pipeline — extract → transform → load → report
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
# Opens at http://127.0.0.1:8501
```

---

## API Keys

### Adzuna (free tier)

1. Register at [developer.adzuna.com](https://developer.adzuna.com/signup) — no credit card needed
2. Create a new app in the dashboard
3. Copy your `App ID` and `App Key` into `.env`

Free tier: 250 requests/month · 50 results/page

### RemoteOK

No API key needed — works out of the box.

---

## Database Schema

### `jobs` table

| Column                | Type      | Notes                       |
| :-------------------- | :-------- | :-------------------------- |
| id                    | SERIAL PK |                             |
| source                | TEXT      | `adzuna` or `remoteok`      |
| external_id           | TEXT      | Source's own ID             |
| title                 | TEXT      |                             |
| company               | TEXT      |                             |
| city, region, country | TEXT      | Parsed from location string |
| is_remote             | BOOLEAN   |                             |
| salary_min/max/mid    | NUMERIC   | Annual USD                  |
| date_posted           | DATE      |                             |
| scraped_at            | DATE      | Pipeline run date           |

### `skills` + `job_skills`

Many-to-many: each job links to zero or more normalised skill tags extracted by regex from the job description.

---

## Skills Detected

The transform stage uses 40+ regex patterns to extract skills including:

Python, SQL, Pandas, Spark, Airflow, dbt, Kafka, TensorFlow, PyTorch, scikit-learn, PostgreSQL, Snowflake, BigQuery, Redshift, AWS, Azure, GCP, Docker, Kubernetes, Terraform, FastAPI, Django, Flask, REST API, GraphQL, and more.

---

## Deployment

### Database — Supabase (free)

1. Create a free project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** and run `sql/schema.sql` to create tables
3. Go to **Settings → Database → Connection pooling → Session mode**
4. Copy the Session Pooler URL and add `?sslmode=require` at the end:

```
postgresql://postgres.xxxx:[PASSWORD]@aws-0-region.pooler.supabase.com:5432/postgres?sslmode=require
```

> Use Session Pooler — not the direct connection string. The direct connection requires IPv6 which is not supported on all networks and hosting platforms.

### Pipeline — Render Cron Job (free)

1. Sign up at [render.com](https://render.com) using your GitHub account
2. Click **New → Cron Job**
3. Connect your GitHub repository
4. Fill in the settings:

```
Name:           job-market-pipeline
Runtime:        Python
Branch:         main
Build Command:  pip install -r requirements.txt
Command:        python main.py
Schedule:       0 6 * * *
```

5. Add environment variables — never put these in GitHub:

```
DATABASE_URL    → your Supabase Session Pooler URL
ADZUNA_APP_ID   → your Adzuna app ID
ADZUNA_APP_KEY  → your Adzuna app key
```

6. Click **Create Cron Job** then **Trigger Run** to test immediately

### Dashboard — Streamlit Community Cloud (free)

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
2. Click **New app**
3. Select your repository and set **Main file path** to `dashboard/app.py`
4. Go to **Settings → Secrets** and add:

```toml
DATABASE_URL = "your Supabase Session Pooler URL"
```

5. Click **Deploy**

---

## Python 3.8 Compatibility Notes

This project runs on Python 3.8. The following changes were made to ensure compatibility:

- All `dict[str, list[str]]` type hints replaced with `Dict[str, List[str]]` from `typing`
- All `X | None` union types replaced with `Optional[X]` from `typing`
- All `tuple[x, y]` hints replaced with `Tuple[x, y]` from `typing`
- Package versions pinned to Python 3.8 compatible releases (see `requirements.txt`)

---

## Known Issues and Fixes

**VSCode Pylance import warnings** — add `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.analysis.diagnosticSeverityOverrides": {
    "reportMissingModuleSource": "none"
  }
}
```

**SQLite stores booleans as 0/1** — the dashboard handles this automatically using `.apply(lambda x: "Remote" if int(x) == 1 else "On-Site")`.

**Localhost not resolving** — use `http://127.0.0.1:8501` directly instead of `http://localhost:8501`.

**Supabase direct connection fails** — use the Session Pooler URL instead. The direct connection string requires IPv6 which many networks block.

---

## Adding New Data Sources

1. Write a `_fetch_<source>()` function in `scripts/extract.py`
2. Return a list of dicts with these keys:
   `source · id · title · company · location · salary_min · salary_max · description · url · date_posted`
3. Call your function inside `run()` and extend `all_jobs`

---

## Advanced Extensions

| Feature               | How                                        |
| :-------------------- | :----------------------------------------- |
| Airflow orchestration | Replace `scheduler.py` with a DAG          |
| Docker                | `docker compose up` with postgres + app    |
| dbt transformations   | Add `dbt/` models for salary normalisation |
| ML salary prediction  | `scikit-learn` regression on `jobs` table  |
| Email alerts          | `smtplib` weekly digest from `report.py`   |

---

## Results from First Run

- **846** job listings collected
- **33** unique skills extracted
- **617** job-skill connections
- **#1 skill**: Python
- **Salary sweet spot**: $100K–$120K USD
- **Remote jobs**: 11.3% of listings
