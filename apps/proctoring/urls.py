from django.urls import path
from . import views

urlpatterns = [
    path('log/', views.log_violation, name='log_violation'),
    path('frame/', views.check_frame, name='check_frame'),
    path('count/<int:submission_id>/', views.violation_count, name='violation_count'),
]
