def notifications(request):
    """Adds the unread count, plus small badges for things waiting on the user."""
    if not request.user.is_authenticated:
        return {'unread_notifications': 0}
    from .models import Notification
    user = request.user
    ctx = {'unread_notifications': Notification.objects.filter(recipient=user, is_read=False).count(),
           'badge_reattempts': 0, 'badge_reviews': 0, 'badge_assignments': 0, 'badge_missed': 0}
    if user.role == 'TEACHER':
        from apps.reattempt.models import ReattemptRequest
        from apps.assignments.models import AssignmentSubmission
        ctx['badge_reattempts'] = ReattemptRequest.objects.filter(exam__created_by=user, status='PENDING').count()
        ctx['badge_reviews'] = AssignmentSubmission.objects.filter(assignment__created_by=user, rating__isnull=True).count()
    elif user.role == 'STUDENT':
        profile = getattr(user, 'student_profile', None)
        if profile:
            from django.utils import timezone
            from apps.assignments.models import Assignment
            from apps.exams.models import Exam
            from apps.reattempt.models import ReattemptRequest
            ctx['badge_assignments'] = Assignment.objects.filter(department=profile.department, semester=profile.semester).exclude(
                submissions__student=user).count()
            ctx['badge_missed'] = Exam.objects.filter(
                department=profile.department, semester=profile.semester, status='PUBLISHED', closes_at__lt=timezone.now()).exclude(
                submissions__student=user).exclude(reattempt_requests__student=user).count()
    return ctx
