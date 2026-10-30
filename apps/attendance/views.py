from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


@login_required
def attendance_list(request):
    if request.user.role == 'STUDENT':
        return redirect('student_attendance')
    if request.user.role == 'TEACHER':
        return redirect('teacher_attendance')
    return redirect('admin_dashboard')
