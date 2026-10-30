import json
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.decorators import student_required
from apps.notifications.models import Notification
from apps.notifications.emails import send_guardian_result
from ai_engine.evaluation.score_generator import generate_scores
from ai_engine.performance.recommendation import generate_recommendations
from ai_engine.performance.weak_topic_detector import detect_weak_topics
from .models import Exam, ExamSubmission, StudentAnswer


def _answers_from_request(request):
    try:
        payload = json.loads(request.body or b'{}')
    except ValueError:
        return {}
    answers = payload.get('answers', payload)
    return answers if isinstance(answers, dict) else {}


def _store_answers(exam, submission, answers):
    for q in exam.questions.all():
        value = str(answers.get(str(q.id), '') or '')
        obj, _ = StudentAnswer.objects.get_or_create(submission=submission, question=q)
        if q.qtype == 'MCQ':
            obj.selected_option = value.strip().upper()[:1]
        else:
            obj.subjective_text = value[:10000]
        obj.save()


@student_required
@require_POST
def save_progress(request, exam_id):
    """Autosave: lets a student refresh without losing answers."""
    exam = get_object_or_404(Exam, id=exam_id, status='PUBLISHED')
    submission = get_object_or_404(ExamSubmission, exam=exam, student=request.user)
    if submission.is_completed or submission.is_cancelled:
        return JsonResponse({'success': False, 'error': 'Exam already closed'}, status=409)
    _store_answers(exam, submission, _answers_from_request(request))
    return JsonResponse({'success': True})


@student_required
@require_POST
def submit_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id, status='PUBLISHED')
    submission = get_object_or_404(ExamSubmission, exam=exam, student=request.user)
    if submission.is_cancelled:
        return JsonResponse({'success': False, 'error': 'This exam was cancelled.'}, status=409)
    if submission.is_completed:
        return JsonResponse({'success': True, 'submission_id': submission.id, 'percentage': submission.percentage})

    _store_answers(exam, submission, _answers_from_request(request))
    submission.submitted_at = timezone.now()
    submission.is_completed = True
    submission.save()

    generate_scores(submission)
    detect_weak_topics(request.user, submission)
    generate_recommendations(request.user)

    Notification.objects.create(
        recipient=request.user, title=f'Result ready: {exam.title}',
        message=f'You scored {submission.total_score:g}/{exam.total_marks} ({submission.percentage:.1f}%).',
        ntype='RESULT', related_exam=exam)
    if submission.is_flagged_low and exam.created_by_id:
        Notification.objects.create(
            recipient=exam.created_by, sender=request.user,
            title=f'{request.user.get_full_name() or request.user.username} scored below {settings.AI_THRESHOLD_FAIL}%',
            message=f'{exam.title}: {submission.percentage:.1f}%. Review the answers and weak topics.',
            ntype='RESULT', related_exam=exam)
    send_guardian_result(submission)           # result goes to the guardian's email every time an exam is done
    return JsonResponse({'success': True, 'submission_id': submission.id, 'percentage': submission.percentage})


@login_required
def exam_list_api(request):
    exams = list(Exam.objects.filter(status='PUBLISHED').values('id', 'title', 'subject', 'scheduled_at'))
    return JsonResponse({'exams': exams})
