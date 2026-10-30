from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='admin_dashboard'),
    path('students/', views.students_list, name='admin_students'),
    path('students/register/', views.register_student, name='register_student'),
    path('teachers/', views.teachers_list, name='admin_teachers'),
    path('teachers/register/', views.register_teacher, name='register_teacher'),
    path('students/<int:user_id>/edit/', views.student_edit, name='student_edit'),
    path('teachers/<int:user_id>/edit/', views.teacher_edit, name='teacher_edit'),
    path('users/<int:user_id>/delete/', views.delete_user, name='delete_user'),
    path('emails/', views.emails_list, name='admin_emails'),
    path('emails/test/', views.email_test, name='email_test'),
    path('users/<int:user_id>/toggle/', views.toggle_active, name='toggle_user'),
    path('users/<int:user_id>/reset-password/', views.reset_password, name='reset_password'),
    path('departments/', views.departments_view, name='admin_departments'),
    path('exams/', views.exams_overview, name='admin_exams'),
    path('announce/', views.announce, name='admin_announce'),
]
