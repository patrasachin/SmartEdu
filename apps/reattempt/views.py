import mimetypes
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.decorators import teacher_required, student_required
from apps.accounts.departments import student_scope
from apps.exams.models import Exam, ExamSubmission
from apps.exams.utils import exam_state, student_extension
from apps.notifications.models import Notification
from .forms import RequestForm, DecisionForm
from .models import ReattemptRequest


def _dept(user):
    p = getattr(user, 'student_profile', None)
    return p.department if p else ''


def _missed_exams(student):
    """Published exams for the student's department whose closing time passed without an attempt."""
    exams = Exam.objects.filter(**student_scope(student), status='PUBLISHED', closes_at__lt=timezone.now()).order_by('-closes_at')
    started = set(ExamSubmission.objects.filter(student=student, exam__in=exams).values_list('exam_id', flat=True))
    return [e for e in exams if e.id not in started]


@login_required
def reattempt_list(request):
    user = request.user
    if user.role == 'STUDENT':
        reqs = {r.exam_id: r for r in ReattemptRequest.objects.filter(student=user).select_related('exam')}
        rows = [{'exam': e, 'req': reqs.get(e.id)} for e in _missed_exams(user)]
        # approved chances whose exam is not "missed" any more (already used or retaken) still show in the history
        shown = {r['exam'].id for r in rows}
        history = [r for r in reqs.values() if r.exam_id not in shown]
        return render(request, 'reattempt/student_list.html', {'rows': rows, 'history': history})
    if user.role == 'TEACHER':
        qs = ReattemptRequest.objects.filter(exam__created_by=user).select_related('exam', 'student', 'student__student_profile')
        f = request.GET.get('filter', '')
        if f in ('PENDING', 'APPROVED', 'REJECTED'):
            qs = qs.filter(status=f)
        pending = [r for r in qs if r.status == 'PENDING']
        others = [r for r in qs if r.status != 'PENDING']
        default_until = timezone.localtime(timezone.now() + timezone.timedelta(days=2)).strftime('%Y-%m-%dT%H:%M')
        return render(request, 'reattempt/teacher_list.html', {'pending': pending, 'others': others, 'filter': f,
                                                              'default_until': default_until})
    return redirect('admin_dashboard')


@student_required
def reattempt_new(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id, status='PUBLISHED', **student_scope(request.user))
    sub = ExamSubmission.objects.filter(exam=exam, student=request.user).first()
    if exam_state(exam, sub, student_extension(exam, request.user)) != 'missed' or sub is not None:
        messages.error(request, 'You can only ask for another chance for an exam you missed after it closed.')
        return redirect('reattempt_list')
    if ReattemptRequest.objects.filter(exam=exam, student=request.user).exists():
        messages.error(request, 'You have already sent a request for this exam.')
        return redirect('reattempt_list')
    form = RequestForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        ReattemptRequest.objects.create(exam=exam, student=request.user, reason=form.cleaned_data['reason'].strip(),
                                        proof=form.cleaned_data['proof'])
        Notification.objects.create(
            recipient=exam.created_by, sender=request.user, ntype='REATTEMPT', title=f'Re-attempt request: {exam.title}',
            message=f'{request.user.get_full_name() or request.user.username} missed the exam and sent a reason with proof.')
        messages.success(request, 'Request sent with your proof. Your teacher will decide and you will be notified.')
        return redirect('reattempt_list')
    return render(request, 'reattempt/new.html', {'exam': exam, 'form': form})


@teacher_required
@require_POST
def reattempt_decide(request, request_id):
    req = get_object_or_404(ReattemptRequest.objects.select_related('exam', 'student'), id=request_id, exam__created_by=request.user)
    if req.status != 'PENDING':
        messages.error(request, 'This request has already been decided.')
        return redirect('reattempt_list')
    form = DecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, ' '.join(e for errs in form.errors.values() for e in errs))
        return redirect('reattempt_list')
    d = form.cleaned_data
    who = req.student.get_full_name() or req.student.username
    req.decided_by, req.decided_at, req.teacher_comment = request.user, timezone.now(), (d['comment'] or '').strip()
    if d['action'] == 'approve':
        req.status, req.extended_until = 'APPROVED', d['extended_until']
        text = f'Your teacher gave you another chance for "{req.exam.title}". You can take it until {timezone.localtime(req.extended_until):%d %b %Y, %I:%M %p}.'
    else:
        req.status = 'REJECTED'
        text = f'Your request for "{req.exam.title}" was not approved. {req.teacher_comment}'
    req.save()
    Notification.objects.create(recipient=req.student, sender=request.user, ntype='REATTEMPT',
                                title=f'Re-attempt {req.get_status_display().lower()}: {req.exam.title}', message=text)
    messages.success(request, f'{who}: request {req.get_status_display().lower()}.' + (' Only this student can now take the exam.' if req.status == 'APPROVED' else ''))
    return redirect('reattempt_list')


@login_required
def reattempt_proof(request, request_id):
    req = get_object_or_404(ReattemptRequest.objects.select_related('exam'), id=request_id)
    u = request.user
    if not (u.role == 'ADMIN' or req.student_id == u.id or req.exam.created_by_id == u.id):
        raise PermissionDenied
    try:
        handle = req.proof.open('rb')
    except (OSError, ValueError):
        raise Http404('The file is missing from the server.')
    ctype = mimetypes.guess_type(req.proof_name)[0] or 'application/octet-stream'
    inline = req.proof_ext in ('pdf', 'jpg', 'jpeg', 'png')
    resp = FileResponse(handle, content_type=ctype, as_attachment=not inline, filename=req.proof_name)
    resp['X-Content-Type-Options'] = 'nosniff'
    return resp
