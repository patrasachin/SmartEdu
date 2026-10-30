from django.conf import settings
from .mcq_evaluator import evaluate_mcq
from .subjective_evaluator import evaluate_subjective
from apps.performance.models import PerformanceReport
from ai_engine.performance.analyzer import calculate_understanding_score


def generate_scores(submission):
    """Score every answer with the AI engine, then total up the submission."""
    for ans in submission.answers.select_related('question'):
        q = ans.question
        if q.qtype == 'MCQ':
            score, is_correct = evaluate_mcq(ans.selected_option, q.correct_option, q.marks)
            ans.score = score
            ans.is_correct = is_correct
            if not ans.selected_option:
                ans.ai_feedback = f'Not answered. Correct answer: {q.correct_option}.'
            else:
                ans.ai_feedback = 'Correct.' if is_correct else f'Incorrect. Correct answer: {q.correct_option}.'
        else:
            score, is_correct, feedback = evaluate_subjective(ans.subjective_text, q.ideal_answer, q.keywords, q.marks)
            ans.score = score
            ans.is_correct = is_correct
            ans.ai_feedback = feedback
        ans.save()
    return recompute_submission(submission)


def recompute_submission(submission):
    """Re-total scores (after AI scoring or a teacher's manual edit) and refresh the performance report."""
    answers = list(submission.answers.select_related('question'))
    max_total = sum(a.question.marks for a in answers)
    total = sum(a.score for a in answers)
    pct = (total / max_total * 100) if max_total else 0
    submission.total_score = round(total, 2)
    submission.percentage = round(pct, 2)
    submission.is_flagged_low = pct < getattr(settings, 'AI_THRESHOLD_FAIL', 70)
    submission.save()

    level = calculate_understanding_score(pct)
    PerformanceReport.objects.update_or_create(
        student=submission.student, exam=submission.exam,
        defaults={
            'total_marks': max_total,
            'obtained_marks': round(total, 2),
            'percentage': round(pct, 2),
            'understanding_level': level,
            'ai_summary': f'Scored {total:.1f}/{max_total} ({pct:.1f}%). Understanding: {level}.',
        },
    )
    return submission
