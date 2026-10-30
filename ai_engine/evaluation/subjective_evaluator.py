"""Scores written answers.

Final ratio = TF-IDF cosine similarity to the teacher's ideal answer
              + up to 0.20 bonus for the teacher's keywords (capped at 1.0).
If scikit-learn is not installed, a plain word-count cosine similarity is used instead.
"""
import math
import re
from collections import Counter

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    HAS_SKLEARN = True
except Exception:  # pragma: no cover - only when sklearn is missing
    HAS_SKLEARN = False


def clean_text(text):
    return re.sub(r'[^a-z0-9\s]', '', (text or '').lower())


def _similarity(ideal, answer):
    a, b = clean_text(ideal), clean_text(answer)
    if not a.strip() or not b.strip():
        return 0.0
    if HAS_SKLEARN:
        matrix = TfidfVectorizer().fit_transform([a, b])
        return float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])
    ca, cb = Counter(a.split()), Counter(b.split())
    dot = sum(ca[w] * cb[w] for w in ca)
    norm = math.sqrt(sum(v * v for v in ca.values())) * math.sqrt(sum(v * v for v in cb.values()))
    return dot / norm if norm else 0.0


def _keywords(keywords_str):
    return [k.strip().lower() for k in (keywords_str or '').split(',') if k.strip()]


def evaluate_subjective(student_answer, ideal_answer, keywords_str, max_marks):
    """Returns (score, is_correct, feedback). is_correct=None means 'needs manual review'."""
    if not student_answer or not student_answer.strip():
        return 0, False, 'No answer provided'

    keywords = _keywords(keywords_str)
    lower = student_answer.lower()
    found = [k for k in keywords if k in lower]
    missing = [k for k in keywords if k not in lower]

    if not (ideal_answer or '').strip():
        if not keywords:
            return round(max_marks * 0.5, 2), None, 'Manual review needed: no ideal answer or keywords were set.'
        ratio = len(found) / len(keywords)
        feedback = f'Found {len(found)}/{len(keywords)} keywords.'
        feedback += ' Good coverage.' if ratio > 0.7 else f' Missing: {", ".join(missing)}.'
        return round(max_marks * ratio, 2), ratio >= 0.6, feedback

    try:
        sim = _similarity(ideal_answer, student_answer)
        bonus = (len(found) / len(keywords)) * 0.2 if keywords else 0
        final_ratio = min(1.0, sim + bonus)
        score = round(max_marks * final_ratio, 2)
        if final_ratio > 0.75:
            verdict = 'Well explained.'
        elif final_ratio < 0.5:
            verdict = 'Needs improvement.'
        else:
            verdict = 'Partly correct.'
        feedback = f'{verdict} Similarity {sim:.2f}.'
        if missing:
            feedback += f' Missing key points: {", ".join(missing)}.'
        return score, final_ratio >= 0.5, feedback
    except Exception as exc:  # defensive: never crash a submission
        return round(max_marks * 0.5, 2), None, f'AI error ({exc}). Manual review needed.'
