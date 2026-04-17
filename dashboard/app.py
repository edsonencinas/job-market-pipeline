"""
dashboard/app.py
────────────────
Streamlit dashboard for the Job Market Trend Tracker.

Run:
    streamlit run dashboard/app.py

Set DATABASE_URL in .env before running.
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import math

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import create_engine, text

from scripts.config import DATABASE_URL

# ── Page config ────────────────────────────────────────────────
st.set_page_config(
    page_title="Job Market Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Cached DB connection ───────────────────────────────────────
@st.cache_resource
def get_engine():
    return create_engine(DATABASE_URL)


# ── Cached data loaders ────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_top_skills(since: str) -> pd.DataFrame:
    q = text("""
        SELECT s.name AS skill, COUNT(*) AS job_count
        FROM job_skills js
        JOIN skills s ON s.id = js.skill_id
        JOIN jobs   j ON j.id = js.job_id
        WHERE j.scraped_at >= :since
        GROUP BY s.name ORDER BY job_count DESC LIMIT 25;
    """)
    with get_engine().connect() as conn:
        return pd.read_sql(q, conn, params={"since": since})


@st.cache_data(ttl=3600)
def load_salary_data(since: str) -> pd.DataFrame:
    q = text("""
        SELECT title, company, city, is_remote, salary_mid, date_posted
        FROM jobs
        WHERE salary_mid IS NOT NULL AND scraped_at >= :since;
    """)
    with get_engine().connect() as conn:
        return pd.read_sql(q, conn, params={"since": since})


@st.cache_data(ttl=3600)
def load_remote_ratio(since: str) -> pd.DataFrame:
    q = text("""
        SELECT is_remote, COUNT(*) AS cnt
        FROM jobs WHERE scraped_at >= :since GROUP BY is_remote;
    """)
    with get_engine().connect() as conn:
        return pd.read_sql(q, conn, params={"since": since})


@st.cache_data(ttl=3600)
def load_trend(since: str) -> pd.DataFrame:
    q = text("""
        SELECT date_posted, COUNT(*) AS new_listings
        FROM jobs
        WHERE date_posted >= :since
        GROUP BY date_posted ORDER BY date_posted;
    """)
    with get_engine().connect() as conn:
        return pd.read_sql(q, conn, params={"since": since})


@st.cache_data(ttl=3600)
def load_top_companies(since: str) -> pd.DataFrame:
    q = text("""
        SELECT company, COUNT(*) AS listings
        FROM jobs
        WHERE scraped_at >= :since AND company IS NOT NULL AND company != ''
        GROUP BY company ORDER BY listings DESC LIMIT 15;
    """)
    with get_engine().connect() as conn:
        return pd.read_sql(q, conn, params={"since": since})


@st.cache_data(ttl=3600)
def load_summary(since: str) -> Dict:
    q = text("""
        SELECT
            COUNT(*)                           AS total_jobs,
            COUNT(DISTINCT company)            AS companies,
            ROUND(AVG(salary_mid))             AS avg_salary,
            SUM(CASE WHEN is_remote THEN 1 ELSE 0 END) AS remote_count
        FROM jobs WHERE scraped_at >= :since;
    """)
    with get_engine().connect() as conn:
        row = conn.execute(q, {"since": since}).fetchone()
    return {
        "total_jobs": int(row[0] or 0),
        "companies":  int(row[1] or 0),
        "avg_salary": int(row[2]) if row[2] is not None and not math.isnan(float(row[2])) else 0,
        "remote_pct": round(row[3] / row[0] * 100, 1) if row[0] else 0,
    }

# ─────────────────────────────────────────────────────────────
# Layout
# ─────────────────────────────────────────────────────────────
st.title("📊 Job Market Trend Tracker")
st.caption("Automated daily pipeline · Python + PostgreSQL + Streamlit")

# ── Sidebar filters ────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")
    days = st.slider("Days back", min_value=7, max_value=90, value=30, step=7)
    since = (date.today() - timedelta(days=days)).isoformat()
    st.markdown("---")
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Data since: {since}")

# ── KPI cards ──────────────────────────────────────────────────
summary = load_summary(since)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Listings",   f"{summary['total_jobs']:,}")
k2.metric("Unique Companies", f"{summary['companies']:,}")
k3.metric("Avg Salary (USD)", f"${summary['avg_salary']:,}")
k4.metric("Remote Jobs",      f"{summary['remote_pct']}%")

st.divider()

# ── Row 1: Skills + Remote ratio ───────────────────────────────
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🔥 Top In-Demand Skills")
    skills_df = load_top_skills(since)
    if not skills_df.empty:
        fig = px.bar(
            skills_df.head(15),
            x="job_count", y="skill",
            orientation="h",
            labels={"job_count": "Job listings", "skill": ""},
            color="job_count",
            color_continuous_scale="Blues",
        )
        fig.update_layout(
            showlegend=False,
            coloraxis_showscale=False,
            yaxis={"categoryorder": "total ascending"},
            margin=dict(l=0, r=0, t=0, b=0),
            height=420,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No skill data yet — run the pipeline first.")

with col2:
    st.subheader("🌍 Remote vs On-Site")
    remote_df = load_remote_ratio(since)
    if not remote_df.empty:
        remote_df["label"] = remote_df["is_remote"].apply(
            lambda x: "Remote" if int(x) == 1 else "On-Site"
        )
        fig = px.pie(
            remote_df,
            names="label",
            values="cnt",
            hole=0.5,
            color_discrete_sequence=["#2563eb", "#93c5fd"],
        )
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=420)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data yet.")

st.divider()

# ── Row 2: Salary distribution + Posting trend ────────────────
col3, col4 = st.columns(2)

with col3:
    st.subheader("💰 Salary Distribution")
    salary_df = load_salary_data(since)
    if not salary_df.empty:
        fig = px.histogram(
            salary_df,
            x="salary_mid",
            nbins=40,
            labels={"salary_mid": "Annual Salary (USD)"},
            color_discrete_sequence=["#2563eb"],
        )
        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            height=320,
            bargap=0.05,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No salary data yet.")

with col4:
    st.subheader("📈 Daily Posting Trend")
    trend_df = load_trend(since)
    if not trend_df.empty:
        trend_df["date_posted"] = pd.to_datetime(trend_df["date_posted"])
        fig = px.area(
            trend_df,
            x="date_posted",
            y="new_listings",
            labels={"date_posted": "Date", "new_listings": "New listings"},
            color_discrete_sequence=["#2563eb"],
        )
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=320)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No trend data yet.")

st.divider()

# ── Top companies ──────────────────────────────────────────────
st.subheader("🏢 Top Hiring Companies")
companies_df = load_top_companies(since)
if not companies_df.empty:
    fig = px.bar(
        companies_df,
        x="company",
        y="listings",
        labels={"listings": "Listings", "company": ""},
        color="listings",
        color_continuous_scale="Blues",
    )
    fig.update_layout(
        showlegend=False,
        coloraxis_showscale=False,
        margin=dict(l=0, r=0, t=0, b=0),
        height=320,
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No company data yet.")

# ── Raw data table ─────────────────────────────────────────────
with st.expander("🗃️ Raw job listings"):
    salary_df_full = load_salary_data(since)
    st.dataframe(
        salary_df_full[["title", "company", "city", "is_remote", "salary_mid", "date_posted"]],
        use_container_width=True,
        height=300,
    )
