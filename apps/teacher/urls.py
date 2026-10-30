from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='teacher_dashboard'),
    path('exams/', views.exams_list, name='teacher_exams'),
    path('create-exam/', views.create_exam, name='create_exam'),
    path('exams/<int:exam_id>/edit/', views.edit_exam, name='edit_exam'),
    path('exams/<int:exam_id>/publish/', views.toggle_publish, name='toggle_publish'),
    path('exams/<int:exam_id>/delete/', views.delete_exam, name='delete_exam'),
    path('exams/<int:exam_id>/questions/', views.questions_view, name='teacher_questions'),
    path('questions/<int:question_id>/delete/', views.delete_question, name='delete_question'),
    path('exams/<int:exam_id>/answer-key/', views.answer_key_view, name='answer_key'),
    path('results/', views.results_view, name='teacher_results'),
    path('results/<int:exam_id>/', views.results_view, name='teacher_results_exam'),
    path('submission/<int:submission_id>/', views.submission_detail, name='submission_detail'),
    path('submission/<int:submission_id>/reset/', views.reset_submission, name='reset_submission'),
    path('evaluate/<int:exam_id>/', views.auto_evaluate, name='auto_evaluate'),
    path('students/', views.students_view, name='teacher_students'),
    path('students/<int:student_id>/', views.student_detail, name='teacher_student_detail'),
    path('attendance/', views.attendance_view, name='teacher_attendance'),
    path('performance/', views.performance_view, name='teacher_performance'),
]
