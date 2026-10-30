"""Emails to students' guardians: exam results and attendance.

Every attempt is saved in EmailLog (shown to admins). With no SMTP settings the console backend prints the
email in the terminal instead of sending it, so everything can be tried without an email account."""
from django.conf import settings
from django.core.mail import EmailMessage, get_connection

from .models import EmailLog


def _guardian(student):
    p = getattr(student, 'student_profile', None)
    return (p.guardian_email, p.guardian_name or 'Parent / Guardian', f'{p.department}, Semester {p.semester}') if p else ('', 'Parent / Guardian', '')


def _deliver(items):
    """items: dicts with student, to, subject, body, kind, key. Sends them over one connection and logs each."""
    items = [i for i in items if i['to']]
    items = [i for i in items if not (i['key'] and EmailLog.objects.filter(key=i['key'], status='SENT').exists())]
    if not items:
        return 0
    sent = 0
    conn = get_connection()
    open_error = ''
    try:
        conn.open()
    except Exception as exc:            # could not connect: record every email as failed
        open_error = str(exc)[:500] or 'Could not connect to the mail server.'
    for it in items:
        status, error = 'SENT', ''
        if open_error:
            status, error = 'FAILED', open_error
        else:
            try:
                EmailMessage(it['subject'], it['body'], settings.DEFAULT_FROM_EMAIL, [it['to']], connection=conn).send()
                sent += 1
            except Exception as exc:
                status, error = 'FAILED', str(exc)[:500]
        EmailLog.objects.create(student=it['student'], to_email=it['to'], subject=it['subject'], body=it['body'],
                                kind=it['kind'], key=it['key'], status=status, error=error)
    try:
        conn.close()
    except Exception:
        pass
    return sent


def _name(student):
    return student.get_full_name() or student.username


FOOTER = '\n\nRegards,\nSmartEdu\nThis is an automatic message. Please do not reply.'


def send_guardian_result(submission):
    """Result email after an exam is submitted and marked."""
    student, exam = submission.student, submission.exam
    to, gname, dept = _guardian(student)
    low = settings.AI_THRESHOLD_FAIL
    lines = [f'Dear {gname},', '',
             f'{_name(student)} ({dept}) has completed the exam "{exam.title}" ({exam.subject}).', '',
             f'Score: {submission.total_score:g} out of {exam.total_marks}',
             f'Percentage: {submission.percentage:.1f}%']
    from apps.performance.models import PerformanceReport
    rep = PerformanceReport.objects.filter(student=student, exam=exam).first()
    if rep:
        lines.append(f'Understanding level: {rep.understanding_level}')
    weak = sorted({a.question.topic or 'General' for a in submission.answers.select_related('question') if a.is_correct is False})
    if weak:
        lines.append('Topics to revise: ' + ', '.join(weak))
    if submission.percentage < low:
        lines += ['', f'The score is below {low}%. Please encourage regular revision. The teacher can give more guidance.']
    else:
        lines += ['', 'Good work. Please keep encouraging regular study.']
    return _deliver([{'student': student, 'to': to, 'kind': 'RESULT', 'key': f'result-{submission.id}',
                      'subject': f'SmartEdu: {_name(student)} scored {submission.percentage:.0f}% in {exam.title}',
                      'body': '\n'.join(lines) + FOOTER}])


def send_guardian_cancelled(submission):
    student, exam = submission.student, submission.exam
    to, gname, dept = _guardian(student)
    body = (f'Dear {gname},\n\nThe exam "{exam.title}" ({exam.subject}) taken by {_name(student)} ({dept}) was cancelled '
            f'because of repeated rule violations during the exam.\n\n{submission.cancel_reason}\n\n'
            'The teacher will review it. A re-attempt may be allowed.' + FOOTER)
    return _deliver([{'student': student, 'to': to, 'kind': 'CANCELLED', 'key': f'cancelled-{submission.id}',
                      'subject': f'SmartEdu: exam cancelled for {_name(student)} ({exam.title})', 'body': body}])


def send_guardian_attendance(records):
    """records: list of (student, date, status, department). One email per student per day and status."""
    label = {'PRESENT': 'PRESENT', 'LATE': 'PRESENT (arrived late)', 'ABSENT': 'ABSENT'}
    items = []
    for student, date, status, dept in records:
        to, gname, _ = _guardian(student)
        verdict = label.get(status, status)
        lines = [f'Dear {gname},', '',
                 f'Attendance for {_name(student)} ({dept}) on {date:%A, %d %B %Y}: {verdict}.']
        if status == 'ABSENT':
            lines.append('If this absence was planned, please inform the department office.')
        items.append({'student': student, 'to': to, 'kind': 'ATTENDANCE', 'key': f'att-{student.id}-{date.isoformat()}-{status}',
                      'subject': f'SmartEdu attendance: {_name(student)} is {verdict.split(" (")[0].lower()} on {date:%d %b}',
                      'body': '\n'.join(lines) + FOOTER})
    return _deliver(items)


def send_test_email(to, requested_by=None):
    body = 'This is a test email from SmartEdu. If you can read it, guardian emails will reach you.' + FOOTER
    return _deliver([{'student': None, 'to': to, 'kind': 'TEST', 'key': '', 'subject': 'SmartEdu test email', 'body': body}])
