from django.urls import path
from rest_framework import routers
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/v1/urls', views.UrlRecordListCreateView.as_view()),
    path('api/v1/urls/', views.UrlRecordRetrieveView.as_view()),
]
