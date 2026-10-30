from django.conf import settings
from django.db.models import Avg
from apps.performance.models import PerformanceReport


def calculate_understanding_score(percentage):
    if percentage >= 85:
        return 'Excellent'
    if percentage >= 70:
        return 'Good'
    if percentage >= 50:
        return 'Average'
    return 'Weak'


def analyze_performance(student_user):
    reports = PerformanceReport.objects.filter(student=student_user).order_by('generated_at')
    threshold = getattr(settings, 'AI_THRESHOLD_FAIL', 70)
    if not reports.exists():
        return {'avg_percentage': 0, 'trend': 'No data yet', 'understanding': 'Not evaluated yet',
                'total_exams': 0, 'improvement_needed': False, 'best': None}
    avg = reports.aggregate(Avg('percentage'))['percentage__avg'] or 0
    values = list(reports.values_list('percentage', flat=True))
    if len(values) >= 2:
        half = max(1, len(values) // 2)
        earlier, recent = values[:-half], values[-half:]
        diff = sum(recent) / len(recent) - sum(earlier) / len(earlier)
        trend = 'Improving' if diff > 2 else 'Declining' if diff < -2 else 'Steady'
    else:
        trend = 'Steady' if avg >= threshold else 'Needs attention'
    levels = [(85, 'Excellent: concepts are clear'), (70, 'Good: only minor gaps'),
              (50, 'Average: needs more practice'), (0, 'Weak: needs extra support')]
    understanding = next(text for cut, text in levels if avg >= cut)
    return {'avg_percentage': round(avg, 1), 'trend': trend, 'understanding': understanding,
            'total_exams': len(values), 'improvement_needed': avg < threshold, 'best': round(max(values), 1)}
