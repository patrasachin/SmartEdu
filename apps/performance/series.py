"""Data for the individual performance graph: exam results and assignment ratings on one timeline."""
from django.conf import settings
from apps.assignments.models import AssignmentSubmission
from .models import PerformanceReport


def performance_series(student):
    events = []
    reports = PerformanceReport.objects.filter(student=student).select_related('exam').order_by('generated_at')
    for r in reports:
        events.append((r.generated_at, 'exam', r.exam.title if r.exam else 'Exam', round(r.percentage, 1)))
    rated = AssignmentSubmission.objects.filter(student=student, rating__isnull=False).select_related('assignment')
    for a in rated:
        events.append((a.reviewed_at or a.submitted_at, 'assignment', a.assignment.title, a.rating * 20.0))
    events.sort(key=lambda e: e[0])

    labels, exams, assignments, titles = [], [], [], []
    for when, kind, title, value in events:
        labels.append(f'{when:%d %b}')
        titles.append(('Exam: ' if kind == 'exam' else 'Assignment: ') + title)
        exams.append(value if kind == 'exam' else None)
        assignments.append(value if kind == 'assignment' else None)

    exam_vals = [e[3] for e in events if e[1] == 'exam']
    star_vals = [e[3] / 20 for e in events if e[1] == 'assignment']
    exam_avg = round(sum(exam_vals) / len(exam_vals), 1) if exam_vals else None
    rating_avg = round(sum(star_vals) / len(star_vals), 1) if star_vals else None
    parts = [v for v in (exam_avg, rating_avg * 20 if rating_avg is not None else None) if v is not None]
    overall = round(sum(parts) / len(parts), 1) if parts else None
    return {
        'chart': {'labels': labels, 'exams': exams, 'assignments': assignments, 'titles': titles,
                  'threshold': settings.AI_THRESHOLD_FAIL},
        'exam_avg': exam_avg, 'rating_avg': rating_avg, 'overall': overall,
        'exam_count': len(exam_vals), 'assignment_count': len(star_vals),
        'has_data': bool(events),
    }
