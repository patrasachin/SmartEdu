from django.urls import path
from . import views

urlpatterns = [
    path('', views.reattempt_list, name='reattempt_list'),
    path('new/<int:exam_id>/', views.reattempt_new, name='reattempt_new'),
    path('<int:request_id>/decide/', views.reattempt_decide, name='reattempt_decide'),
    path('<int:request_id>/proof/', views.reattempt_proof, name='reattempt_proof'),
]
