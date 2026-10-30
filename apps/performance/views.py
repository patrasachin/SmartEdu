from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


@login_required
def performance_dashboard(request):
    if request.user.role == 'STUDENT':
        return redirect('student_performance')
    if request.user.role == 'TEACHER':
        return redirect('teacher_performance')
    return redirect('admin_dashboard')
