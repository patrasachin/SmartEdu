from django.db.models import Sum
from django.utils import timezone


def refresh_exam_totals(exam):
    """Keep total_marks and exam_type in step with the questions."""
    qs = exam.questions.all()
    exam.total_marks = qs.aggregate(t=Sum('marks'))['t'] or 0
    kinds = set(qs.values_list('qtype', flat=True))
    exam.exam_type = 'MIXED' if len(kinds) > 1 else (kinds.pop() if kinds else 'MCQ')
    exam.save(update_fields=['total_marks', 'exam_type'])


def seconds_left(submission):
    """Time left for a submission, measured on the server so refreshing can't reset the clock."""
    end = submission.started_at + timezone.timedelta(minutes=submission.exam.duration_minutes)
    return max(0, int((end - timezone.now()).total_seconds()))


def is_closed(exam, now=None):
    """True once the teacher's closing time has passed (an exam without a closing time never closes)."""
    now = now or timezone.now()
    return exam.closes_at is not None and now > exam.closes_at


def student_extension(exam, student):
    """The approved re-attempt chance for this student only, if it is still open."""
    from apps.reattempt.models import ReattemptRequest
    req = ReattemptRequest.objects.filter(exam=exam, student=student, status='APPROVED').first()
    return req if req and req.chance_is_open else None


def exam_state(exam, submission=None, extension=None):
    """upcoming | open | done | cancelled | missed
    missed = the closing time passed and the student never started (and has no open extra chance)."""
    if submission is not None:
        if submission.is_cancelled:
            return 'cancelled'
        if submission.is_completed:
            return 'done'
    now = timezone.now()
    if exam.scheduled_at > now:
        return 'upcoming'
    if submission is not None:          # started but not finished: they may carry on
        return 'open'
    if is_closed(exam, now) and extension is None:
        return 'missed'
    return 'open'
