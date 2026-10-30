from collections import Counter
from django.conf import settings
from django.contrib import messages
from django.db.models import Avg, Count, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.decorators import teacher_required
from apps.accounts.models import User, StudentProfile
from apps.attendance.models import Attendance
from apps.exams.models import Exam, Question, ExamSubmission
from apps.exams.utils import refresh_exam_totals
from apps.notifications.models import Notification
from apps.notifications.emails import send_guardian_attendance
from urllib.parse import urlencode
from apps.accounts.departments import DEPARTMENTS, semester_count, students_in
from apps.performance.models import PerformanceReport, WeakTopic, Recommendation
from apps.performance.series import performance_series
from apps.assignments.models import AssignmentSubmission
from apps.proctoring.models import ProctoringLog
from ai_engine.evaluation.score_generator import generate_scores, recompute_submission
from .forms import ExamForm, QuestionForm

THRESHOLD = settings.AI_THRESHOLD_FAIL


def _my_exam(request, exam_id):
    return get_object_or_404(Exam, id=exam_id, created_by=request.user)


def _sem_values(department):
    return list(range(1, semester_count(department) + 1)) if department else list(range(1, 9))


def _student_stats(students):
    """Average % and attendance % for each student, using two queries in total."""
    ids = [s.id for s in students]
    avgs = dict(PerformanceReport.objects.filter(student_id__in=ids).values_list('student_id').annotate(a=Avg('percentage')))
    counts = {r['student']: r for r in Attendance.objects.filter(student_id__in=ids).values('student').annotate(
        total=Count('id'), attended=Count('id', filter=~Q(status='ABSENT')))}
    for s in students:
        s.avg_pct = round(avgs[s.id], 1) if s.id in avgs else None
        c = counts.get(s.id)
        s.att_pct = round(c['attended'] / c['total'] * 100) if c and c['total'] else None
        s.is_low = s.avg_pct is not None and s.avg_pct < THRESHOLD
    return students


# ------------------------------------------------------------------ dashboard
@teacher_required
def dashboard(request):
    me = request.user
    exams = Exam.objects.filter(created_by=me)
    subs = ExamSubmission.objects.filter(exam__created_by=me, is_completed=True)
    flagged = subs.filter(is_flagged_low=True).select_related('student', 'exam').order_by('-submitted_at')[:6]
    recent = subs.select_related('student', 'exam').order_by('-submitted_at')[:6]
    avg = subs.aggregate(a=Avg('percentage'))['a']
    per_exam = (exams.filter(submissions__is_completed=True)
                .annotate(avg=Avg('submissions__percentage'), n=Count('submissions', filter=Q(submissions__is_completed=True)))
                .order_by('scheduled_at'))
    chart = {'labels': [e.title for e in per_exam], 'values': [round(e.avg, 1) for e in per_exam], 'threshold': THRESHOLD}
    return render(request, 'teacher/dashboard.html', {
        'exam_count': exams.count(), 'draft_count': exams.filter(status='DRAFT').count(),
        'submission_count': subs.count(), 'avg_pct': round(avg, 1) if avg is not None else None,
        'flagged_count': subs.filter(is_flagged_low=True).count(),
        'flagged': flagged, 'recent': recent, 'chart': chart,
        'upcoming': exams.filter(status='PUBLISHED').order_by('-scheduled_at')[:5],
        'cancelled_count': ExamSubmission.objects.filter(exam__created_by=me, is_cancelled=True).count(),
    })


# ------------------------------------------------------------------ exams
@teacher_required
def exams_list(request):
    exams = (Exam.objects.filter(created_by=request.user)
             .annotate(q_count=Count('questions', distinct=True),
                       done=Count('submissions', filter=Q(submissions__is_completed=True), distinct=True))
             .order_by('-scheduled_at'))
    return render(request, 'teacher/exams.html', {'exams': exams})


@teacher_required
def create_exam(request):
    form = ExamForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        exam = form.save(commit=False)
        exam.created_by = request.user
        exam.status = 'DRAFT'
        exam.total_marks = 0
        exam.save()
        messages.success(request, 'Exam created as a draft. Add questions, then publish it to notify students.')
        return redirect('teacher_questions', exam_id=exam.id)
    return render(request, 'teacher/exam_form.html', {'form': form, 'editing': False})


@teacher_required
def edit_exam(request, exam_id):
    exam = _my_exam(request, exam_id)
    form = ExamForm(request.POST or None, instance=exam, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Exam details saved.')
        return redirect('teacher_questions', exam_id=exam.id)
    return render(request, 'teacher/exam_form.html', {'form': form, 'editing': True, 'exam': exam})


@teacher_required
@require_POST
def toggle_publish(request, exam_id):
    exam = _my_exam(request, exam_id)
    if exam.status == 'PUBLISHED':
        if exam.submissions.exists():
            messages.error(request, 'Students have already started this exam, so it cannot go back to draft.')
        else:
            exam.status = 'DRAFT'
            exam.save()
            messages.success(request, 'Exam moved back to draft. Students no longer see it.')
        return redirect('teacher_questions', exam_id=exam.id)

    if not exam.questions.exists():
        messages.error(request, 'Add at least one question before publishing.')
        return redirect('teacher_questions', exam_id=exam.id)
    exam.status = 'PUBLISHED'
    exam.save()
    local = timezone.localtime(exam.scheduled_at).strftime('%d %b %Y, %I:%M %p')
    students = students_in(exam.department, exam.semester)
    Notification.objects.bulk_create([
        Notification(recipient=s, sender=request.user, title=f'New exam: {exam.title}',
                     message=f'{exam.subject} exam opens {local}' + (f' and closes {timezone.localtime(exam.closes_at).strftime("%d %b %Y, %I:%M %p")}' if exam.closes_at else '') + f'. Duration {exam.duration_minutes} minutes.',
                     ntype='EXAM', related_exam=exam)
        for s in students])
    messages.success(request, f'Published. {students.count()} student(s) in {exam.department}, Semester {exam.semester} were notified.')
    return redirect('teacher_questions', exam_id=exam.id)


@teacher_required
@require_POST
def delete_exam(request, exam_id):
    exam = _my_exam(request, exam_id)
    title = exam.title
    exam.delete()
    messages.success(request, f'"{title}" was deleted.')
    return redirect('teacher_exams')


@teacher_required
def questions_view(request, exam_id):
    exam = _my_exam(request, exam_id)
    locked = exam.submissions.exists()
    form = QuestionForm(request.POST or None, initial={'qtype': 'MCQ', 'marks': 5})
    if request.method == 'POST':
        if locked:
            messages.error(request, 'Students have already started this exam, so questions are locked.')
            return redirect('teacher_questions', exam_id=exam.id)
        if form.is_valid():
            q = form.save(commit=False)
            q.exam = exam
            q.correct_option = (q.correct_option or '').upper()
            q.save()
            refresh_exam_totals(exam)
            messages.success(request, 'Question added.')
            return redirect('teacher_questions', exam_id=exam.id)
    return render(request, 'teacher/questions.html', {
        'exam': exam, 'questions': exam.questions.all(), 'form': form, 'locked': locked})


@teacher_required
@require_POST
def delete_question(request, question_id):
    q = get_object_or_404(Question, id=question_id, exam__created_by=request.user)
    exam = q.exam
    if exam.submissions.exists():
        messages.error(request, 'Students have already started this exam, so questions are locked.')
    else:
        q.delete()
        refresh_exam_totals(exam)
        messages.success(request, 'Question removed.')
    return redirect('teacher_questions', exam_id=exam.id)


@teacher_required
def answer_key_view(request, exam_id):
    exam = _my_exam(request, exam_id)
    return render(request, 'teacher/answer_key.html', {'exam': exam, 'questions': exam.questions.all()})


# ------------------------------------------------------------------ results
@teacher_required
def results_view(request, exam_id=None):
    exam = _my_exam(request, exam_id) if exam_id else None
    subs = ExamSubmission.objects.filter(exam__created_by=request.user).select_related('student', 'exam')
    if exam:
        subs = subs.filter(exam=exam)
    subs = subs.annotate(violation_count=Count('proctoring_logs')).order_by('-submitted_at', '-started_at')
    f = request.GET.get('filter', '')
    if f == 'low':
        subs = subs.filter(is_flagged_low=True, is_completed=True)
    elif f == 'cancelled':
        subs = subs.filter(is_cancelled=True)
    exams = Exam.objects.filter(created_by=request.user).order_by('-scheduled_at')
    return render(request, 'teacher/results.html', {'submissions': subs, 'exam': exam, 'exams': exams, 'filter': f})


@teacher_required
def submission_detail(request, submission_id):
    sub = get_object_or_404(ExamSubmission.objects.select_related('exam', 'student'), id=submission_id, exam__created_by=request.user)
    answers = list(sub.answers.select_related('question').order_by('question_id'))
    if request.method == 'POST':
        if not sub.is_completed:
            messages.error(request, 'This submission is not completed, so there is nothing to mark.')
            return redirect('submission_detail', submission_id=sub.id)
        for a in answers:
            raw = request.POST.get(f'score_{a.id}')
            if raw in (None, ''):
                continue
            try:
                score = max(0.0, min(float(raw), float(a.question.marks)))
            except ValueError:
                continue
            feedback = request.POST.get(f'feedback_{a.id}', a.ai_feedback).strip()
            if score != a.score or feedback != a.ai_feedback:
                a.score = score
                a.ai_feedback = feedback
                a.is_correct = score >= a.question.marks * 0.5
                a.save()
        recompute_submission(sub)
        Notification.objects.create(
            recipient=sub.student, sender=request.user, title=f'Marks updated: {sub.exam.title}',
            message=f'Your teacher reviewed your answers. New score: {sub.total_score:g}/{sub.exam.total_marks} ({sub.percentage:.1f}%).',
            ntype='RESULT', related_exam=sub.exam)
        messages.success(request, 'Marks saved and the student was notified.')
        return redirect('submission_detail', submission_id=sub.id)
    return render(request, 'teacher/submission_detail.html', {
        'sub': sub, 'answers': answers,
        'logs': ProctoringLog.objects.filter(submission=sub).order_by('timestamp'),
        'threshold': THRESHOLD})


@teacher_required
@require_POST
def reset_submission(request, submission_id):
    """Lets a student retake an exam (for example after a wrongly cancelled attempt)."""
    sub = get_object_or_404(ExamSubmission, id=submission_id, exam__created_by=request.user)
    PerformanceReport.objects.filter(student=sub.student, exam=sub.exam).delete()
    student, exam = sub.student, sub.exam
    sub.delete()
    Notification.objects.create(recipient=student, sender=request.user, title=f'Retake allowed: {exam.title}',
                                message='Your teacher has reopened this exam for you.', ntype='EXAM', related_exam=exam)
    messages.success(request, f'{student.get_full_name() or student.username} can retake the exam.')
    return redirect('teacher_results_exam', exam_id=exam.id)


@teacher_required
@require_POST
def auto_evaluate(request, exam_id):
    exam = _my_exam(request, exam_id)
    subs = ExamSubmission.objects.filter(exam=exam, is_completed=True)
    for s in subs:
        generate_scores(s)
    messages.success(request, f'{subs.count()} submission(s) re-scored by the AI. Manual edits were replaced.')
    return redirect('teacher_results_exam', exam_id=exam.id)


# ------------------------------------------------------------------ students
@teacher_required
def students_view(request):
    qs = User.objects.filter(role='STUDENT').select_related('student_profile').order_by(
        'student_profile__department', 'student_profile__semester', 'student_profile__roll_number')
    dept, sem = request.GET.get('department', ''), request.GET.get('semester', '')
    q = request.GET.get('q', '').strip()
    if dept:
        qs = qs.filter(student_profile__department=dept)
    if sem.isdigit():
        qs = qs.filter(student_profile__semester=int(sem))
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(student_profile__roll_number__icontains=q))
    students = _student_stats(list(qs))
    if request.GET.get('filter') == 'low':
        students = [s for s in students if s.is_low]
    return render(request, 'teacher/students.html', {
        'students': students, 'departments': DEPARTMENTS, 'dept': dept, 'sem': sem, 'semesters': _sem_values(dept),
        'q': q, 'filter': request.GET.get('filter', '')})


@teacher_required
def student_detail(request, student_id):
    student = get_object_or_404(User.objects.select_related('student_profile'), id=student_id, role='STUDENT')
    reports = PerformanceReport.objects.filter(student=student).select_related('exam').order_by('generated_at')
    chart = {'labels': [r.exam.title if r.exam else 'Exam' for r in reports], 'values': [round(r.percentage, 1) for r in reports], 'threshold': THRESHOLD}
    _student_stats([student])
    series = performance_series(student)
    return render(request, 'teacher/student_detail.html', {
        'student': student, 'reports': reversed(list(reports)), 'chart': chart,
        'series': series, 'combined': series['chart'],
        'rated': AssignmentSubmission.objects.filter(student=student, rating__isnull=False).select_related('assignment').order_by('-reviewed_at'),
        'weak_topics': WeakTopic.objects.filter(student=student).order_by('is_improved', '-failure_count'),
        'attendance': Attendance.objects.filter(student=student).order_by('-date')[:10]})


# ------------------------------------------------------------------ attendance
@teacher_required
def attendance_view(request):
    profile = getattr(request.user, 'teacher_profile', None)
    default_dept = profile.department if profile and profile.department in DEPARTMENTS else DEPARTMENTS[0]
    dept = request.GET.get('department') or request.POST.get('department') or default_dept
    if dept not in DEPARTMENTS:
        dept = default_dept
    try:
        sem = int(request.GET.get('semester') or request.POST.get('semester') or 1)
    except ValueError:
        sem = 1
    sem = min(max(sem, 1), semester_count(dept))
    date_str = request.GET.get('date') or request.POST.get('date') or timezone.localdate().isoformat()
    try:
        date = timezone.datetime.fromisoformat(date_str).date()
    except ValueError:
        date = timezone.localdate()
    students = list(students_in(dept, sem).select_related('student_profile').order_by('student_profile__roll_number'))

    if request.method == 'POST':
        saved = 0
        email_records = []
        for s in students:
            status = request.POST.get(f'status_{s.id}')
            if status not in ('PRESENT', 'ABSENT', 'LATE'):
                continue
            Attendance.objects.update_or_create(
                student=s, date=date,
                defaults={'status': status, 'department': dept, 'semester': sem, 'marked_by': request.user})
            saved += 1
            email_records.append((s, date, status, f'{dept}, Semester {sem}'))
            if status == 'ABSENT':
                Notification.objects.get_or_create(
                    recipient=s, ntype='ATTENDANCE', title=f'Marked absent on {date:%d %b}',
                    defaults={'sender': request.user, 'message': f'You were marked absent in {dept}, Semester {sem} on {date:%d %b %Y}.'})
        sent = send_guardian_attendance(email_records)
        messages.success(request, f'Attendance saved for {saved} student(s) on {date:%d %b %Y}. {sent} guardian email(s) sent.')
        return redirect('/teacher/attendance/?' + urlencode({'department': dept, 'semester': sem, 'date': date.isoformat()}))

    existing = {a.student_id: a.status for a in Attendance.objects.filter(date=date, student__in=students)}
    for s in students:
        s.current = existing.get(s.id, 'PRESENT')
    history = (Attendance.objects.filter(marked_by=request.user)
               .values('date', 'department', 'semester')
               .annotate(present=Count('id', filter=Q(status='PRESENT')), late=Count('id', filter=Q(status='LATE')),
                         absent=Count('id', filter=Q(status='ABSENT')))
               .order_by('-date')[:8])
    return render(request, 'teacher/attendance.html', {
        'students': students, 'departments': DEPARTMENTS, 'dept': dept, 'sem': str(sem), 'semesters': _sem_values(dept),
        'date': date, 'history': history,
        'statuses': [('PRESENT', 'Present'), ('LATE', 'Late'), ('ABSENT', 'Absent')],
        'already_marked': bool(existing)})


# ------------------------------------------------------------------ analytics
@teacher_required
def performance_view(request):
    me = request.user
    subs = ExamSubmission.objects.filter(exam__created_by=me, is_completed=True)
    per_exam = (Exam.objects.filter(created_by=me, submissions__is_completed=True)
                .annotate(avg=Avg('submissions__percentage'), n=Count('submissions', filter=Q(submissions__is_completed=True)))
                .order_by('scheduled_at'))
    buckets = Counter()
    for pct in subs.values_list('percentage', flat=True):
        buckets[min(int(pct // 20), 4)] += 1
    labels = ['0-19%', '20-39%', '40-59%', '60-79%', '80-100%']
    student_ids = subs.values_list('student_id', flat=True)
    weak = WeakTopic.objects.filter(student_id__in=student_ids, is_improved=False).select_related('student')
    topic_counts = Counter(w.topic for w in weak)
    chart = {
        'exams': {'labels': [e.title for e in per_exam], 'values': [round(e.avg, 1) for e in per_exam]},
        'dist': {'labels': labels, 'values': [buckets.get(i, 0) for i in range(5)]},
        'topics': {'labels': [t for t, _ in topic_counts.most_common(8)], 'values': [c for _, c in topic_counts.most_common(8)]},
        'threshold': THRESHOLD,
    }
    return render(request, 'teacher/performance.html', {
        'chart': chart, 'per_exam': per_exam, 'weak_topics': weak.order_by('-failure_count')[:25], 'total': subs.count()})
