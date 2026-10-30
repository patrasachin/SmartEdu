import mimetypes
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from apps.accounts.decorators import teacher_required
from apps.accounts.departments import DEPARTMENTS, semester_count, student_scope, students_in
from apps.accounts.models import User
from apps.notifications.models import Notification
from .forms import MaterialForm
from .models import StudyMaterial


@login_required
def material_list(request):
    user = request.user
    if user.role == 'STUDENT':
        qs = StudyMaterial.objects.filter(**student_scope(user)).select_related('uploaded_by')
        subjects = sorted(set(qs.values_list('subject', flat=True)))
        subject, kind, q = request.GET.get('subject', ''), request.GET.get('type', ''), request.GET.get('q', '').strip()
        if subject:
            qs = qs.filter(subject=subject)
        items = list(qs)
        if kind:
            items = [m for m in items if m.kind_label == kind]
        if q:
            items = [m for m in items if q.lower() in (m.title + ' ' + m.description).lower()]
        p = user.student_profile
        return render(request, 'materials/student_list.html', {
            'items': items, 'subjects': subjects, 'subject': subject, 'kind': kind, 'q': q,
            'kinds': ['PDF', 'Word', 'PowerPoint', 'Excel', 'Link'], 'my_department': p.department, 'my_semester': p.semester})
    if user.role == 'TEACHER':
        qs = StudyMaterial.objects.filter(uploaded_by=user)
        dept, sem = request.GET.get('department', ''), request.GET.get('semester', '')
        if dept:
            qs = qs.filter(department=dept)
        if sem.isdigit():
            qs = qs.filter(semester=int(sem))
        return render(request, 'materials/teacher_list.html', {
            'items': qs, 'departments': DEPARTMENTS, 'dept': dept, 'sem': sem,
            'semesters': list(range(1, (semester_count(dept) if dept else 8) + 1))})
    return redirect('admin_dashboard')


@teacher_required
def material_upload(request):
    profile = getattr(request.user, 'teacher_profile', None)
    form = MaterialForm(request.POST or None, request.FILES or None, user=request.user,
                        subject_default=profile.subject if profile else '')
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        m = StudyMaterial(title=d['title'].strip(), description=d['description'].strip(), subject=d['subject'].strip(),
                          department=d['department'], semester=d['semester'], link=d['link'], uploaded_by=request.user)
        if d['file']:
            m.file = d['file']
        m.save()
        Notification.objects.bulk_create([
            Notification(recipient=s, sender=request.user, title=f'New study material: {m.title}',
                         message=f'{m.subject}, shared by {request.user.get_full_name() or request.user.username}.', ntype='GENERAL')
            for s in students_in(m.department, m.semester)])
        messages.success(request, f'Shared with {m.department}, Semester {m.semester}. Students were notified.')
        return redirect('material_list')
    return render(request, 'materials/upload.html', {'form': form})


@teacher_required
@require_POST
def material_delete(request, material_id):
    m = get_object_or_404(StudyMaterial, id=material_id, uploaded_by=request.user)
    name = m.file.name
    m.delete()
    # remove the stored file only when no other record still uses it
    if name and not StudyMaterial.objects.filter(file=name).exists():
        m.file.storage.delete(name)
    messages.success(request, 'Study material removed.')
    return redirect('material_list')


@login_required
def material_file(request, material_id):
    """Authenticated download: only the owner teacher and students of that class may open a file."""
    m = get_object_or_404(StudyMaterial, id=material_id)
    user = request.user
    p = getattr(user, 'student_profile', None)
    allowed = (user.role == 'ADMIN' or m.uploaded_by_id == user.id
               or (user.role == 'STUDENT' and p is not None and (p.department, p.semester) == (m.department, m.semester)))
    if not allowed:
        raise PermissionDenied
    if not m.file:
        raise Http404
    try:
        handle = m.file.open('rb')
    except (OSError, ValueError):
        raise Http404('The file is missing from the server.')
    ctype = mimetypes.guess_type(m.filename)[0] or 'application/octet-stream'
    inline = m.extension in ('pdf', 'txt')
    resp = FileResponse(handle, content_type=ctype, as_attachment=not inline, filename=m.filename)
    resp['X-Content-Type-Options'] = 'nosniff'
    return resp
