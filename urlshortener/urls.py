from django.urls import path, re_path
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from . import views

app_name = 'urlshortener'

LIST_CREATE_URL_API_ENDPOINT = 'api/v1/urls'
RETRIEVE_URL_API_ENDPOINT = 'api/v1/urls/'

schema_view = get_schema_view(
    openapi.Info(
        title='URL Shortener RESTful API',
        default_version='v1',
        contact=openapi.Contact(
            url='https://github.com/randalhsu/django-url-shortener'),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('', views.index, name='index'),
    path(LIST_CREATE_URL_API_ENDPOINT,
         views.UrlRecordListCreateView.as_view(), name='list_create_url'),
    re_path(RETRIEVE_URL_API_ENDPOINT +
            '(?P<short_url>[A-Za-z0-9]{1,32}/?)?$', views.UrlRecordRetrieveView.as_view(), name='retrieve_url'),
    re_path(views.VALID_SHORT_URL_REGEX,
            views.handle_redirect, name='redirect'),
    path(r'swagger/', schema_view.with_ui('swagger',
                                          cache_timeout=0), name='schema-swagger-ui'),
]
