"""Shared matching runner: scores resumes against job postings and stores
results in match_results / match_skill_details."""
import database as db
import nlp_engine as nlp


def score_resume(resume_id):
    """(Re)score one resume against every job posting."""
    r = db.query_one("SELECT * FROM resumes WHERE resume_id=?", (resume_id,))
    if not r:
        return 0
    cand = db.query_one("SELECT * FROM candidates WHERE candidate_id=?",
                        (r["candidate_id"],))
    r_skill_ids = {s["skill_id"] for s in db.query(
        "SELECT skill_id FROM resume_skills WHERE resume_id=?", (resume_id,))}
    for j in db.query("SELECT * FROM job_postings"):
        job_skills = db.query(
            """SELECT js.skill_id, js.weight, s.name FROM job_skills js
               JOIN skills s USING(skill_id) WHERE js.job_id=?""", (j["job_id"],))
        tfidf = nlp.tfidf_similarity(r["raw_text"], j["description"])
        emb = nlp.embedding_similarity(r["raw_text"], j["description"])
        skill, _m, _mi = nlp.skill_overlap(r_skill_ids, job_skills)
        exp = nlp.experience_score(cand["years_experience"], j["min_experience"])
        final = nlp.blend(tfidf, emb, skill, exp)
        rec = nlp.recommend(final)

        mid = db.query_one(
            "SELECT match_id FROM match_results WHERE resume_id=? AND job_id=?",
            (resume_id, j["job_id"]))
        if mid:
            mid_id = mid["match_id"]
            db.execute("DELETE FROM match_skill_details WHERE match_id=?", (mid_id,))
            db.execute(
                """UPDATE match_results SET tfidf_score=?,embedding_score=?,
                   skill_score=?,experience_score=?,final_score=?,
                   recommendation=?,matched_at=datetime('now')
                   WHERE match_id=?""",
                (tfidf, emb, skill, exp, final, rec, mid_id))
        else:
            mid_id = db.execute(
                """INSERT INTO match_results
                   (resume_id,job_id,tfidf_score,embedding_score,skill_score,
                    experience_score,final_score,recommendation)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (resume_id, j["job_id"], tfidf, emb, skill, exp, final, rec))
        for s in job_skills:
            status = "matched" if s["skill_id"] in r_skill_ids else "missing"
            db.execute(
                "INSERT INTO match_skill_details (match_id,skill_id,status) VALUES (?,?,?)",
                (mid_id, s["skill_id"], status))
    return db.query("SELECT COUNT(*) n FROM match_results")[0]["n"]


def match_all():
    """Score every resume. Returns total number of stored matches."""
    n = 0
    for r in db.query("SELECT resume_id FROM resumes"):
        n = score_resume(r["resume_id"])
    return n
