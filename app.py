"""AI-resume_matcher  -  Flask backend + REST API (role-based auth).

Roles: candidate | company | admin   (login with email OR mobile number)

Run:  python app.py     ->  open http://127.0.0.1:5000
"""
import io
import os
import time
from datetime import timedelta

from flask import (Flask, jsonify, render_template, request, session,
                   send_from_directory)
from flask_cors import CORS
from werkzeug.utils import secure_filename

import config
import database as db
import nlp_engine as nlp
import mailer
import auth
from matcher import match_all, score_resume

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=config.SESSION_HOURS)
CORS(app, supports_credentials=True)

db.init_db()  # ensure tables exist

# Self-heal the database: if there are no login accounts at all, seed the
# demo data so the app is always usable after a reset.
if (db.query_one("SELECT COUNT(*) c FROM users") or {}).get("c", 0) == 0:
    import seed_data
    seed_data.run()


# ===================================================================== #
#  Helpers
# ===================================================================== #
def err(msg, code=400):
    return jsonify({"error": msg}), code


def current_candidate_id(user):
    prof = auth.profile_for(user)
    return prof["candidate_id"] if prof else None


def extract_text_from_file(storage):
    """Return (text, filename, size_bytes) from an uploaded file."""
    filename = secure_filename(storage.filename or "")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported file type '%s'. Allowed: %s"
                         % (ext, ", ".join(sorted(config.ALLOWED_EXTENSIONS))))
    raw = storage.read()
    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
    else:
        text = raw.decode("utf-8", errors="ignore")
    return text, filename, len(raw)


# ===================================================================== #
#  Pages
# ===================================================================== #
@app.route("/")
def index():
    return render_template("index.html")


# ===================================================================== #
#  Authentication
# ===================================================================== #
@app.post("/api/auth/register")
def register():
    d = request.get_json(force=True)
    role = (d.get("role") or "").strip()
    if role not in ("candidate", "company"):
        return err("role must be 'candidate' or 'company'")
    name = (d.get("full_name") or "").strip()
    email = (d.get("email") or "").strip() or None
    phone = (d.get("phone") or "").strip() or None
    password = d.get("password") or ""
    if not name:
        return err("full_name is required (use the HR / contact name for companies)")
    if not email and not phone:
        return err("provide an email or a mobile number")
    if len(password) < 6:
        return err("password must be at least 6 characters")
    if email and db.query_one("SELECT 1 FROM users WHERE lower(email)=lower(?)", (email,)):
        return err("email already registered")
    if phone and db.query_one("SELECT 1 FROM users WHERE phone=?", (phone,)):
        return err("mobile number already registered")

    uid = db.execute(
        """INSERT INTO users (role, full_name, email, phone, password_hash)
           VALUES (?,?,?,?,?)""",
        (role, name, email, phone, auth.hash_password(password)))

    if role == "candidate":
        db.execute(
            """INSERT INTO candidates
               (user_id, full_name, email, phone, location, years_experience, education)
               VALUES (?,?,?,?,?,?,?)""",
            (uid, name, email, phone, d.get("location"),
             float(d.get("years_experience") or 0), d.get("education")))
    else:
        cname = (d.get("company_name") or "").strip()
        if not cname:
            return err("company name is required")
        db.execute(
            """INSERT INTO companies
               (user_id, company_name, hr_name, industry, location, website, description)
               VALUES (?,?,?,?,?,?,?)""",
            (uid, cname, name, d.get("industry"), d.get("location"),
             d.get("website"), d.get("description")))

    user = db.query_one("SELECT * FROM users WHERE user_id=?", (uid,))
    auth.start_session(user)
    db.log("REGISTER", f"{role} '{name}' registered", uid)
    return jsonify({"user": auth.public_user(user),
                    "profile": auth.profile_for(user)}), 201


@app.post("/api/auth/login")
def login():
    d = request.get_json(force=True)
    ident = (d.get("identifier") or "").strip()
    password = d.get("password") or ""
    user = auth.find_user(ident)
    if not user or not auth.verify_password(password, user["password_hash"]):
        return err("invalid email/mobile or password", 401)
    if not user["is_active"]:
        return err("account disabled — contact the administrator", 403)
    auth.start_session(user)
    db.log("LOGIN", f"{user['role']} '{user['full_name']}' logged in",
           user["user_id"])
    return jsonify({"user": auth.public_user(user),
                    "profile": auth.profile_for(user)})


@app.post("/api/auth/logout")
def logout():
    u = auth.current_user()
    if u:
        db.log("LOGOUT", f"{u['full_name']} logged out", u["user_id"])
    auth.end_session()
    return jsonify({"ok": True})


@app.get("/api/me")
def me():
    user = auth.current_user()
    if not user:
        return jsonify({"user": None})
    return jsonify({"user": auth.public_user(user),
                    "profile": auth.profile_for(user)})


# ===================================================================== #
#  Dashboard stats (role-aware)
# ===================================================================== #
@app.get("/api/stats")
@auth.login_required
def stats():
    user = auth.current_user()

    def count(t):
        return db.query(f"SELECT COUNT(*) c FROM {t}")[0]["c"]

    if user["role"] == "candidate":
        cid = current_candidate_id(user)
        return jsonify({
            "role": "candidate",
            "my_matches": db.query(
                """SELECT COUNT(*) c FROM match_results m JOIN resumes r
                   ON r.resume_id=m.resume_id WHERE r.candidate_id=?""",
                (cid,))[0]["c"],
            "open_jobs": count("job_postings"),
            "avg_score": db.query(
                """SELECT ROUND(AVG(m.final_score),1) a FROM match_results m
                   JOIN resumes r ON r.resume_id=m.resume_id
                   WHERE r.candidate_id=?""", (cid,))[0]["a"] or 0,
            "applications": db.query(
                "SELECT COUNT(*) c FROM applications WHERE candidate_id=?",
                (cid,))[0]["c"],
            "best": db.query(
                """SELECT j.title AS job, co.company_name AS company,
                          ROUND(m.final_score,1) AS score, m.recommendation
                   FROM match_results m
                   JOIN resumes r ON r.resume_id=m.resume_id
                   JOIN job_postings j ON j.job_id=m.job_id
                   LEFT JOIN companies co ON co.company_id=j.company_id
                   WHERE r.candidate_id=?
                   ORDER BY m.final_score DESC LIMIT 1""", (cid,)),
        })

    if user["role"] == "company":
        comp = auth.profile_for(user)
        coid = comp["company_id"]
        return jsonify({
            "role": "company",
            "jobs": db.query("SELECT COUNT(*) c FROM job_postings WHERE company_id=?",
                             (coid,))[0]["c"],
            "applicants": db.query(
                """SELECT COUNT(DISTINCT a.candidate_id) c FROM applications a
                   JOIN job_postings j ON j.job_id=a.job_id WHERE j.company_id=?""",
                (coid,))[0]["c"],
            "avg_score": db.query(
                """SELECT ROUND(AVG(m.final_score),1) a FROM match_results m
                   JOIN job_postings j ON j.job_id=m.job_id WHERE j.company_id=?""",
                (coid,))[0]["a"] or 0,
            "total_candidates": count("candidates"),
        })

    # admin
    top = db.query("SELECT * FROM v_match_summary LIMIT 1")
    return jsonify({
        "role": "admin",
        "candidates": count("candidates"), "companies": count("companies"),
        "resumes": count("resumes"), "jobs": count("job_postings"),
        "skills": count("skills"), "matches": count("match_results"),
        "applications": count("applications"),
        "avg_score": db.query(
            "SELECT ROUND(AVG(final_score),1) a FROM match_results")[0]["a"] or 0,
        "embedding_mode": "ON" if config.USE_EMBEDDINGS else "TF-IDF + Skills",
        "best_match": top[0] if top else None,
    })


# ===================================================================== #
#  CANDIDATE
# ===================================================================== #
@app.get("/api/jobs")
def list_jobs():
    user = auth.current_user()
    q = (request.args.get("q") or "").strip()
    where = "WHERE j.is_active=1"
    params = []
    if q:
        where += " AND (j.title LIKE ? OR j.company LIKE ? OR j.description LIKE ?)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    cid = current_candidate_id(user) if user else None
    sql = f"""
        SELECT j.*, co.company_name, co.verified, co.industry,
               (SELECT ROUND(final_score,1) FROM match_results m
                  JOIN resumes r ON r.resume_id=m.resume_id
                 WHERE m.job_id=j.job_id AND r.candidate_id=?
                 ORDER BY m.final_score DESC LIMIT 1) AS my_score,
               (SELECT recommendation FROM match_results m
                  JOIN resumes r ON r.resume_id=m.resume_id
                 WHERE m.job_id=j.job_id AND r.candidate_id=?
                 ORDER BY m.final_score DESC LIMIT 1) AS my_rec,
               (SELECT COUNT(*) FROM applications a
                 WHERE a.job_id=j.job_id AND a.candidate_id=?) AS applied,
               (SELECT COUNT(*) FROM job_skills s WHERE s.job_id=j.job_id)
                 AS skill_count
        FROM job_postings j
        LEFT JOIN companies co ON co.company_id=j.company_id
        {where}
        ORDER BY j.posted_at DESC"""
    rows = db.query(sql, [cid, cid, cid, *params])
    # how many jobs this company posted (shown to companies too)
    return jsonify(rows)


@app.get("/api/job/<int:job_id>")
@auth.login_required
def job_detail(job_id):
    user = auth.current_user()
    job = db.query_one(
        """SELECT j.*, co.company_name, co.industry, co.website, co.verified
           FROM job_postings j LEFT JOIN companies co
             ON co.company_id=j.company_id WHERE j.job_id=?""", (job_id,))
    if not job:
        return err("job not found", 404)
    skills = db.query(
        """SELECT s.name, s.category, js.is_required, js.weight
           FROM job_skills js JOIN skills s USING(skill_id)
           WHERE js.job_id=? ORDER BY js.weight DESC""", (job_id,))
    my = None
    if user["role"] == "candidate":
        cid = current_candidate_id(user)
        my = db.query_one(
            """SELECT m.match_id, ROUND(m.final_score,1) AS final_score,
                      ROUND(m.skill_score,1) AS skill_score,
                      ROUND(m.tfidf_score,1) AS tfidf_score,
                      ROUND(m.embedding_score,1) AS embedding_score,
                      m.recommendation
               FROM match_results m JOIN resumes r ON r.resume_id=m.resume_id
               WHERE m.job_id=? AND r.candidate_id=?
               ORDER BY m.final_score DESC LIMIT 1""", (job_id, cid))
    return jsonify({"job": job, "skills": skills, "my_match": my})


@app.get("/api/my/matches")
@auth.role_required("candidate")
def my_matches():
    user = auth.current_user()
    cid = current_candidate_id(user)
    return jsonify(db.query(
        """SELECT j.job_id, j.title AS job_title, co.company_name AS company,
                  j.location, ROUND(m.final_score,1) AS final_score,
                  ROUND(m.skill_score,1) AS skill_score,
                  ROUND(m.tfidf_score,1) AS tfidf_score,
                  m.recommendation, m.match_id
           FROM match_results m
           JOIN resumes r ON r.resume_id=m.resume_id
           JOIN job_postings j ON j.job_id=m.job_id
           LEFT JOIN companies co ON co.company_id=j.company_id
           WHERE r.candidate_id=? AND j.is_active=1
           ORDER BY m.final_score DESC""", (cid,)))


@app.post("/api/resume")
@auth.role_required("candidate")
def upload_resume():
    """The '+' uploader: accepts a file (multipart) OR pasted text (JSON)."""
    user = auth.current_user()
    cid = current_candidate_id(user)
    prof = auth.profile_for(user)

    saved_file = None
    if "file" in request.files and request.files["file"].filename:
        storage = request.files["file"]
        try:
            text, filename, size = extract_text_from_file(storage)
        except Exception as e:
            return err(str(e))
        stored_name = f"{int(time.time())}_{filename}"
        storage.stream.seek(0)
        storage.save(os.path.join(config.UPLOAD_DIR, stored_name))
        saved_file = (filename, stored_name, size)
        form = request.form
    else:
        d = request.get_json(force=True)
        text = (d.get("text") or "").strip()
        form = d

    if not text or len(text.split()) < 10:
        return err("resume text too short — nothing to analyse")

    title = (form.get("title") or "Uploaded Resume").strip()
    years = float(form.get("years_experience") or prof["years_experience"] or 0)

    # keep only the newest resume as primary
    db.execute("UPDATE resumes SET is_primary=0 WHERE candidate_id=?", (cid,))
    rid = db.execute(
        """INSERT INTO resumes
           (candidate_id,title,raw_text,clean_text,source_file,word_count,is_primary)
           VALUES (?,?,?,?,?,?,1)""",
        (cid, title, text, nlp.clean_text(text),
         saved_file[0] if saved_file else "pasted", len(text.split())))

    if saved_file:
        db.execute(
            """INSERT INTO resume_files (resume_id,filename,stored_name,filesize,mime)
               VALUES (?,?,?,?,?)""",
            (rid, saved_file[0], saved_file[1], saved_file[2],
             "application/pdf" if saved_file[0].lower().endswith(".pdf")
             else "text/plain"))

    skills = db.extract_skill_ids(text)
    for sid, count in skills.items():
        db.execute(
            """INSERT OR IGNORE INTO resume_skills (resume_id,skill_id,mentions)
               VALUES (?,?,?)""", (rid, sid, count))

    # update experience on the profile if provided
    if form.get("years_experience") not in (None, ""):
        db.execute("UPDATE candidates SET years_experience=? WHERE candidate_id=?",
                   (years, cid))

    score_resume(rid)
    db.log("RESUME", f"{user['full_name']} uploaded a resume", user["user_id"])
    return jsonify({"ok": True, "resume_id": rid, "skills_found": len(skills),
                    "words": len(text.split())}), 201


@app.get("/api/my/resumes")
@auth.role_required("candidate")
def my_resumes():
    user = auth.current_user()
    cid = current_candidate_id(user)
    return jsonify(db.query(
        """SELECT resume_id, title, source_file, word_count, is_primary, uploaded_at
           FROM resumes WHERE candidate_id=? ORDER BY uploaded_at DESC""", (cid,)))


@app.post("/api/apply")
@auth.role_required("candidate")
def apply_job():
    user = auth.current_user()
    cid = current_candidate_id(user)
    d = request.get_json(force=True)
    job_id = d.get("job_id")
    if not job_id:
        return err("job_id required")
    if db.query_one("SELECT 1 FROM applications WHERE candidate_id=? AND job_id=?",
                    (cid, job_id)):
        return err("already applied to this job")
    res = db.query_one(
        "SELECT resume_id FROM resumes WHERE candidate_id=? ORDER BY is_primary DESC, uploaded_at DESC LIMIT 1",
        (cid,))
    db.execute(
        """INSERT INTO applications (candidate_id,job_id,resume_id,cover_note)
           VALUES (?,?,?,?)""",
        (cid, job_id, res["resume_id"] if res else None, d.get("cover_note")))
    job = db.query_one("SELECT title FROM job_postings WHERE job_id=?", (job_id,))
    db.log("APPLY", f"{user['full_name']} applied to '{job['title'] if job else job_id}'",
           user["user_id"])
    return jsonify({"ok": True}), 201


@app.get("/api/my/applications")
@auth.role_required("candidate")
def my_applications():
    user = auth.current_user()
    cid = current_candidate_id(user)
    return jsonify(db.query(
        """SELECT a.application_id, j.title AS job_title,
                  co.company_name AS company, a.status,
                  ROUND(m.final_score,1) AS match_score, a.applied_at
           FROM applications a
           JOIN job_postings j ON j.job_id=a.job_id
           LEFT JOIN companies co ON co.company_id=j.company_id
           LEFT JOIN match_results m ON m.resume_id=a.resume_id AND m.job_id=a.job_id
           WHERE a.candidate_id=? ORDER BY a.applied_at DESC""", (cid,)))


# ===================================================================== #
#  COMPANY
# ===================================================================== #
@app.get("/api/company/jobs")
@auth.role_required("company")
def company_jobs():
    user = auth.current_user()
    coid = auth.profile_for(user)["company_id"]
    return jsonify(db.query(
        """SELECT j.*,
             (SELECT COUNT(*) FROM applications a WHERE a.job_id=j.job_id)
               AS applicants,
             (SELECT ROUND(AVG(final_score),1) FROM match_results m
               WHERE m.job_id=j.job_id) AS avg_score,
             (SELECT COUNT(*) FROM job_skills s WHERE s.job_id=j.job_id)
               AS skill_count
           FROM job_postings j WHERE j.company_id=? ORDER BY j.posted_at DESC""",
        (coid,)))


@app.post("/api/company/jobs")
@auth.role_required("company")
def create_job():
    user = auth.current_user()
    comp = auth.profile_for(user)
    d = request.get_json(force=True)
    title = (d.get("title") or "").strip()
    desc = (d.get("description") or "").strip()
    if not title or not desc:
        return err("title and description are required")
    jid = db.execute(
        """INSERT INTO job_postings
           (company_id,title,company,location,description,clean_text,
            min_experience,salary,employment_type)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (comp["company_id"], title, comp["company_name"],
         d.get("location") or comp["location"], desc, nlp.clean_text(desc),
         float(d.get("min_experience") or 0), d.get("salary"),
         d.get("employment_type") or "Full-time"))

    # skills: either explicit list or auto-extracted from the description
    names = d.get("skills") or []
    if isinstance(names, str):
        names = [s.strip() for s in names.split(",") if s.strip()]
    if not names:
        found = db.extract_skill_ids(desc)
        names = [db.query_one("SELECT name FROM skills WHERE skill_id=?", (sid,))["name"]
                 for sid in found]
    for nm in names:
        row = db.query_one("SELECT skill_id FROM skills WHERE lower(name)=lower(?)", (nm,))
        if row:
            sid = row["skill_id"]
        else:
            sid = db.execute("INSERT INTO skills (name, category) VALUES (?, 'Other')", (nm,))
        db.execute(
            """INSERT OR IGNORE INTO job_skills (job_id,skill_id,is_required,weight)
               VALUES (?,?,1,1.0)""", (jid, sid))

    match_all()  # score all resumes against the new job
    db.log("JOB", f"{user['full_name']} posted '{title}'", user["user_id"])
    return jsonify({"ok": True, "job_id": jid, "skills": names}), 201


@app.delete("/api/company/jobs/<int:job_id>")
@auth.role_required("company")
def delete_job(job_id):
    user = auth.current_user()
    coid = auth.profile_for(user)["company_id"]
    job = db.query_one("SELECT * FROM job_postings WHERE job_id=?", (job_id,))
    if not job or job["company_id"] != coid:
        return err("job not found for your company", 404)
    db.execute("DELETE FROM job_postings WHERE job_id=?", (job_id,))
    db.log("JOB", f"{user['full_name']} deleted job #{job_id}", user["user_id"])
    return jsonify({"ok": True})


@app.get("/api/company/jobs/<int:job_id>/applicants")
@auth.role_required("company")
def job_applicants(job_id):
    """All candidates ranked by AI match score for one of my jobs."""
    user = auth.current_user()
    coid = auth.profile_for(user)["company_id"]
    job = db.query_one("SELECT * FROM job_postings WHERE job_id=?", (job_id,))
    if not job or job["company_id"] != coid:
        return err("job not found for your company", 404)
    rows = db.query(
        """SELECT m.match_id, c.candidate_id, c.full_name AS candidate,
                  c.email, c.location, c.years_experience,
                  r.title AS resume_title,
                  ROUND(m.final_score,1) AS final_score,
                  ROUND(m.skill_score,1) AS skill_score,
                  ROUND(m.tfidf_score,1) AS tfidf_score,
                  ROUND(m.embedding_score,1) AS embedding_score,
                  ROUND(m.experience_score,1) AS experience_score,
                  m.recommendation,
                  a.application_id, a.status AS application_status
           FROM match_results m
           JOIN resumes r ON r.resume_id=m.resume_id
           JOIN candidates c ON c.candidate_id=r.candidate_id
           LEFT JOIN applications a ON a.candidate_id=c.candidate_id
                 AND a.job_id=m.job_id
           WHERE m.job_id=?
           ORDER BY m.final_score DESC""", (job_id,))
    return jsonify({"job": job, "applicants": rows})


@app.get("/api/match/<int:match_id>")
@auth.login_required
def match_detail(match_id):
    user = auth.current_user()
    m = db.query_one(
        """SELECT m.*, j.title AS job_title, j.company, j.company_id,
                  j.description, c.full_name AS candidate,
                  r.raw_text, r.title AS resume_title, r.resume_id
           FROM match_results m
           JOIN resumes r ON r.resume_id=m.resume_id
           JOIN candidates c ON c.candidate_id=r.candidate_id
           JOIN job_postings j ON j.job_id=m.job_id
           WHERE m.match_id=?""", (match_id,))
    if not m:
        return err("match not found", 404)
    # access control: candidate owns it, company owns the job, admin sees all
    if user["role"] == "candidate":
        if m["candidate"] != user["full_name"]:
            return err("forbidden", 403)
    elif user["role"] == "company":
        if m["company_id"] != auth.profile_for(user)["company_id"]:
            return err("forbidden", 403)
    details = db.query(
        """SELECT s.name AS skill, s.category, d.status, js.weight, js.is_required
           FROM match_skill_details d
           JOIN skills s USING(skill_id)
           JOIN job_skills js ON js.job_id=? AND js.skill_id=d.skill_id
           WHERE d.match_id=?""", (m["job_id"], match_id))
    return jsonify({
        "summary": {
            "match_id": m["match_id"], "candidate": m["candidate"],
            "job_title": m["job_title"], "company": m["company"],
            "resume_title": m["resume_title"],
            "final_score": round(m["final_score"], 1),
            "skill_score": round(m["skill_score"], 1),
            "tfidf_score": round(m["tfidf_score"], 1),
            "embedding_score": m["embedding_score"],
            "recommendation": m["recommendation"],
        },
        "resume_text": m["raw_text"],
        "skills": details,
        "matched": [d["skill"] for d in details if d["status"] == "matched"],
        "missing": [d["skill"] for d in details if d["status"] == "missing"],
    })


@app.get("/api/company/applications")
@auth.role_required("company")
def company_applications():
    user = auth.current_user()
    coid = auth.profile_for(user)["company_id"]
    return jsonify(db.query(
        """SELECT a.application_id, c.full_name AS candidate,
                  j.title AS job_title, a.status,
                  ROUND(m.final_score,1) AS match_score, a.applied_at
           FROM applications a
           JOIN candidates c ON c.candidate_id=a.candidate_id
           JOIN job_postings j ON j.job_id=a.job_id
           LEFT JOIN match_results m ON m.resume_id=a.resume_id AND m.job_id=a.job_id
           WHERE j.company_id=? ORDER BY a.applied_at DESC""", (coid,)))


@app.patch("/api/company/applications/<int:app_id>")
@auth.role_required("company")
def update_application(app_id):
    user = auth.current_user()
    coid = auth.profile_for(user)["company_id"]
    d = request.get_json(force=True)
    status = d.get("status")
    if status not in ("submitted", "reviewed", "shortlisted", "rejected"):
        return err("invalid status")
    row = db.query_one(
        """SELECT a.application_id, a.status AS prev_status FROM applications a
           JOIN job_postings j ON j.job_id=a.job_id
           WHERE a.application_id=? AND j.company_id=?""", (app_id, coid))
    if not row:
        return err("application not found", 404)
    db.execute("UPDATE applications SET status=? WHERE application_id=?",
               (status, app_id))

    email_result = None
    if status == "shortlisted" and row["prev_status"] != "shortlisted":
        email_result = _send_shortlist_email(app_id, user)

    return jsonify({"ok": True, "status": status, "email": email_result})


def _send_shortlist_email(app_id, user):
    """Email the candidate a professional interview invitation."""
    info = db.query_one(
        """SELECT c.full_name AS candidate_name, c.email AS candidate_email,
                  j.title AS job_title, j.location AS job_location,
                  co.company_name, co.hr_name,
                  co.location AS company_location, co.website
           FROM applications a
           JOIN candidates c   ON c.candidate_id = a.candidate_id
           JOIN job_postings j ON j.job_id = a.job_id
           JOIN companies co   ON co.company_id = j.company_id
           WHERE a.application_id=?""", (app_id,))
    if not info:
        return {"sent": False, "status": "skipped", "detail": "application not found"}

    recipient = info.get("candidate_email")
    subject, text, html = mailer.build_shortlist_email(
        candidate=info["candidate_name"], job_title=info["job_title"],
        company_name=info["company_name"], hr_name=info["hr_name"],
        location=info.get("job_location") or info.get("company_location"),
        website=info.get("website"))
    sent, detail = mailer.send_email(recipient, subject, text, html)
    status = "sent" if sent else ("failed" if mailer.email_configured() else "dev")
    if status == "dev":
        detail = "SMTP not configured — logged to console and email_log"
        print(f"\n[email] interview invitation -> {recipient}\n"
              f"Subject: {subject}\n{text}\n", flush=True)
    db.execute(
        """INSERT INTO email_log
             (application_id, recipient, subject, body, status, detail)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (app_id, recipient, subject, text, status, detail))
    db.log("email_shortlist",
           f"Interview email to {recipient or '(no email on file)'} [{status}]",
           user["user_id"])
    return {"recipient": recipient, "sent": sent, "status": status, "detail": detail}


# ===================================================================== #
#  ADMIN
# ===================================================================== #
@app.get("/api/admin/candidates")
@auth.role_required("admin")
def admin_candidates():
    return jsonify(db.query(
        """SELECT c.*, u.is_active, u.created_at AS joined,
                  (SELECT COUNT(*) FROM resumes r WHERE r.candidate_id=c.candidate_id)
                    AS resume_count,
                  (SELECT COUNT(*) FROM applications a WHERE a.candidate_id=c.candidate_id)
                    AS applications
           FROM candidates c JOIN users u ON u.user_id=c.user_id
           ORDER BY c.full_name"""))


@app.get("/api/admin/companies")
@auth.role_required("admin")
def admin_companies():
    return jsonify(db.query(
        """SELECT co.*, u.is_active, u.email AS login_email, u.phone,
                  (SELECT COUNT(*) FROM job_postings j WHERE j.company_id=co.company_id)
                    AS job_count
           FROM companies co JOIN users u ON u.user_id=co.user_id
           ORDER BY co.company_name"""))


@app.get("/api/admin/users")
@auth.role_required("admin")
def admin_users():
    return jsonify(db.query(
        """SELECT user_id, role, full_name, email, phone, is_active, created_at
           FROM users ORDER BY role, full_name"""))


@app.get("/api/admin/applications")
@auth.role_required("admin")
def admin_applications():
    return jsonify(db.query("SELECT * FROM v_applications"))


@app.post("/api/admin/users/<int:user_id>/toggle")
@auth.role_required("admin")
def admin_toggle(user_id):
    u = db.query_one("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not u:
        return err("user not found", 404)
    if u["role"] == "admin":
        return err("cannot disable an admin account")
    db.execute("UPDATE users SET is_active=? WHERE user_id=?",
               (0 if u["is_active"] else 1, user_id))
    db.log("ADMIN", f"toggled user #{user_id} ({u['full_name']})")
    return jsonify({"ok": True, "is_active": 0 if u["is_active"] else 1})


@app.delete("/api/admin/users/<int:user_id>")
@auth.role_required("admin")
def admin_delete_user(user_id):
    u = db.query_one("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not u:
        return err("user not found", 404)
    if u["role"] == "admin":
        return err("cannot delete an admin account")
    if u["role"] == "company":
        db.execute("DELETE FROM companies WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM users WHERE user_id=?", (user_id,))
    db.log("ADMIN", f"deleted user #{user_id} ({u['full_name']})")
    return jsonify({"ok": True})


@app.post("/api/admin/companies/<int:company_id>/verify")
@auth.role_required("admin")
def admin_verify(company_id):
    co = db.query_one("SELECT * FROM companies WHERE company_id=?", (company_id,))
    if not co:
        return err("company not found", 404)
    db.execute("UPDATE companies SET verified=? WHERE company_id=?",
               (0 if co["verified"] else 1, company_id))
    return jsonify({"ok": True, "verified": 0 if co["verified"] else 1})


# ===================================================================== #
#  Analytics + SQL report
# ===================================================================== #
@app.get("/api/skill_demand")
@auth.login_required
def skill_demand():
    return jsonify(db.query("SELECT * FROM v_skill_demand"))


@app.get("/api/activity")
@auth.login_required
def activity():
    return jsonify(db.query(
        """SELECT a.*, u.full_name AS actor FROM activity_log a
           LEFT JOIN users u ON u.user_id=a.user_id
           ORDER BY a.id DESC LIMIT 25"""))


@app.get("/api/tables")
@auth.role_required("admin")
def tables():
    out = []
    for name in db.list_tables():
        cols = db.table_columns(name)
        cnt = db.query(f"SELECT COUNT(*) c FROM `{name}`")[0]["c"]
        out.append({"name": name, "rows": cnt, "columns": cols})
    return jsonify({"tables": out, "views": db.list_views()})


@app.post("/api/sql")
@auth.role_required("admin")
def run_sql():
    q = (request.get_json(force=True).get("query") or "").strip()
    if not q:
        return err("empty query")
    if not q.lower().startswith(("select", "with", "show", "describe",
                                 "desc", "pragma")):
        return err("Only read-only SELECT / SHOW / DESCRIBE queries are allowed.")
    try:
        rows = db.query(q)
        cols = list(rows[0].keys()) if rows else []
        return jsonify({"columns": cols, "rows": rows, "count": len(rows)})
    except Exception as exc:
        return err(str(exc))


@app.post("/api/rematch")
@auth.role_required("admin")
def rematch():
    n = match_all()
    db.log("REMATCH", "Admin re-ran the matching engine")
    return jsonify({"ok": True, "matches": n})


# ---- admin: email (SMTP) settings -----------------------------------
@app.get("/api/admin/mail-settings")
@auth.role_required("admin")
def get_mail_settings():
    s = mailer.effective()
    return jsonify({
        "host": s["host"], "port": s["port"], "user": s["user"],
        "from": s["from"], "from_name": s["from_name"], "tls": s["tls"],
        "has_password": bool(s["password"]),
        "configured": mailer.email_configured(),
    })


@app.post("/api/admin/mail-settings")
@auth.role_required("admin")
def save_mail_settings():
    d = request.get_json(force=True)
    saved = mailer.load_saved()
    for key in ("host", "user", "from", "from_name"):
        if key in d:
            saved[key] = (d.get(key) or "").strip()
    if d.get("port"):
        saved["port"] = int(d["port"])
    if "tls" in d:
        saved["tls"] = bool(d["tls"])
    # only overwrite the password when a new one is supplied
    if (d.get("password") or "").strip():
        saved["password"] = d["password"].strip()
    mailer.save_settings(saved)
    db.log("MAIL_SETTINGS", "Admin updated email (SMTP) settings",
           auth.current_user()["user_id"])
    return jsonify({"ok": True, "configured": mailer.email_configured()})


@app.post("/api/admin/mail-settings/test")
@auth.role_required("admin")
def test_mail_settings():
    to = (request.get_json(force=True).get("to") or "").strip()
    if not to:
        return err("enter a recipient address for the test")
    subject = "HireMatch test email"
    text = ("This is a test message from HireMatch. If you received it, your "
            "email settings are working — shortlisted candidates will now get "
            "interview invitations automatically.")
    sent, detail = mailer.send_email(to, subject, text)
    if sent:
        return jsonify({"ok": True, "detail": "sent"})
    return err(f"could not send: {detail}")


# ===================================================================== #
#  File download (recruiters / admin can read uploaded resumes)
# ===================================================================== #
@app.get("/api/file/<int:file_id>")
@auth.login_required
def download_file(file_id):
    user = auth.current_user()
    if user["role"] not in ("company", "admin"):
        return err("forbidden", 403)
    f = db.query_one("SELECT * FROM resume_files WHERE file_id=?", (file_id,))
    if not f:
        return err("file not found", 404)
    return send_from_directory(config.UPLOAD_DIR, f["stored_name"],
                               as_attachment=True, download_name=f["filename"])


# --------------------------------------------------------------------- #
if __name__ == "__main__":
    print(f"  AI-resume_matcher running -> http://{config.HOST}:{config.PORT}")
    print("  Logins: admin@resume.com | aarav.sharma@example.com | hr@neurotech.ai")
    print(f"  Password for all demo accounts: {config.DEFAULT_PASSWORD}")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
