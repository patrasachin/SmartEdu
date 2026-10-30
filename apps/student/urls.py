from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='student_dashboard'),
    path('exams/', views.exams_view, name='student_exams'),
    path('exams/<int:exam_id>/instructions/', views.exam_instructions, name='exam_instructions'),
    path('exams/<int:exam_id>/take/', views.take_exam, name='take_exam'),
    path('attendance/', views.attendance_view, name='student_attendance'),
    path('performance/', views.performance_view, name='student_performance'),
    path('notifications/', RedirectView.as_view(pattern_name='notification_list'), name='student_notifications'),
    path('result/<int:submission_id>/', views.result_view, name='student_result'),
]
