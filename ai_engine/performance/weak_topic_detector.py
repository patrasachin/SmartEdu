from apps.performance.models import WeakTopic


def detect_weak_topics(student_user, submission):
    """A topic is weak when half or more of its questions were answered wrongly.
    Topics that were weak before but are now answered well are marked as improved."""
    stats = {}
    for ans in submission.answers.select_related('question', 'question__exam'):
        topic = ans.question.topic.strip() or 'General'
        subject = ans.question.exam.subject
        s = stats.setdefault((topic, subject), {'wrong': 0, 'total': 0})
        s['total'] += 1
        if ans.is_correct is False:
            s['wrong'] += 1

    for (topic, subject), s in stats.items():
        wrong_rate = s['wrong'] / s['total']
        score_pct = (1 - wrong_rate) * 100
        existing = WeakTopic.objects.filter(student=student_user, topic=topic, subject=subject).first()
        if wrong_rate >= 0.5:
            if existing:
                existing.failure_count += 1
                existing.avg_score_in_topic = (existing.avg_score_in_topic + score_pct) / 2
                existing.is_improved = False
                existing.save()
            else:
                WeakTopic.objects.create(student=student_user, topic=topic, subject=subject,
                                         failure_count=1, avg_score_in_topic=score_pct)
        elif existing and not existing.is_improved:
            existing.is_improved = True
            existing.avg_score_in_topic = score_pct
            existing.save()


def get_weak_topics(student_user):
    return WeakTopic.objects.filter(student=student_user, is_improved=False).order_by('-failure_count')
