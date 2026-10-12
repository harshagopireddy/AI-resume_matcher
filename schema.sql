-- =====================================================================
--  AI RESUME MATCHER  -  Database Schema (SQLite)
--  Project : AI-resume_matcher
--  Roles   : candidate | company | admin   (login by email OR mobile)
-- =====================================================================
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- 0) users : authentication for every role
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    role          TEXT NOT NULL CHECK (role IN ('candidate','company','admin')),
    full_name     TEXT NOT NULL,
    email         TEXT UNIQUE,             -- login by email ...
    phone         TEXT UNIQUE,             -- ... or by mobile number
    password_hash TEXT NOT NULL,
    is_active     INTEGER DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------
-- 1) companies : profile owned by a 'company' user
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS companies (
    company_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER UNIQUE,
    company_name TEXT NOT NULL,
    hr_name      TEXT,
    industry     TEXT,
    location     TEXT,
    website      TEXT,
    description  TEXT,
    verified     INTEGER DEFAULT 0,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- 2) candidates : profile owned by a 'candidate' user
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidates (
    candidate_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER UNIQUE,
    full_name        TEXT    NOT NULL,
    email            TEXT,
    phone            TEXT,
    location         TEXT,
    years_experience REAL    DEFAULT 0,
    education        TEXT,
    linkedin         TEXT,
    created_at       TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- 3) resumes : the raw resume document + cleaned text used by the NLP
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS resumes (
    resume_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id    INTEGER NOT NULL,
    title           TEXT,
    raw_text        TEXT    NOT NULL,
    clean_text      TEXT,
    source_file     TEXT,
    word_count      INTEGER DEFAULT 0,
    is_primary      INTEGER DEFAULT 1,
    uploaded_at     TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- 4) resume_files : metadata for files uploaded with the "+" button
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS resume_files (
    file_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id   INTEGER NOT NULL,
    filename    TEXT,
    stored_name TEXT,
    filesize    INTEGER,
    mime        TEXT,
    uploaded_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (resume_id) REFERENCES resumes(resume_id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- 5) skills : master dictionary of skills
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS skills (
    skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL UNIQUE,
    category TEXT,
    aliases  TEXT
);

-- ---------------------------------------------------------------------
-- 6) resume_skills : bridge table  resume <-> skill
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS resume_skills (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id  INTEGER NOT NULL,
    skill_id   INTEGER NOT NULL,
    years_used REAL    DEFAULT 0,
    mentions   INTEGER DEFAULT 1,
    UNIQUE (resume_id, skill_id),
    FOREIGN KEY (resume_id) REFERENCES resumes(resume_id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id)  REFERENCES skills(skill_id)  ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- 7) job_postings : open roles posted by companies
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS job_postings (
    job_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER,
    title           TEXT NOT NULL,
    company         TEXT,
    location        TEXT,
    description     TEXT NOT NULL,
    clean_text      TEXT,
    min_experience  REAL DEFAULT 0,
    salary          TEXT,
    employment_type TEXT DEFAULT 'Full-time',
    posted_at       TEXT DEFAULT (datetime('now')),
    is_active       INTEGER DEFAULT 1,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- 8) job_skills : bridge table  job <-> skill  (with weight)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS job_skills (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      INTEGER NOT NULL,
    skill_id    INTEGER NOT NULL,
    is_required INTEGER DEFAULT 1,
    weight      REAL    DEFAULT 1.0,
    UNIQUE (job_id, skill_id),
    FOREIGN KEY (job_id)   REFERENCES job_postings(job_id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skills(skill_id)     ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- 9) match_results : one AI score per (resume, job) pair
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS match_results (
    match_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id        INTEGER NOT NULL,
    job_id           INTEGER NOT NULL,
    tfidf_score      REAL,
    embedding_score  REAL,
    skill_score      REAL,
    experience_score REAL,
    final_score      REAL,
    recommendation   TEXT,
    matched_at       TEXT DEFAULT (datetime('now')),
    UNIQUE (resume_id, job_id),
    FOREIGN KEY (resume_id) REFERENCES resumes(resume_id)   ON DELETE CASCADE,
    FOREIGN KEY (job_id)    REFERENCES job_postings(job_id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- 10) match_skill_details : matched / missing skills per match
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS match_skill_details (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,
    status   TEXT,
    FOREIGN KEY (match_id) REFERENCES match_results(match_id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skills(skill_id)        ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- 11) applications : a candidate applies to a job
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id   INTEGER NOT NULL,
    job_id         INTEGER NOT NULL,
    resume_id      INTEGER,
    status         TEXT DEFAULT 'submitted',   -- submitted/reviewed/shortlisted/rejected
    cover_note     TEXT,
    applied_at     TEXT DEFAULT (datetime('now')),
    UNIQUE (candidate_id, job_id),
    FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE,
    FOREIGN KEY (job_id)       REFERENCES job_postings(job_id)     ON DELETE CASCADE,
    FOREIGN KEY (resume_id)    REFERENCES resumes(resume_id)       ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- 12) activity_log : audit trail
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS activity_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,
    event_type TEXT,
    message    TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------
-- 13) email_log : notifications sent to candidates (shortlist/interview)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER,
    recipient  TEXT,
    subject    TEXT,
    body       TEXT,
    status     TEXT DEFAULT 'queued',   -- sent/dev/failed
    detail     TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- =====================================================================
--  INDEXES
-- =====================================================================
CREATE INDEX IF NOT EXISTS idx_users_email      ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_phone      ON users(phone);
CREATE INDEX IF NOT EXISTS idx_resumes_cand     ON resumes(candidate_id);
CREATE INDEX IF NOT EXISTS idx_jobs_company     ON job_postings(company_id);
CREATE INDEX IF NOT EXISTS idx_match_resume     ON match_results(resume_id);
CREATE INDEX IF NOT EXISTS idx_match_job        ON match_results(job_id);
CREATE INDEX IF NOT EXISTS idx_match_score      ON match_results(final_score DESC);
CREATE INDEX IF NOT EXISTS idx_apps_job         ON applications(job_id);
CREATE INDEX IF NOT EXISTS idx_apps_cand        ON applications(candidate_id);

-- =====================================================================
--  VIEWS
-- =====================================================================
CREATE VIEW IF NOT EXISTS v_match_summary AS
SELECT
    m.match_id,
    c.full_name              AS candidate,
    r.title                  AS resume_title,
    j.title                  AS job_title,
    j.company                AS company,
    ROUND(m.final_score, 1)  AS final_score,
    ROUND(m.skill_score, 1)  AS skill_score,
    ROUND(m.tfidf_score, 1)  AS tfidf_score,
    ROUND(m.embedding_score,1) AS embedding_score,
    m.recommendation,
    m.matched_at
FROM match_results m
JOIN resumes      r ON r.resume_id    = m.resume_id
JOIN candidates   c ON c.candidate_id = r.candidate_id
JOIN job_postings j ON j.job_id       = m.job_id
ORDER BY m.final_score DESC;

CREATE VIEW IF NOT EXISTS v_skill_demand AS
SELECT
    s.name                       AS skill,
    s.category                   AS category,
    COUNT(DISTINCT js.job_id)    AS jobs_requiring,
    COUNT(DISTINCT rs.resume_id) AS resumes_with_skill
FROM skills s
LEFT JOIN job_skills    js ON js.skill_id = s.skill_id
LEFT JOIN resume_skills rs ON rs.skill_id = s.skill_id
GROUP BY s.skill_id
ORDER BY jobs_requiring DESC;

CREATE VIEW IF NOT EXISTS v_top_candidates AS
SELECT
    j.job_id,
    j.title      AS job_title,
    c.full_name  AS candidate,
    m.final_score,
    m.recommendation
FROM match_results m
JOIN resumes      r ON r.resume_id    = m.resume_id
JOIN candidates   c ON c.candidate_id = r.candidate_id
JOIN job_postings j ON j.job_id       = m.job_id
ORDER BY j.job_id, m.final_score DESC;

-- Admin / company overview of every application with score
CREATE VIEW IF NOT EXISTS v_applications AS
SELECT
    a.application_id,
    c.full_name            AS candidate,
    c.email                AS candidate_email,
    j.title                AS job_title,
    co.company_name        AS company,
    a.status,
    ROUND(m.final_score,1) AS match_score,
    a.applied_at
FROM applications a
JOIN candidates   c  ON c.candidate_id = a.candidate_id
JOIN job_postings j  ON j.job_id       = a.job_id
LEFT JOIN companies co ON co.company_id = j.company_id
LEFT JOIN match_results m ON m.resume_id = a.resume_id AND m.job_id = a.job_id
ORDER BY a.applied_at DESC;
