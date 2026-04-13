CREATE TABLE IF NOT EXISTS jobs (
    id           SERIAL PRIMARY KEY,
    source       TEXT NOT NULL,
    external_id  TEXT NOT NULL,
    title        TEXT,
    company      TEXT,
    city         TEXT,
    region       TEXT,
    country      TEXT,
    is_remote    BOOLEAN NOT NULL DEFAULT FALSE,
    salary_min   NUMERIC(12,2),
    salary_max   NUMERIC(12,2),
    salary_mid   NUMERIC(12,2),
    url          TEXT,
    date_posted  DATE,
    scraped_at   DATE NOT NULL DEFAULT CURRENT_DATE,
    CONSTRAINT jobs_source_ext_uq UNIQUE (source, external_id)
);

CREATE TABLE IF NOT EXISTS skills (
    id    SERIAL PRIMARY KEY,
    name  TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS job_skills (
    job_id    INTEGER NOT NULL REFERENCES jobs(id)   ON DELETE CASCADE,
    skill_id  INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    PRIMARY KEY (job_id, skill_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_scraped_at  ON jobs (scraped_at);
CREATE INDEX IF NOT EXISTS idx_jobs_date_posted ON jobs (date_posted);
CREATE INDEX IF NOT EXISTS idx_jobs_is_remote   ON jobs (is_remote);
CREATE INDEX IF NOT EXISTS idx_jobs_salary_mid  ON jobs (salary_mid);
CREATE INDEX IF NOT EXISTS idx_job_skills_job   ON job_skills (job_id);
CREATE INDEX IF NOT EXISTS idx_job_skills_skill ON job_skills (skill_id);
