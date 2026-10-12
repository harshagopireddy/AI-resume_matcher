"""Initialise the database and load rich sample data (with logins).

Run:  python seed_data.py
"""
import config
import database as db
import nlp_engine as nlp
from auth import hash_password
from matcher import match_all


SKILLS = [
    ("Python", "Programming", "py|python3"),
    ("Java", "Programming", ""),
    ("JavaScript", "Programming", "js|ecmascript"),
    ("TypeScript", "Programming", "ts"),
    ("C++", "Programming", "cpp"),
    ("SQL", "Databases", "mysql|postgresql|postgres|sqlite|t-sql"),
    ("NoSQL", "Databases", "mongodb|mongo|redis|cassandra"),
    ("Machine Learning", "Data Science", "ml"),
    ("Deep Learning", "Data Science", "dl|neural networks"),
    ("NLP", "Data Science", "natural language processing"),
    ("Data Science", "Data Science", "datascience"),
    ("Pandas", "Data Science", "pandas library"),
    ("NumPy", "Data Science", "numpy library"),
    ("Scikit-learn", "Data Science", "sklearn|scikit learn"),
    ("TensorFlow", "Data Science", "tf"),
    ("PyTorch", "Data Science", "torch"),
    ("Statistics", "Data Science", "statistical analysis"),
    ("Data Visualization", "Data Science", "matplotlib|seaborn|plotly"),
    ("Power BI", "Data Science", "powerbi"),
    ("Tableau", "Data Science", ""),
    ("Excel", "Data Science", "ms excel|microsoft excel"),
    ("Flask", "Web", ""),
    ("Django", "Web", ""),
    ("React", "Web", "reactjs|react.js"),
    ("Node.js", "Web", "nodejs|node"),
    ("REST API", "Web", "restful|rest apis"),
    ("Docker", "DevOps", "containerization"),
    ("Kubernetes", "DevOps", "k8s"),
    ("AWS", "Cloud", "amazon web services"),
    ("Azure", "Cloud", "microsoft azure"),
    ("GCP", "Cloud", "google cloud"),
    ("Git", "DevOps", "github|gitlab"),
    ("Agile", "Soft Skills", "scrum"),
    ("Communication", "Soft Skills", ""),
    ("Teamwork", "Soft Skills", "collaboration"),
    ("Problem Solving", "Soft Skills", "analytical thinking"),
    ("Spark", "Big Data", "apache spark|pyspark"),
    ("Hadoop", "Big Data", ""),
    ("ETL", "Big Data", "extract transform load"),
    ("Airflow", "Big Data", "apache airflow"),
]

# (full_name, email, phone, location, years, education)
CANDIDATES = [
    ("Aarav Sharma", "aarav.sharma@example.com", "+91-98765-43210",
     "Bengaluru, India", 6, "M.Tech Computer Science"),
    ("Meera Nair", "meera.nair@example.com", "+91-91234-56789",
     "Kochi, India", 4, "B.Tech Information Technology"),
    ("Rohan Verma", "rohan.verma@example.com", "+91-99887-76655",
     "Pune, India", 8, "M.Sc Statistics"),
    ("Sara Khan", "sara.khan@example.com", "+91-90012-34567",
     "Hyderabad, India", 2, "B.Sc Data Science"),
    ("Vikram Rao", "vikram.rao@example.com", "+91-97654-32109",
     "Chennai, India", 5, "B.E Computer Engineering"),
]

RESUMES = [
    (0, "Senior Machine Learning Engineer", """
Aarav Sharma - Senior Machine Learning Engineer with 6 years of experience.
Expert in Python, TensorFlow, PyTorch and deep learning. Built NLP pipelines for
resume parsing and text classification using Scikit-learn and NLTK. Strong in SQL
and NoSQL databases, data science, Pandas, NumPy and statistics. Deployed models
with Docker and Kubernetes on AWS. Experience with Spark for big data ETL.
Familiar with REST API development using Flask. Agile, good communication and
problem solving skills.
"""),
    (1, "Data Scientist", """
Meera Nair - Data Scientist with 4 years building predictive models.
Skilled in Python, Pandas, NumPy, Scikit-learn, statistics and data visualization
with Matplotlib and Tableau. Experience with machine learning, SQL and ETL.
Built dashboards in Power BI. Worked in Agile teams, strong communication and
teamwork. Some experience with NLP text analytics.
"""),
    (2, "Data Engineer / Big Data", """
Rohan Verma - Data Engineer with 8 years. Expert in SQL, Python, Spark, Hadoop and
Airflow building large scale ETL pipelines. Strong AWS and Azure cloud experience,
Docker and Kubernetes. Worked with NoSQL stores like MongoDB and Cassandra.
Data science background with statistics and Pandas. Excellent teamwork and
problem solving.
"""),
    (3, "Junior Data Analyst", """
Sara Khan - Junior Data Analyst with 2 years experience. Proficient in SQL, Excel,
Power BI and Tableau. Basic Python, Pandas and NumPy for data analysis and
data visualization. Learning machine learning and statistics. Good communication
and eager to learn.
"""),
    (4, "Full Stack Developer with ML interest", """
Vikram Rao - Full Stack Developer with 5 years. Strong in JavaScript, TypeScript,
React, Node.js and REST API design. Backend experience with Python, Django and
Flask. Worked with SQL and NoSQL databases, Docker, Git and AWS. Recently built
machine learning features using Scikit-learn and basic NLP. Agile team player.
"""),
]

# (title, company, location, min_exp, description)
JOBS = [
    ("Senior Machine Learning Engineer", "NeuroTech AI", "Bengaluru, India", 5, """
We are hiring a Senior Machine Learning Engineer to build NLP and deep learning
systems. Must have strong Python, TensorFlow or PyTorch, Machine Learning,
Deep Learning and NLP. Experience with Scikit-learn, Pandas, NumPy, SQL and
deploying models using Docker, Kubernetes on AWS required. Spark and ETL a plus.
"""),
    ("Data Scientist", "Insight Analytics", "Remote", 3, """
Seeking a Data Scientist to turn data into decisions. Requirements: Python,
Pandas, NumPy, Scikit-learn, Statistics, Machine Learning and Data Visualization
(Tableau or Power BI). Strong SQL and communication skills. NLP experience is a
bonus. Agile environment.
"""),
    ("Data Engineer", "CloudScale", "Hyderabad, India", 4, """
Data Engineer needed to build large scale pipelines. Must have SQL, Python, Spark,
Hadoop, Airflow and ETL. Cloud experience with AWS or Azure, plus Docker and
Kubernetes. NoSQL knowledge (MongoDB) required. Git and Agile teamwork expected.
"""),
    ("Frontend Developer", "PixelWorks", "Pune, India", 2, """
Frontend Developer to craft beautiful web apps. Requirements: JavaScript,
TypeScript, React, Node.js and REST API integration. Familiarity with Git, Docker
and SQL helpful. Good communication and teamwork required.
"""),
    ("Junior Data Analyst", "BrightData", "Chennai, India", 0, """
Junior Data Analyst role for a detail oriented person. Must know SQL, Excel,
Power BI or Tableau and Data Visualization. Basic Python, Pandas and NumPy.
Statistics knowledge preferred. Good communication skills.
"""),
]

# company_name -> (email, phone, industry, website, location, HR contact name)
COMPANIES = {
    "NeuroTech AI": ("hr@neurotech.ai", "+91-90000-00011", "Artificial Intelligence",
                     "https://neurotech.example.com", "Bengaluru, India", "Priya Menon"),
    "Insight Analytics": ("careers@insightanalytics.com", "+91-90000-00012",
                          "Analytics", "https://insight.example.com", "Remote", "David Fernandes"),
    "CloudScale": ("jobs@cloudscale.io", "+91-90000-00013", "Cloud / Big Data",
                   "https://cloudscale.example.com", "Hyderabad, India", "Ananya Iyer"),
    "PixelWorks": ("talent@pixelworks.dev", "+91-90000-00014", "Web / Design",
                   "https://pixelworks.example.com", "Pune, India", "Kabir Singh"),
    "BrightData": ("team@brightdata.co", "+91-90000-00015", "Data Services",
                   "https://brightdata.example.com", "Chennai, India", "Nisha Reddy"),
}

JOB_SKILLS = {
    "Senior Machine Learning Engineer": [
        ("Python", 1, 2.0), ("TensorFlow", 1, 1.5), ("PyTorch", 1, 1.5),
        ("Machine Learning", 1, 2.0), ("Deep Learning", 1, 1.5), ("NLP", 1, 1.5),
        ("Scikit-learn", 1, 1.0), ("Pandas", 1, 1.0), ("NumPy", 1, 1.0),
        ("SQL", 1, 1.0), ("Docker", 0, 0.8), ("Kubernetes", 0, 0.8),
        ("AWS", 0, 1.0), ("Spark", 0, 0.6), ("ETL", 0, 0.6),
    ],
    "Data Scientist": [
        ("Python", 1, 2.0), ("Pandas", 1, 1.0), ("NumPy", 1, 1.0),
        ("Scikit-learn", 1, 1.5), ("Statistics", 1, 1.5),
        ("Machine Learning", 1, 2.0), ("Data Visualization", 1, 1.0),
        ("Tableau", 0, 0.8), ("Power BI", 0, 0.8), ("SQL", 1, 1.5),
        ("Communication", 1, 1.0), ("NLP", 0, 0.6), ("Agile", 0, 0.5),
    ],
    "Data Engineer": [
        ("SQL", 1, 2.0), ("Python", 1, 1.5), ("Spark", 1, 2.0),
        ("Hadoop", 1, 1.0), ("Airflow", 1, 1.0), ("ETL", 1, 1.5),
        ("AWS", 1, 1.0), ("Azure", 0, 0.8), ("Docker", 1, 0.8),
        ("Kubernetes", 0, 0.8), ("NoSQL", 1, 1.0), ("Git", 1, 0.5),
        ("Agile", 0, 0.5),
    ],
    "Frontend Developer": [
        ("JavaScript", 1, 2.0), ("TypeScript", 1, 1.5), ("React", 1, 2.0),
        ("Node.js", 1, 1.0), ("REST API", 1, 1.0), ("Git", 1, 0.5),
        ("Docker", 0, 0.6), ("SQL", 0, 0.6), ("Communication", 1, 1.0),
        ("Teamwork", 1, 0.8),
    ],
    "Junior Data Analyst": [
        ("SQL", 1, 2.0), ("Excel", 1, 1.5), ("Power BI", 1, 1.5),
        ("Tableau", 0, 0.8), ("Data Visualization", 1, 1.0),
        ("Python", 0, 1.0), ("Pandas", 0, 0.8), ("NumPy", 0, 0.8),
        ("Statistics", 0, 1.0), ("Communication", 1, 1.0),
    ],
}


def run():
    print("Initialising database ...")
    db.init_db(reset=True)

    # -- admin --------------------------------------------------------
    db.execute(
        """INSERT INTO users (role, full_name, email, phone, password_hash)
           VALUES ('admin','Platform Admin','admin@resume.com','+91-90000-00001',?)""",
        (hash_password(config.DEFAULT_PASSWORD),))
    db.log("SEED", "Admin account created")

    # -- skills -------------------------------------------------------
    for name, cat, aliases in SKILLS:
        db.execute("INSERT INTO skills (name, category, aliases) VALUES (?,?,?)",
                   (name, cat, aliases))
    print(f"  inserted {len(SKILLS)} skills")

    # -- candidate users + profiles + resumes ------------------------
    for i, (name, email, phone, loc, yrs, edu) in enumerate(CANDIDATES):
        uid = db.execute(
            """INSERT INTO users (role, full_name, email, phone, password_hash)
               VALUES ('candidate',?,?,?,?)""",
            (name, email, phone, hash_password(config.DEFAULT_PASSWORD)))
        cid = db.execute(
            """INSERT INTO candidates
               (user_id,full_name,email,phone,location,years_experience,education)
               VALUES (?,?,?,?,?,?,?)""",
            (uid, name, email, phone, loc, yrs, edu))
        title, text = RESUMES[i][1], RESUMES[i][2]
        rid = db.execute(
            """INSERT INTO resumes
               (candidate_id,title,raw_text,clean_text,source_file,word_count)
               VALUES (?,?,?,?,?,?)""",
            (cid, title, text, nlp.clean_text(text), f"resume_{cid}.txt",
             len(text.split())))
        for sid, count in db.extract_skill_ids(text).items():
            db.execute(
                """INSERT OR IGNORE INTO resume_skills
                   (resume_id, skill_id, mentions) VALUES (?,?,?)""",
                (rid, sid, count))
    print(f"  inserted {len(CANDIDATES)} candidates (users + profiles + resumes)")

    # -- company users + profiles ------------------------------------
    company_ids = {}
    for name, (email, phone, industry, site, loc, hr) in COMPANIES.items():
        uid = db.execute(
            """INSERT INTO users (role, full_name, email, phone, password_hash)
               VALUES ('company',?,?,?,?)""",
            (hr, email, phone, hash_password(config.DEFAULT_PASSWORD)))
        coid = db.execute(
            """INSERT INTO companies
               (user_id,company_name,hr_name,industry,location,website,verified)
               VALUES (?,?,?,?,?,?,1)""",
            (uid, name, hr, industry, loc, site))
        company_ids[name] = coid
    print(f"  inserted {len(COMPANIES)} companies (users + profiles)")

    # -- jobs + job skills (linked to companies) ---------------------
    for title, company, loc, min_exp, desc in JOBS:
        jid = db.execute(
            """INSERT INTO job_postings
               (company_id,title,company,location,description,clean_text,min_experience)
               VALUES (?,?,?,?,?,?,?)""",
            (company_ids[company], title, company, loc, desc,
             nlp.clean_text(desc), min_exp))
        for skill_name, required, weight in JOB_SKILLS[title]:
            sid = db.query_one("SELECT skill_id FROM skills WHERE name=?",
                               (skill_name,))["skill_id"]
            db.execute(
                """INSERT INTO job_skills (job_id,skill_id,is_required,weight)
                   VALUES (?,?,?,?)""", (jid, sid, required, weight))
    print(f"  inserted {len(JOBS)} job postings")

    # -- a couple of sample applications -----------------------------
    for cand_email, job_title in [("aarav.sharma@example.com",
                                   "Senior Machine Learning Engineer"),
                                  ("meera.nair@example.com", "Data Scientist")]:
        cand = db.query_one("SELECT * FROM candidates WHERE email=?", (cand_email,))
        job = db.query_one("SELECT * FROM job_postings WHERE title=?", (job_title,))
        res = db.query_one("SELECT resume_id FROM resumes WHERE candidate_id=?",
                           (cand["candidate_id"],))
        db.execute(
            """INSERT INTO applications (candidate_id,job_id,resume_id,status)
               VALUES (?,?,?,'submitted')""",
            (cand["candidate_id"], job["job_id"], res["resume_id"]))

    # -- run the AI matcher for every (resume, job) pair -------------
    match_all()
    db.log("SEED", "Database initialised with sample data + logins")


if __name__ == "__main__":
    run()
    print("Done. Database file: data/resume_matcher.db")
    print("Login:  admin@resume.com / password123  (admin)")
    print("        aarav.sharma@example.com / password123  (candidate)")
    print("        hr@neurotech.ai / password123  (company)")
