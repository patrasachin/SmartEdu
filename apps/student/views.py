from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from apps.accounts.decorators import student_required
from apps.accounts.departments import student_scope
from apps.attendance.models import Attendance
from apps.exams.models import Exam, ExamSubmission
from apps.materials.models import StudyMaterial
from apps.exams.utils import seconds_left, exam_state, student_extension, is_closed
from apps.notifications.models import Notification
from apps.performance.models import PerformanceReport, WeakTopic, Recommendation
from apps.performance.series import performance_series
from apps.assignments.models import Assignment, AssignmentSubmission
from apps.reattempt.models import ReattemptRequest
from apps.proctoring.models import ProctoringLog
from ai_engine.proctoring.face_detector import AVAILABLE as FACE_DETECTOR_AVAILABLE
from ai_engine.performance.analyzer import analyze_performance


def _scope(user):
    return student_scope(user)


def _department(user):
    profile = getattr(user, 'student_profile', None)
    return profile.department if profile else ''


def _exam_rows(user):
    """Published exams for the student's department, each with the student's own submission, request and state."""
    exams = list(Exam.objects.filter(**_scope(user), status='PUBLISHED').order_by('scheduled_at'))
    subs = {s.exam_id: s for s in ExamSubmission.objects.filter(student=user, exam__in=exams)}
    reqs = {r.exam_id: r for r in ReattemptRequest.objects.filter(student=user, exam__in=exams)}
    rows = []
    for e in exams:
        sub, req = subs.get(e.id), reqs.get(e.id)
        ext = req if req and req.chance_is_open else None
        rows.append({'exam': e, 'submission': sub, 'state': exam_state(e, sub, ext), 'request': req, 'extension': ext})
    return rows


def _pending_assignments(user):
    done = AssignmentSubmission.objects.filter(student=user).values_list('assignment_id', flat=True)
    return list(Assignment.objects.filter(**_scope(user)).exclude(id__in=done).select_related('created_by'))


def _attendance_summary(user):
    agg = Attendance.objects.filter(student=user).aggregate(
        total=Count('id'), present=Count('id', filter=Q(status='PRESENT')),
        late=Count('id', filter=Q(status='LATE')), absent=Count('id', filter=Q(status='ABSENT')))
    # Late still counts as attended
    attended = agg['present'] + agg['late']
    agg['percent'] = round(attended / agg['total'] * 100) if agg['total'] else 0
    return agg


@student_required
def dashboard(request):
    user = request.user
    rows = _exam_rows(user)
    todo = [r for r in rows if r['state'] in ('open', 'upcoming')]
    missed = [r for r in rows if r['state'] == 'missed' and r['request'] is None]
    open_now = [r for r in todo if r['state'] == 'open']
    analysis = analyze_performance(user)
    reports = PerformanceReport.objects.filter(student=user).select_related('exam').order_by('-generated_at')[:5]
    return render(request, 'student/dashboard.html', {
        'todo': todo, 'open_now': open_now, 'missed': missed,
        'assignments_due': _pending_assignments(user)[:4],
        'overall': performance_series(user)['overall'],
        'att': _attendance_summary(user),
        'analysis': analysis,
        'reports': reports,
        'weak_topics': WeakTopic.objects.filter(student=user, is_improved=False).order_by('-failure_count')[:6],
        'recent_notifications': Notification.objects.filter(recipient=user).order_by('-created_at')[:4],
        'department': _department(user), 'semester': getattr(getattr(user, 'student_profile', None), 'semester', ''),
        'materials': StudyMaterial.objects.filter(**_scope(user)).select_related('uploaded_by')[:4],
    })


@student_required
def exams_view(request):
    rows = list(reversed(_exam_rows(request.user)))
    return render(request, 'student/exams.html', {'rows': rows})


def _get_exam_for_student(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id, status='PUBLISHED')
    p = getattr(request.user, 'student_profile', None)
    if p is None or (p.department, p.semester) != (exam.department, exam.semester):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    return exam


@student_required
def exam_instructions(request, exam_id):
    exam = _get_exam_for_student(request, exam_id)
    sub = ExamSubmission.objects.filter(exam=exam, student=request.user).first()
    ext = student_extension(exam, request.user)
    state = exam_state(exam, sub, ext)
    return render(request, 'student/exam_instructions.html', {
        'exam': exam, 'submission': sub, 'state': state, 'extension': ext,
        'request_obj': ReattemptRequest.objects.filter(exam=exam, student=request.user).first(),
        'question_count': exam.questions.count(),
        'max_violations': settings.AI_PROCTORING_MAX_VIOLATIONS,
    })


@student_required
def take_exam(request, exam_id):
    exam = _get_exam_for_student(request, exam_id)
    if exam.scheduled_at > timezone.now():
        messages.warning(request, 'This exam has not opened yet.')
        return redirect('exam_instructions', exam_id=exam.id)
    existing = ExamSubmission.objects.filter(exam=exam, student=request.user).first()
    if existing is None and is_closed(exam) and student_extension(exam, request.user) is None:
        messages.warning(request, 'This exam has closed. You can tell your teacher why you missed it and ask for another chance.')
        return redirect('exam_instructions', exam_id=exam.id)
    questions = list(exam.questions.all())
    if not questions:
        messages.warning(request, 'This exam has no questions yet. Ask your teacher.')
        return redirect('student_exams')

    submission, _ = ExamSubmission.objects.get_or_create(exam=exam, student=request.user)
    if submission.is_cancelled or submission.is_completed:
        return redirect('student_result', submission_id=submission.id)

    saved = {}
    for a in submission.answers.all():
        saved[a.question_id] = a.selected_option or a.subjective_text
    for q in questions:
        q.saved = saved.get(q.id, '')
        q.option_list = [('A', q.option_a), ('B', q.option_b), ('C', q.option_c), ('D', q.option_d)]
    left = seconds_left(submission)
    config = {
        'examId': exam.id, 'submissionId': submission.id, 'secondsLeft': left,
        'violations': ProctoringLog.objects.filter(submission=submission).count(),
        'maxViolations': settings.AI_PROCTORING_MAX_VIOLATIONS,
        'frameInterval': settings.PROCTORING_FRAME_INTERVAL,
        'faceCheckAvailable': settings.PROCTORING_FACE_CHECK and FACE_DETECTOR_AVAILABLE,
        'urls': {'submit': f'/exams/submit/{exam.id}/', 'save': f'/exams/save/{exam.id}/',
                 'log': '/proctoring/log/', 'frame': '/proctoring/frame/',
                 'result': f'/student/result/{submission.id}/'},
    }

    return render(request, 'student/exam.html', {
        'exam': exam, 'questions': questions, 'submission': submission,
        'config': config, 'seconds_left_min': max(1, left // 60),
        'max_violations': settings.AI_PROCTORING_MAX_VIOLATIONS,
        'max_range': range(settings.AI_PROCTORING_MAX_VIOLATIONS),
        'total_marks': sum(q.marks for q in questions),
    })


@student_required
def attendance_view(request):
    records = Attendance.objects.filter(student=request.user).order_by('-date')
    return render(request, 'student/attendance.html', {'attendances': records, 'att': _attendance_summary(request.user)})


@student_required
def performance_view(request):
    user = request.user
    reports = list(PerformanceReport.objects.filter(student=user).select_related('exam').order_by('generated_at'))
    chart = {'labels': [r.exam.title if r.exam else 'Exam' for r in reports],
             'values': [round(r.percentage, 1) for r in reports],
             'threshold': settings.AI_THRESHOLD_FAIL}
    weak = WeakTopic.objects.filter(student=user).order_by('is_improved', '-failure_count')
    active_topics = [w.topic for w in weak if not w.is_improved]
    recs = Recommendation.objects.filter(student=user, topic__in=active_topics).order_by('topic', 'id')
    series = performance_series(user)
    return render(request, 'student/performance.html', {
        'reports': reversed(reports), 'chart': chart, 'weak_topics': weak,
        'analysis': analyze_performance(user), 'recommendations': recs,
        'series': series, 'combined': series['chart'],
        'rated': AssignmentSubmission.objects.filter(student=user, rating__isnull=False).select_related('assignment').order_by('-reviewed_at'),
    })


@student_required
def result_view(request, submission_id):
    submission = get_object_or_404(ExamSubmission.objects.select_related('exam'), id=submission_id, student=request.user)
    answers = submission.answers.select_related('question').order_by('question_id')
    report = PerformanceReport.objects.filter(student=request.user, exam=submission.exam).first()
    topics = sorted({a.question.topic or 'General' for a in answers if a.is_correct is False})
    recs = Recommendation.objects.filter(student=request.user, topic__in=topics)
    return render(request, 'student/result.html', {
        'submission': submission, 'answers': answers, 'report': report,
        'missed_topics': topics, 'recommendations': recs,
        'violations': ProctoringLog.objects.filter(submission=submission).order_by('timestamp'),
        'threshold': settings.AI_THRESHOLD_FAIL,
    })
