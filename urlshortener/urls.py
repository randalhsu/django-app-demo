from django.urls import path, re_path
from . import views

LIST_CREATE_URL_API_ENDPOINT = 'api/v1/urls'
RETRIEVE_URL_API_ENDPOINT = 'api/v1/urls/'

urlpatterns = [
    path('', views.index, name='index'),
    path(LIST_CREATE_URL_API_ENDPOINT,
         views.UrlRecordListCreateView.as_view(), name='list_create_url'),
    re_path(RETRIEVE_URL_API_ENDPOINT +
            '(?P<short_url>[A-Za-z0-9]{1,32}/?)?$', views.UrlRecordRetrieveView.as_view(), name='retrieve_url'),
    re_path(views.VALID_SHORT_URL_REGEX,
            views.handle_redirect, name='redirect'),
]
