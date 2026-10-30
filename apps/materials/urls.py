from django.urls import path
from . import views

urlpatterns = [
    path('', views.material_list, name='material_list'),
    path('upload/', views.material_upload, name='material_upload'),
    path('<int:material_id>/delete/', views.material_delete, name='material_delete'),
    path('<int:material_id>/file/', views.material_file, name='material_file'),
]
