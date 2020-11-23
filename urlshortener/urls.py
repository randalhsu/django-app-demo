from django.urls import path, re_path
from rest_framework import routers
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/v1/urls', views.UrlRecordListCreateView.as_view(),
         name='list_create_url'),
    path('api/v1/urls/', views.UrlRecordRetrieveView.as_view(), name='retrieve_url'),
    re_path(views.VALID_SHORT_URL_REGEX,
            views.handle_redirect, name='redirect'),
]
