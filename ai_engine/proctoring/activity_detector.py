from django.conf import settings


def detect_suspicious_activity(logs):
    """Summarises a list of violation logs."""
    count = len(logs)
    limit = getattr(settings, 'AI_PROCTORING_MAX_VIOLATIONS', 3)
    return {'violation_count': count, 'should_cancel': count >= limit,
            'risk_level': 'HIGH' if count >= limit - 1 else 'MEDIUM' if count == 1 else 'LOW'}
