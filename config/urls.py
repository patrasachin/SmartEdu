from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.accounts.views import home_redirect

urlpatterns = [
    path('', home_redirect, name='home'),
    path('django-admin/', admin.site.urls),
    path('auth/', include('apps.accounts.urls')),
    path('admin-portal/', include('apps.admin_portal.urls')),
    path('teacher/', include('apps.teacher.urls')),
    path('student/', include('apps.student.urls')),
    path('exams/', include('apps.exams.urls')),
    path('attendance/', include('apps.attendance.urls')),
    path('performance/', include('apps.performance.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('proctoring/', include('apps.proctoring.urls')),
    path('materials/', include('apps.materials.urls')),
    path('assignments/', include('apps.assignments.urls')),
    path('reattempt/', include('apps.reattempt.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
