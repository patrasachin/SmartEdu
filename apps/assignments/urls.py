from django.urls import path
from . import views

urlpatterns = [
    path('', views.assignment_list, name='assignment_list'),
    path('new/', views.assignment_create, name='assignment_create'),
    path('<int:assignment_id>/', views.assignment_detail, name='assignment_detail'),
    path('<int:assignment_id>/submit/', views.assignment_submit, name='assignment_submit'),
    path('<int:assignment_id>/delete/', views.assignment_delete, name='assignment_delete'),
    path('submission/<int:submission_id>/review/', views.submission_review, name='submission_review'),
    path('submission/<int:submission_id>/file/', views.submission_file, name='submission_file'),
]
