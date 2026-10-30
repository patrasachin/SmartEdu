from django.urls import path
from . import views
urlpatterns = [
    path('', views.attendance_list, name='attendance_list'),
]
