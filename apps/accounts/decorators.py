from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """Allow only signed-in users whose role is in `roles`; everyone else gets 403 (or the login page)."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


admin_required = role_required('ADMIN')
teacher_required = role_required('TEACHER')
student_required = role_required('STUDENT')
