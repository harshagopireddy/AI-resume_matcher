"""NLP / AI / Data-Science matching engine for AI-resume_matcher.

Techniques used
---------------
* NLP      : tokenisation, stop-word removal, light stemming, TF-IDF vectors
             and cosine similarity between resume and job text.
* AI/ML    : (optional) sentence-transformer embeddings for semantic
             similarity that understands synonyms / paraphrases.
* Data Sci : weighted skill-overlap scoring + experience-fit scoring, then a
             blended final score with a human recommendation label.
"""
import re
import math
from collections import Counter

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import config

# --------------------------------------------------------------------- #
#  Light-weight NLP pre-processing (no external corpus download needed)
# --------------------------------------------------------------------- #
STOPWORDS = set("""
a an and or the of to in for with on at by from as is are was were be been
being this that these those it its into your you we our their they he she
will would shall should can could may might must do does did doing have has
had having not no nor so than then over under about above below between
within without across after before during through during each other more
most some such only own same too very s t don now i me my myself
""".split())


def clean_text(text: str) -> str:
    """Normalise, tokenise, strip stop-words and lightly stem."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"http\S+|www\.\S+", " ", text)
    text = re.sub(r"[^a-z0-9+#./ ]", " ", text)
    tokens = []
    for tok in text.split():
        tok = tok.strip("._/")
        if len(tok) < 2 or tok in STOPWORDS:
            continue
        tok = stem(tok)
        tokens.append(tok)
    return " ".join(tokens)


def stem(word: str) -> str:
    """Very small suffix stripper so 'managing' == 'manager' enough for TF-IDF."""
    for suf in ("ingly", "edly", "ization", "ation", "ings", "ing", "ers",
                "er", "ies", "ed", "es", "s"):
        if len(word) > len(suf) + 3 and word.endswith(suf):
            return word[: -len(suf)]
    return word


# --------------------------------------------------------------------- #
#  Score components
# --------------------------------------------------------------------- #
def tfidf_similarity(resume_text: str, job_text: str) -> float:
    """Cosine similarity of TF-IDF vectors -> 0..100."""
    docs = [clean_text(resume_text), clean_text(job_text)]
    if not docs[0] or not docs[1]:
        return 0.0
    try:
        vec = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
        matrix = vec.fit_transform(docs)
        sim = cosine_similarity(matrix[0], matrix[1])[0][0]
        return round(float(sim) * 100, 2)
    except ValueError:
        return 0.0


def embedding_similarity(resume_text: str, job_text: str):
    """Semantic similarity via sentence-transformers (optional)."""
    if not config.USE_EMBEDDINGS:
        return None
    try:
        from sentence_transformers import SentenceTransformer
        global _MODEL
        try:
            _MODEL
        except NameError:
            _MODEL = SentenceTransformer(config.EMBEDDING_MODEL)
        emb = _MODEL.encode([resume_text[:4000], job_text[:4000]])
        sim = float(np.dot(emb[0], emb[1]) /
                    (np.linalg.norm(emb[0]) * np.linalg.norm(emb[1]) + 1e-9))
        return round(max(0.0, sim) * 100, 2)
    except Exception:
        return None


def skill_overlap(resume_ids, job_skills):
    """Weighted skill overlap -> (score 0..100, matched, missing).

    job_skills : list of dicts {skill_id, weight, name}
    """
    if not job_skills:
        return 0.0, [], []
    total_weight = sum(s.get("weight", 1.0) or 1.0 for s in job_skills)
    gained = 0.0
    matched, missing = [], []
    for s in job_skills:
        if s["skill_id"] in resume_ids:
            gained += s.get("weight", 1.0) or 1.0
            matched.append(s["name"])
        else:
            missing.append(s["name"])
    score = round((gained / total_weight) * 100, 2) if total_weight else 0.0
    return score, matched, missing


def experience_score(pref_years: float, job_min_years: float) -> float:
    """How well experience fits (100 = meets or exceeds the minimum)."""
    pref_years = pref_years or 0
    job_min_years = job_min_years or 0
    if job_min_years <= 0:
        return 100.0
    if pref_years >= job_min_years:
        return 100.0
    return round((pref_years / job_min_years) * 100, 2)


def recommend(final_score: float) -> str:
    if final_score >= 80:
        return "Excellent"
    if final_score >= 60:
        return "Good"
    if final_score >= 40:
        return "Fair"
    return "Poor"


def blend(tfidf, embedding, skill, experience):
    w = config.WEIGHTS
    emb = embedding if embedding is not None else tfidf  # fall back to tfidf
    # re-normalise weights when embeddings are disabled
    if embedding is None:
        wl = {"tfidf": w["tfidf"] + w["embedding"], "skill": w["skill"],
              "experience": w["experience"]}
    else:
        wl = dict(w)
    final = (tfidf * wl["tfidf"] + emb * wl.get("embedding", 0) +
             skill * wl["skill"] + experience * wl["experience"])
    return round(final, 2)


def keyword_gap(resume_text: str, job_text: str, top_n: int = 15):
    """Data-science reporting: key job terms missing from the resume."""
    job_tokens = Counter(clean_text(job_text).split())
    res_tokens = set(clean_text(resume_text).split())
    gap = [(t, c) for t, c in job_tokens.most_common(200) if t not in res_tokens]
    return gap[:top_n]
