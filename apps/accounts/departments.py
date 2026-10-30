"""The fixed list of departments, and how many semesters each one has.

Every student belongs to one department and one semester. Exams, assignments and study material are sent to a
department and semester, and only the students in exactly that department and semester see them."""

DEPARTMENTS = [
    'Agricultural Engineering',
    'Applied Electronics and Instrumentation Engineering',
    'Applied Science & Humanities',
    'Bio Technology',
    'Chemical Engineering',
    'Civil Engineering',
    'Computer Science and Engineering (CSE)',
    'Computer Science & Engineering (AI & ML)',
    'CSE (Cyber Security)',
    'CSE (Data Science)',
    'Electrical Engineering',
    'Electronics & Communication Engineering (ECE)',
    'Food Technology',
    'Information Technology (IT)',
    'Mechanical Engineering',
    'Master of Business Administration (MBA)',
    'Master of Computer Applications (MCA)',
]

FOUR_SEMESTER = {
    'Master of Business Administration (MBA)',
    'Master of Computer Applications (MCA)',
}


def semester_count(department):
    """4 semesters for MBA and MCA, 8 for every other department."""
    return 4 if department in FOUR_SEMESTER else 8


def semester_label(n):
    return f'Semester {n}'


def department_choices():
    return list(DEPARTMENTS)


def dept_semester_map():
    return {d: semester_count(d) for d in DEPARTMENTS}


def check_pair(department, semester):
    """Returns an error text, or None when the department and semester go together."""
    if department not in DEPARTMENTS:
        return 'Choose a department from the list.'
    try:
        semester = int(semester)
    except (TypeError, ValueError):
        return 'Choose a semester.'
    if not 1 <= semester <= semester_count(department):
        return f'{department} has only {semester_count(department)} semesters.'
    return None


def students_in(department, semester):
    """Active students of exactly this department and semester."""
    from .models import User
    return User.objects.filter(role='STUDENT', is_active=True, student_profile__department=department,
                               student_profile__semester=semester)


def student_scope(user):
    """Filter arguments that match what a student is allowed to see: their department AND semester."""
    p = getattr(user, 'student_profile', None)
    if not p:
        return {'pk__in': []}
    return {'department': p.department, 'semester': p.semester}


def teacher_departments(user):
    """Departments a teacher may send work to. Everything by default (one teacher can teach many departments, for
    example Applied Science & Humanities); set TEACHER_LIMIT_TO_OWN_DEPARTMENT = True to allow only their own."""
    from django.conf import settings
    p = getattr(user, 'teacher_profile', None)
    if getattr(settings, 'TEACHER_LIMIT_TO_OWN_DEPARTMENT', False) and p and p.department in DEPARTMENTS:
        return [p.department]
    return department_choices()


def pair_label(department, semester):
    return f'{department}, {semester_label(semester)}'
