from django.urls import path
from . import views

urlpatterns = [
    path('submit/<int:exam_id>/', views.submit_exam, name='submit_exam'),
    path('save/<int:exam_id>/', views.save_progress, name='save_progress'),
    path('api/list/', views.exam_list_api, name='exam_list_api'),
]
