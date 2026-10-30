from .departments import dept_semester_map


def departments(request):
    """Lets the department and semester drop-downs know how many semesters each department has."""
    return {'DEPT_SEM_MAP': dept_semester_map()}
