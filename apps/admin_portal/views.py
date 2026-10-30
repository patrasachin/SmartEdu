from django.conf import settings
from django.core.mail import send_mail
from django.contrib import messages
from django.db.models import Avg, Count, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.crypto import get_random_string
from django.views.decorators.http import require_POST

from apps.accounts.decorators import admin_required
from apps.accounts.departments import DEPARTMENTS, semester_count, semester_label, students_in
from apps.accounts.forms import StudentRegisterForm, StudentEditForm, TeacherRegisterForm, TeacherEditForm
from apps.accounts.models import User, StudentProfile, TeacherProfile
from apps.assignments.models import Assignment, AssignmentSubmission
from apps.attendance.models import Attendance
from apps.exams.models import Exam, ExamSubmission
from apps.materials.models import StudyMaterial
from apps.notifications.models import Notification, EmailLog
from apps.notifications.emails import send_test_email
from apps.performance.models import PerformanceReport
from apps.reattempt.models import ReattemptRequest
from .forms import AnnouncementForm

THRESHOLD = settings.AI_THRESHOLD_FAIL


def _new_password():
    return get_random_string(8, 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789')
def _send_login_details(user, password, role):
    send_mail(
        subject='Your SmartEdu account details',
        message=(
            f'Hello {user.get_full_name() or user.username},\n\n'
            f'Your SmartEdu {role} account has been created.\n'
            f'User ID: {user.username}\n'
            f'Password: {password}\n\n'
            'Please sign in and change your password.'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

def _with_stats(students):
    ids = [s.id for s in students]
    avgs = dict(PerformanceReport.objects.filter(student_id__in=ids).values_list('student_id').annotate(a=Avg('percentage')))
    for s in students:
        s.avg_pct = round(avgs[s.id], 1) if s.id in avgs else None
        s.is_low = s.avg_pct is not None and s.avg_pct < THRESHOLD
    return students


def _semester_filter_values(department):
    """Semesters to offer in a filter: those of the chosen department, or 1 to 8."""
    return list(range(1, semester_count(department) + 1)) if department else list(range(1, 9))


@admin_required
def dashboard(request):
    students = User.objects.filter(role='STUDENT')
    per_dept = {d['department']: d['n'] for d in StudentProfile.objects.values('department').annotate(n=Count('id'))}
    labels = [d for d in DEPARTMENTS if d in per_dept] + sorted(d for d in per_dept if d not in DEPARTMENTS)
    low = [s for s in _with_stats(list(students.select_related('student_profile'))) if s.is_low]
    submissions = ExamSubmission.objects.filter(is_completed=True)
    return render(request, 'admin/dashboard.html', {
        'total_students': students.count(),
        'total_teachers': User.objects.filter(role='TEACHER').count(),
        'total_exams': Exam.objects.count(),
        'total_submissions': submissions.count(),
        'avg_pct': (lambda v: round(v, 1) if v is not None else None)(submissions.aggregate(a=Avg('percentage'))['a']),
        'low_performers': low[:8], 'low_count': len(low),
        'recent_exams': Exam.objects.select_related('created_by').order_by('-created_at')[:6],
        'cancelled': ExamSubmission.objects.filter(is_cancelled=True).count(),
        'chart': {'labels': labels, 'values': [per_dept[d] for d in labels]},
        'chart_height': max(220, 30 * len(labels) + 50),
    })


def _people(request, role):
    qs = User.objects.filter(role=role)
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q))
    return qs, q


# ------------------------------------------------------------------ students
def _students_page(request, form, show_form):
    qs, q = _people(request, 'STUDENT')
    dept, sem = request.GET.get('department', ''), request.GET.get('semester', '')
    qs = qs.select_related('student_profile')
    if dept:
        qs = qs.filter(student_profile__department=dept)
    if sem.isdigit():
        qs = qs.filter(student_profile__semester=int(sem))
    qs = qs.order_by('student_profile__department', 'student_profile__semester', 'student_profile__roll_number')
    return render(request, 'admin/students.html', {
        'students': _with_stats(list(qs)), 'q': q, 'dept': dept, 'sem': sem, 'departments': DEPARTMENTS,
        'semesters': _semester_filter_values(dept), 'form': form, 'show_form': show_form})


@admin_required
def students_list(request):
    return _students_page(request, StudentRegisterForm(), False)


@admin_required
def register_student(request):
    form = StudentRegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        password = d['password'] or _new_password()
        user = User.objects.create_user(
            username=d['username'], email=d['email'], password=password, role='STUDENT',
            first_name=d['first_name'], last_name=d['last_name'], phone=d['phone'])
        StudentProfile.objects.create(user=user, roll_number=d['roll_number'], department=d['department'], semester=d['semester'],
                                      guardian_name=d['guardian_name'].strip(), guardian_email=d['guardian_email'].strip())
        _send_login_details(user, password, 'student')
        Notification.objects.create(recipient=user, sender=request.user, title='Welcome to SmartEdu',
                                    message=f'Your account is ready: {d["department"]}, {semester_label(d["semester"])}.', ntype='GENERAL')
        messages.success(request, f'Student {user.username} registered. Initial password: {password} (share it once; they can change it).')
        return redirect('admin_students')
    return _students_page(request, form, True)


@admin_required
def student_edit(request, user_id):
    user = get_object_or_404(User.objects.select_related('student_profile'), id=user_id, role='STUDENT')
    p = user.student_profile
    initial = {'first_name': user.first_name, 'last_name': user.last_name, 'email': user.email, 'phone': user.phone,
               'department': p.department, 'semester': str(p.semester),
               'guardian_name': p.guardian_name, 'guardian_email': p.guardian_email}
    form = StudentEditForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        user.first_name, user.last_name, user.email, user.phone = d['first_name'], d['last_name'], d['email'], d['phone']
        user.save()
        moved = (p.department, p.semester) != (d['department'], d['semester'])
        p.department, p.semester = d['department'], d['semester']
        p.guardian_name, p.guardian_email = d['guardian_name'].strip(), d['guardian_email'].strip()
        p.save()
        if moved:
            Notification.objects.create(recipient=user, sender=request.user, ntype='GENERAL', title='Your semester was updated',
                                        message=f'You are now in {p.department}, {semester_label(p.semester)}. Your exams, assignments and study material follow this.')
        messages.success(request, f'{user.get_full_name() or user.username} updated.')
        return redirect('admin_students')
    return render(request, 'admin/student_edit.html', {'form': form, 'student': user})


# ------------------------------------------------------------------ teachers
def _teachers_page(request, form, show_form):
    qs, q = _people(request, 'TEACHER')
    dept = request.GET.get('department', '')
    qs = qs.select_related('teacher_profile').annotate(exam_count=Count('created_exams', distinct=True))
    if dept:
        qs = qs.filter(teacher_profile__department=dept)
    return render(request, 'admin/teachers.html', {
        'teachers': qs.order_by('teacher_profile__department', 'first_name', 'username'),
        'q': q, 'dept': dept, 'departments': DEPARTMENTS, 'form': form, 'show_form': show_form})


@admin_required
def teachers_list(request):
    return _teachers_page(request, TeacherRegisterForm(), False)


@admin_required
def register_teacher(request):
    form = TeacherRegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        password = d['password'] or _new_password()
        user = User.objects.create_user(
            username=d['username'], email=d['email'], password=password, role='TEACHER',
            first_name=d['first_name'], last_name=d['last_name'], phone=d['phone'])
        TeacherProfile.objects.create(user=user, employee_id=d['employee_id'], subject=d['subject'], department=d['department'])
        _send_login_details(user, password, 'teacher')
        messages.success(request, f'Teacher {user.username} registered in {d["department"]}. Initial password: {password} (share it once; they can change it).')
        return redirect('admin_teachers')
    return _teachers_page(request, form, True)


@admin_required
def teacher_edit(request, user_id):
    user = get_object_or_404(User.objects.select_related('teacher_profile'), id=user_id, role='TEACHER')
    p = user.teacher_profile
    initial = {'first_name': user.first_name, 'last_name': user.last_name, 'email': user.email, 'phone': user.phone,
               'employee_id': p.employee_id, 'subject': p.subject, 'department': p.department}
    form = TeacherEditForm(request.POST or None, initial=initial, teacher=user)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        user.first_name, user.last_name, user.email, user.phone = d['first_name'], d['last_name'], d['email'], d['phone']
        user.save()
        p.employee_id, p.subject, p.department = d['employee_id'], d['subject'], d['department']
        p.save()
        messages.success(request, f'{user.get_full_name() or user.username} updated.')
        return redirect('admin_teachers')
    return render(request, 'admin/teacher_edit.html', {'form': form, 'teacher': user})


# ------------------------------------------------------------------ switch off, password, delete
def _manageable(request, user_id):
    return get_object_or_404(User, id=user_id, role__in=['STUDENT', 'TEACHER'])


@admin_required
@require_POST
def toggle_active(request, user_id):
    user = _manageable(request, user_id)
    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])
    messages.success(request, f'{user.username} is now {"active" if user.is_active else "switched off"}.')
    return redirect(request.POST.get('next') or 'admin_dashboard')


@admin_required
@require_POST
def reset_password(request, user_id):
    user = _manageable(request, user_id)
    password = _new_password()
    user.set_password(password)
    user.save()
    messages.success(request, f'New password for {user.username}: {password} (share it once; they can change it).')
    return redirect(request.POST.get('next') or 'admin_dashboard')


def _impact(user):
    """What deleting this person will also remove (shown before the admin confirms)."""
    if user.role == 'STUDENT':
        return [('exam attempts and results', ExamSubmission.objects.filter(student=user).count()),
                ('assignment submissions', AssignmentSubmission.objects.filter(student=user).count()),
                ('re-attempt requests', ReattemptRequest.objects.filter(student=user).count()),
                ('attendance records', Attendance.objects.filter(student=user).count())]
    return [('exams they created', Exam.objects.filter(created_by=user).count()),
            ('student attempts on those exams', ExamSubmission.objects.filter(exam__created_by=user).count()),
            ('assignments they sent', Assignment.objects.filter(created_by=user).count()),
            ('student submissions to those assignments', AssignmentSubmission.objects.filter(assignment__created_by=user).count()),
            ('study materials they shared', StudyMaterial.objects.filter(uploaded_by=user).count())]


@admin_required
def delete_user(request, user_id):
    user = _manageable(request, user_id)
    back = 'admin_students' if user.role == 'STUDENT' else 'admin_teachers'
    if request.method == 'POST':
        name = user.get_full_name() or user.username
        user.delete()
        messages.success(request, f'{name} was deleted.')
        return redirect(back)
    return render(request, 'admin/confirm_delete.html', {'person': user, 'impact': _impact(user), 'back': back})


# ------------------------------------------------------------------ departments overview, exams, announcements
@admin_required
def departments_view(request):
    rows = []
    groups = (StudentProfile.objects.values('department', 'semester').annotate(n=Count('id')).order_by('department', 'semester'))
    for g in groups:
        ids = StudentProfile.objects.filter(department=g['department'], semester=g['semester']).values_list('user_id', flat=True)
        avg = PerformanceReport.objects.filter(student_id__in=ids).aggregate(a=Avg('percentage'))['a']
        att = Attendance.objects.filter(student_id__in=ids).aggregate(t=Count('id'), p=Count('id', filter=~Q(status='ABSENT')))
        rows.append({**g, 'avg': round(avg, 1) if avg is not None else None,
                     'att': round(att['p'] / att['t'] * 100) if att['t'] else None,
                     'exams': Exam.objects.filter(department=g['department'], semester=g['semester']).count()})
    teachers = {d['teacher_profile__department']: d['n'] for d in
                User.objects.filter(role='TEACHER').values('teacher_profile__department').annotate(n=Count('id'))}
    return render(request, 'admin/departments.html', {'rows': rows, 'teachers': teachers})


@admin_required
def exams_overview(request):
    exams = (Exam.objects.select_related('created_by')
             .annotate(q_count=Count('questions', distinct=True),
                       done=Count('submissions', filter=Q(submissions__is_completed=True), distinct=True),
                       avg=Avg('submissions__percentage', filter=Q(submissions__is_completed=True)))
             .order_by('-scheduled_at'))
    return render(request, 'admin/exams.html', {'exams': exams})


@admin_required
def announce(request):
    form = AnnouncementForm(request.POST or None, initial={'audience': 'ALL'})
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        users = User.objects.filter(is_active=True).exclude(role='ADMIN')
        if d['audience'] in ('STUDENT', 'TEACHER'):
            users = users.filter(role=d['audience'])
        elif d['audience'] == 'DEPT':
            users = users.filter(role='STUDENT', student_profile__department=d['department'])
            if d['semester']:
                users = users.filter(student_profile__semester=d['semester'])
        Notification.objects.bulk_create([
            Notification(recipient=u, sender=request.user, title=d['title'], message=d['message'], ntype='GENERAL') for u in users])
        messages.success(request, f'Announcement sent to {users.count()} people.')
        return redirect('admin_announce')
    sent = (Notification.objects.filter(sender=request.user, ntype='GENERAL')
            .values('title', 'message', 'created_at').annotate(n=Count('id')).order_by('-created_at')[:6])
    return render(request, 'admin/announce.html', {'form': form, 'sent': sent})


# ------------------------------------------------------------------ guardian emails
@admin_required
def emails_list(request):
    qs = EmailLog.objects.select_related('student')
    f = request.GET.get('status', '')
    if f in ('SENT', 'FAILED'):
        qs = qs.filter(status=f)
    return render(request, 'admin/emails.html', {
        'logs': qs[:100], 'filter': f, 'failed': EmailLog.objects.filter(status='FAILED').count(),
        'real_smtp': bool(settings.EMAIL_HOST), 'backend': settings.EMAIL_BACKEND.rsplit('.', 2)[-2]})


@admin_required
@require_POST
def email_test(request):
    to = (request.POST.get('to') or '').strip()
    from django.core.validators import validate_email
    from django.core.exceptions import ValidationError
    try:
        validate_email(to)
    except ValidationError:
        messages.error(request, 'Enter a valid email address for the test.')
        return redirect('admin_emails')
    ok = send_test_email(to)
    messages.success(request, 'Test email sent.') if ok else messages.error(request, 'The test email failed. See the log below for the reason.')
    return redirect('admin_emails')
