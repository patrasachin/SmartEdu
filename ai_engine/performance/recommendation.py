from urllib.parse import quote_plus
from .weak_topic_detector import get_weak_topics
from apps.performance.models import Recommendation

# Hand-picked links for common topics; everything else gets search links built from the topic name.
KNOWN = {
    'algebra': [('Khan Academy: Algebra basics', 'https://www.khanacademy.org/math/algebra', 'Revise the fundamentals step by step')],
    'calculus': [('Khan Academy: Calculus 1', 'https://www.khanacademy.org/math/calculus-1', 'Limits, derivatives and integrals')],
    'geometry': [('Khan Academy: Geometry', 'https://www.khanacademy.org/math/geometry', 'Shapes, angles and proofs')],
    'photosynthesis': [('Khan Academy: Photosynthesis', 'https://www.khanacademy.org/science/biology/photosynthesis-in-plants', 'How plants turn light into food')],
}


def resources_for(topic):
    key = topic.strip().lower()
    items = list(KNOWN.get(key, []))
    q = quote_plus(topic)
    items.append((f'Watch: {topic} explained', f'https://www.youtube.com/results?search_query={q}+explained', 'Short video lessons'))
    if key not in KNOWN:
        items.insert(0, (f'Khan Academy: {topic}', f'https://www.khanacademy.org/search?page_search_query={q}', 'Lessons and practice'))
    return items


def generate_recommendations(student_user):
    recs = []
    for wt in get_weak_topics(student_user):
        for title, link, desc in resources_for(wt.topic):
            rec, _ = Recommendation.objects.get_or_create(
                student=student_user, topic=wt.topic, title=title,
                defaults={'resource_link': link, 'description': desc})
            recs.append(rec)
    return recs
