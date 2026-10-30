import json
from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from apps.accounts.decorators import student_required
from apps.exams.models import ExamSubmission
from apps.notifications.models import Notification
from apps.notifications.emails import send_guardian_cancelled
from ai_engine.proctoring.face_detector import analyze_frame
from .models import ProctoringLog

VALID_TYPES = {t for t, _ in ProctoringLog.VIOLATION_TYPES}


def _active_submission(request, submission_id):
    return get_object_or_404(ExamSubmission, id=submission_id, student=request.user)


def _record(submission, user, vtype, details='', snapshot=None):
    """Create a violation log; cancel the exam when the limit is reached."""
    log = ProctoringLog.objects.create(submission=submission, student=user, violation_type=vtype, details=details[:500])
    if snapshot:
        log.image_snapshot.save(f'sub{submission.id}_{log.id}.jpg', ContentFile(snapshot), save=True)
    limit = settings.AI_PROCTORING_MAX_VIOLATIONS
    count = ProctoringLog.objects.filter(submission=submission).count()
    cancelled = False
    if count >= limit and not submission.is_cancelled:
        submission.is_cancelled = True
        submission.cancel_reason = f'Cancelled after {count} violations. Last: {log.get_violation_type_display()}'
        submission.save()
        cancelled = True
        send_guardian_cancelled(submission)
        exam = submission.exam
        if exam.created_by_id:
            face_missing = log.violation_type == 'NO_FACE'
            Notification.objects.create(
                recipient=exam.created_by, sender=user,
                title=f'Exam cancelled: {user.get_full_name() or user.username}',
                message=(f'{exam.title}: {user.get_full_name() or user.username} reached the violation limit after their face was repeatedly missing from the camera. Review the proctoring log and decide whether to allow a retake.'
                         if face_missing else
                         f'{exam.title}: {count} proctoring violations. You can review the log and allow a retake.'),
                ntype='EXAM', related_exam=exam)
    return count, cancelled or submission.is_cancelled


@student_required
@require_POST
def log_violation(request):
    try:
        data = json.loads(request.body or b'{}')
        submission = _active_submission(request, data.get('submission_id'))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Bad request'}, status=400)
    vtype = data.get('violation_type')
    if vtype not in VALID_TYPES:
        return JsonResponse({'error': 'Unknown violation type'}, status=400)
    if submission.is_completed:
        return JsonResponse({'cancelled': False, 'count': ProctoringLog.objects.filter(submission=submission).count(), 'closed': True})
    count, cancelled = _record(submission, request.user, vtype, str(data.get('details', '')))
    return JsonResponse({'cancelled': cancelled, 'count': count, 'max': settings.AI_PROCTORING_MAX_VIOLATIONS})


@student_required
@require_POST
def check_frame(request):
    """Receives a webcam snapshot, runs the face check and records a violation after repeated misses."""
    try:
        submission = _active_submission(request, int(request.POST.get('submission_id', 0)))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Bad request'}, status=400)
    image = request.FILES.get('image')
    if submission.is_completed or submission.is_cancelled or image is None:
        return JsonResponse({'status': 'closed'})
    if not getattr(settings, 'PROCTORING_FACE_CHECK', True):
        return JsonResponse({'status': 'unavailable'})

    data = image.read()
    result = analyze_frame(data)
    if not result['available']:
        return JsonResponse({'status': 'unavailable'})

    key = f'proctor-miss-{submission.id}'
    faces = result['faces']
    violation = None
    if faces == 1:
        cache.set(key, 0, 3600)
        status = 'ok'
    elif faces == 0:
        misses = cache.get(key, 0) + 1
        status = 'no_face'
        if misses >= settings.PROCTORING_FACE_MISS_LIMIT:
            violation, misses = 'NO_FACE', 0
        cache.set(key, misses, 3600)
    else:
        status = 'multiple'
        violation = 'MULTIPLE_FACE'

    payload = {'status': status, 'faces': faces}
    if violation:
        count, cancelled = _record(submission, request.user, violation,
                                   f'{faces} face(s) in snapshot', snapshot=data)
        payload.update({'violation': violation, 'count': count, 'cancelled': cancelled})
    return JsonResponse(payload)


@student_required
def violation_count(request, submission_id):
    count = ProctoringLog.objects.filter(submission_id=submission_id, student=request.user).count()
    return JsonResponse({'count': count})
