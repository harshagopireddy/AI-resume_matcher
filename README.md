# AI Resume Matcher

An end-to-end **resume ⇄ job matching** platform with **login, 3 user roles,
resume upload, and admin management**, built with **NLP, AI, Data Science and SQL**.

```
NLP        ->  text cleaning, tokenising, stemming, TF-IDF + cosine similarity
AI / ML    ->  sentence-transformer embeddings (optional) for semantic similarity
Data Sci   ->  weighted skill-overlap, experience-fit, blended scoring, analytics
SQL        ->  MySQL (device) or SQLite: 14 tables + 4 reporting views + live SQL runner
Auth       ->  login by EMAIL or MOBILE, roles: candidate / company / admin
Notify     ->  auto interview-invitation email when a company shortlists a candidate
```

---

## 1. Quick start (Windows)

```bat
cd "C:\Users\hgopi\onedrive personal\OneDrive\Desktop\resume\AI-resume_matcher"
python seed_data.py      :: build the DB + sample data + demo logins (already done)
python app.py            :: start the server
```

Then open **http://127.0.0.1:5000** and log in.
Or double-click **run.bat**.

> If double-clicking `run.bat` opens it in VS Code, right-click → **Open with →
> Windows Command Processor**, or open a terminal in the folder and type `run.bat`.

To reinstall dependencies anywhere:

```bat
pip install -r requirements.txt
```

### Enable true AI embeddings (optional)

```bat
pip install sentence-transformers
set USE_EMBEDDINGS=1
python seed_data.py
python app.py
```

### Interview emails (optional)

When a company **accepts (shortlists)** an application, the candidate is sent a
professional interview-invitation email (position, venue, HR contact). No email
is sent until SMTP is configured — until then the message is printed to the
console and stored in the `email_log` table.

```bat
set SMTP_USER=you@gmail.com
set SMTP_PASSWORD=your_app_password   :: Gmail: enable 2-Step + use an App password
set SMTP_FROM=you@gmail.com           :: optional, defaults to SMTP_USER
python app.py
```

Or set `SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD` in `config.py`.

### Keeping secrets out of Git

Secrets are never committed. Put machine-specific values (MySQL password,
`SECRET_KEY`, SMTP credentials) in a local, git-ignored `config_local.py`:

```py
# config_local.py  (created by you, git-ignored)
MYSQL_PASSWORD = "your-mysql-password"
SECRET_KEY     = "a-long-random-string"
SMTP_USER      = "you@gmail.com"
SMTP_PASSWORD  = "your-app-password"
```

`config.py` loads `config_local.py` automatically if it exists (environment
variables still take priority). The `data/` folder, the database file and
`.env` are also git-ignored.

---

## 2. Demo logins

All demo accounts use the password **`password123`**.
Login works with **either** the email **or** the mobile number.

| Role      | Email / Mobile                    | Can do |
|-----------|-----------------------------------|--------|
| **Admin** | `admin@resume.com` / `+91-90000-00001` | Manage candidates AND companies, verify companies, view all users/analytics/SQL |
| **Candidate** | `aarav.sharma@example.com` / `+91-98765-43210` | Browse jobs, upload resume (the **+** button), see match scores, apply |
| **Company**   | `hr@neurotech.ai` / `+91-90000-00011`          | Post jobs, view ranked applicants, update application status |

Other seeded candidates: `meera.nair@example.com`, `rohan.verma@example.com`,
`sara.khan@example.com`, `vikram.rao@example.com` — all `password123`.
Other companies: `careers@insightanalytics.com`, `jobs@cloudscale.io`,
`talent@pixelworks.dev`, `team@brightdata.co` — all `password123`.

You can also **register** a new candidate or company from the login screen.

---

## 3. Roles & features

### Candidate
- **+ button (floating)** to upload a resume — drag & drop **.txt / .pdf / .md / .csv**
  or paste text; skills are auto-extracted and scored instantly.
- **Browse Jobs** with live search; each card shows *your* match %.
- **My Matches** – all jobs ranked by your resume score, click for matched/missing skills.
- **My Applications** with status tracking.

### Company
- **Post a Job** – skills can be typed or auto-detected from the description.
- **My Jobs** – applicant counts + average match score, delete jobs.
- **Applicants** – every candidate ranked by the AI match score, with **Accept / Reject** buttons per application.
- **Applications** – review and update status (submitted / reviewed / shortlisted / rejected).

### Admin
- **Candidates** – enable/disable or delete candidate accounts.
- **Companies** – verify/unverify, enable/disable, delete company accounts.
- **All Users** – every login in one table.
- **Applications** – global view across all companies.
- **Analytics** + **SQL Report** over the whole database.

---

## 4. Project structure

```
AI-resume_matcher/
├── app.py              Flask backend + REST API (auth + role routes)
├── auth.py             password hashing, sessions, role guards
├── config.py           weights, DB backend, SMTP, upload settings, secret key
├── database.py         MySQL / SQLite dual-backend access layer + skill extraction
├── mailer.py           SMTP email delivery (interview invitations)
├── nlp_engine.py       NLP / AI / Data-Science scoring engine
├── matcher.py          shared scoring runner
├── schema.sql          ALL SQL tables, indexes and views
├── seed_data.py        sample data + users/companies + runs the matcher
├── requirements.txt
├── run.bat             one-click launcher
├── data/               (git-ignored, generated locally)
│   ├── resume_matcher.db   the SQLite database (generated)
│   └── uploads/            files uploaded via the + button
├── templates/index.html
└── static/{css/style.css, js/app.js}
```

---

## 5. How the score is calculated

| Component      | Weight | Technique                        |
|----------------|--------|----------------------------------|
| TF-IDF         | 0.35   | NLP keyword relevance            |
| Embedding      | 0.25   | AI semantic similarity (optional)|
| Skill overlap  | 0.30   | weighted Data-Science overlap    |
| Experience fit | 0.10   | years vs. required               |

`final_score` (0–100) is labelled **Excellent ≥80, Good ≥60, Fair ≥40, else Poor**.

---

## 6. Where is the data? (SQL)

The app runs on **MySQL by default** (your device, database `resume_matcher1`).
Set `DB_BACKEND=sqlite` in an environment variable (or `config.py`) to use the
portable SQLite file instead. SQL is **admin-only** in the UI.

---

## 7. MySQL on your device (`resume_matcher1`)

The app targets **MySQL 8.0** by default (database **`resume_matcher1`**, same
**14 tables + 4 views** as SQLite). The `mysql/` helper scripts shipped with
this project were removed from the repo — create the schema yourself from
`schema.sql` (or run with `DB_BACKEND=sqlite`, which needs no server), then
point `config_local.py` at MySQL with your credentials.

Use **MySQL Workbench 8.0** → connect to `localhost`, open the
`resume_matcher1` schema. The Flask app reads/writes MySQL directly, so
everything registered through the website appears there instantly.
