import mimetypes
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.decorators import teacher_required, student_required
from apps.accounts.departments import student_scope, students_in
from apps.accounts.models import User
from apps.notifications.models import Notification
from .forms import AssignmentForm, SubmitForm, ReviewForm
from .models import Assignment, AssignmentSubmission


def _students_of(assignment):
    return students_in(assignment.department, assignment.semester).select_related('student_profile').order_by('student_profile__roll_number')


def _mine(user, assignment):
    """Is this assignment sent to this student's department and semester?"""
    p = getattr(user, 'student_profile', None)
    return p is not None and (p.department, p.semester) == (assignment.department, assignment.semester)


@login_required
def assignment_list(request):
    user = request.user
    if user.role == 'STUDENT':
        items = list(Assignment.objects.filter(**student_scope(user)).select_related('created_by'))
        subs = {s.assignment_id: s for s in AssignmentSubmission.objects.filter(student=user, assignment__in=items)}
        rows = []
        for a in items:
            s = subs.get(a.id)
            state = 'reviewed' if s and s.is_reviewed else 'submitted' if s else 'overdue' if a.is_overdue else 'pending'
            rows.append({'a': a, 's': s, 'state': state})
        f = request.GET.get('filter', '')
        if f:
            rows = [r for r in rows if r['state'] == f or (f == 'pending' and r['state'] == 'overdue')]
        return render(request, 'assignments/student_list.html', {'rows': rows, 'filter': f})
    if user.role == 'TEACHER':
        qs = (Assignment.objects.filter(created_by=user)
              .annotate(done=Count('submissions', distinct=True),
                        reviewed=Count('submissions', filter=Q(submissions__rating__isnull=False), distinct=True),
                        avg=Avg('submissions__rating')))
        rows = []
        for a in qs:
            a.avg_int = int(round(a.avg)) if a.avg else 0
            a.total = students_in(a.department, a.semester).count()
            rows.append(a)
        return render(request, 'assignments/teacher_list.html', {'assignments': rows})
    return redirect('admin_dashboard')


@teacher_required
def assignment_create(request):
    profile = getattr(request.user, 'teacher_profile', None)
    form = AssignmentForm(request.POST or None, user=request.user, subject_default=profile.subject if profile else '')
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        a = Assignment.objects.create(title=d['title'].strip(), description=d['description'].strip(), subject=d['subject'].strip(),
                                      department=d['department'], semester=d['semester'], due_date=d['due_date'], created_by=request.user)
        due = f' Submit before {timezone.localtime(a.due_date):%d %b %Y, %I:%M %p}.' if a.due_date else ''
        Notification.objects.bulk_create([
            Notification(recipient=s, sender=request.user, title=f'New assignment: {a.title}', ntype='ASSIGNMENT',
                         message=f'{a.subject}, from {request.user.get_full_name() or request.user.username}.{due}')
            for s in students_in(a.department, a.semester)])
        messages.success(request, f'Assignment sent to {a.department}, Semester {a.semester}. Students were notified.')
        return redirect('assignment_list')
    return render(request, 'assignments/create.html', {'form': form})


@login_required
def assignment_detail(request, assignment_id):
    a = get_object_or_404(Assignment.objects.select_related('created_by'), id=assignment_id)
    user = request.user
    if user.role == 'TEACHER':
        if a.created_by_id != user.id:
            raise PermissionDenied
        subs = {s.student_id: s for s in a.submissions.all()}
        rows = [{'student': st, 'sub': subs.get(st.id)} for st in _students_of(a)]
        reviewed = [r['sub'].rating for r in rows if r['sub'] and r['sub'].is_reviewed]
        return render(request, 'assignments/teacher_detail.html', {
            'a': a, 'rows': rows, 'submitted': sum(1 for r in rows if r['sub']), 'reviewed': len(reviewed),
            'avg': round(sum(reviewed) / len(reviewed), 1) if reviewed else None})
    if user.role == 'STUDENT':
        if not _mine(user, a):
            raise PermissionDenied
        sub = AssignmentSubmission.objects.filter(assignment=a, student=user).first()
        form = SubmitForm()
        return render(request, 'assignments/student_detail.html', {'a': a, 'sub': sub, 'form': form})
    raise PermissionDenied


@student_required
@require_POST
def assignment_submit(request, assignment_id):
    a = get_object_or_404(Assignment, id=assignment_id)
    if not _mine(request.user, a):
        raise PermissionDenied
    sub = AssignmentSubmission.objects.filter(assignment=a, student=request.user).first()
    if sub and sub.is_reviewed:
        messages.error(request, 'Your teacher has already reviewed this assignment, so it can no longer be changed.')
        return redirect('assignment_detail', assignment_id=a.id)
    form = SubmitForm(request.POST, request.FILES)
    if not form.is_valid():
        return render(request, 'assignments/student_detail.html', {'a': a, 'sub': sub, 'form': form})
    now = timezone.now()
    late = bool(a.due_date and now > a.due_date)
    if sub:                                   # replace the earlier upload
        old = sub.file.name
        sub.file = form.cleaned_data['file']
        sub.note, sub.submitted_at, sub.is_late = form.cleaned_data['note'].strip(), now, late
        sub.save()
        if old and old != sub.file.name:
            sub.file.storage.delete(old)
    else:
        sub = AssignmentSubmission.objects.create(assignment=a, student=request.user, file=form.cleaned_data['file'],
                                                  note=form.cleaned_data['note'].strip(), submitted_at=now, is_late=late)
    Notification.objects.create(
        recipient=a.created_by, sender=request.user, ntype='ASSIGNMENT', title=f'Assignment submitted: {a.title}',
        message=f'{request.user.get_full_name() or request.user.username} submitted{" (late)" if late else ""}. Open it to review and rate.')
    messages.success(request, 'Assignment submitted. Your teacher will review it.' + (' It was marked late.' if late else ''))
    return redirect('assignment_detail', assignment_id=a.id)


@teacher_required
def submission_review(request, submission_id):
    sub = get_object_or_404(AssignmentSubmission.objects.select_related('assignment', 'student'),
                            id=submission_id, assignment__created_by=request.user)
    form = ReviewForm(request.POST or None, initial={'rating': sub.rating, 'review': sub.review})
    if request.method == 'POST' and form.is_valid():
        sub.rating, sub.review = form.cleaned_data['rating'], form.cleaned_data['review'].strip()
        sub.reviewed_by, sub.reviewed_at = request.user, timezone.now()
        sub.save()
        Notification.objects.create(
            recipient=sub.student, sender=request.user, ntype='ASSIGNMENT', title=f'Assignment reviewed: {sub.assignment.title}',
            message=f'Rating: {sub.rating} out of 5.' + (f' "{sub.review[:120]}"' if sub.review else ''))
        messages.success(request, f'Review saved. {sub.student.get_full_name() or sub.student.username} can see the rating.')
        return redirect('assignment_detail', assignment_id=sub.assignment_id)
    return render(request, 'assignments/review.html', {'sub': sub, 'form': form})


@teacher_required
@require_POST
def assignment_delete(request, assignment_id):
    a = get_object_or_404(Assignment, id=assignment_id, created_by=request.user)
    names = [s.file.name for s in a.submissions.all()]
    title = a.title
    a.delete()
    for n in names:                              # remove the uploaded files too
        if n:
            AssignmentSubmission._meta.get_field('file').storage.delete(n)
    messages.success(request, f'"{title}" and its submissions were deleted.')
    return redirect('assignment_list')


@login_required
def submission_file(request, submission_id):
    """Only the student who uploaded it, the teacher who set the assignment, or an admin may open the file."""
    sub = get_object_or_404(AssignmentSubmission.objects.select_related('assignment'), id=submission_id)
    u = request.user
    if not (u.role == 'ADMIN' or sub.student_id == u.id or sub.assignment.created_by_id == u.id):
        raise PermissionDenied
    try:
        handle = sub.file.open('rb')
    except (OSError, ValueError):
        raise Http404('The file is missing from the server.')
    ctype = mimetypes.guess_type(sub.filename)[0] or 'application/octet-stream'
    inline = sub.extension in ('pdf', 'txt', 'jpg', 'jpeg', 'png')
    resp = FileResponse(handle, content_type=ctype, as_attachment=not inline, filename=sub.filename)
    resp['X-Content-Type-Options'] = 'nosniff'
    return resp
