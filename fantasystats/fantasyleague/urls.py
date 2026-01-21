from django.urls import path
from . import views

app_name = 'fantasyleague'

urlpatterns = [
    path('', views.index, name='index'),
    path('teams/', views.team_list, name='team_list'),
    path('teams/<int:team_id>/', views.team_detail, name='team_detail'),
    path('teams/<int:team_id>/insights/', views.team_insights, name='team_insights'),
]
