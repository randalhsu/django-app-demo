import enum
import logging
import random
import string
import re
from urllib.parse import urlsplit
from django.core.validators import ValidationError
from django.forms import URLField
from django.http import HttpResponseRedirect, QueryDict
from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import generics, status
from .models import UrlRecord, UrlMappingForm
from .serializers import UrlRecordSerializer


logging.basicConfig(
    format='[%(asctime)s] %(levelname)s {%(name)s:%(lineno)d} %(message)s',
    datefmt='%d/%b/%Y %H:%M:%S',
    level=logging.INFO
)

logger = logging.getLogger(__name__)


def get_client_ip(request):
    if x_forwarded_for := request.META.get('HTTP_X_FORWARDED_FOR'):
        ip = x_forwarded_for.split(',')[-1]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip.strip()


def convert_to_absolute_url(url: str) -> str:
    try:
        if urlsplit(url).netloc:
            return url
        else:
            return 'http://' + url
    except:
        return url


def is_valid_long_url(url: str) -> bool:
    field = URLField()
    try:
        url = field.clean(url)
    except ValidationError:
        return False
    return True


VALID_SHORT_URL_REGEX = r'(?P<short_url>^[A-Za-z0-9]{1,32}$)'
DEFAULT_SHORT_URL_LENGTH = 6


def is_valid_short_url(url: str) -> bool:
    if re.match(VALID_SHORT_URL_REGEX, url) is None:
        return False
    if url == 'api':
        return False
    return True


def generate_random_short_url(length: int = DEFAULT_SHORT_URL_LENGTH) -> str:
    '''Return a uncollided short_url with length.'''
    CHAR_SET = string.ascii_letters + string.digits
    RETRY_LIMIT = 5

    for _ in range(RETRY_LIMIT):
        short_url = ''.join(random.sample(CHAR_SET, length))
        if not UrlRecord.objects.filter(short_url=short_url).exists():
            return short_url

    logger.error(f'Unable to generate any available random short_url!')
    return ''


@enum.unique
class ErrorReason(enum.Enum):
    INVALID_LONG_URL = 1001
    INVALID_SHORT_URL = 1002
    SHORT_URL_ALREADY_EXISTS = 1003
    SHORT_URL_MAPPING_NOT_EXISTS = 1004
    MALFORMED_DATA = 1005


class UrlAPIErrorResponse(Response):
    ATTRIBUTES_FOR_REASON = {
        ErrorReason.INVALID_LONG_URL: {
            'title': 'Invalid long_url',
            'detail_template': string.Template("long_url:`$long_url` is not a valid URL"),
            'status_code': status.HTTP_400_BAD_REQUEST,
        },
        ErrorReason.INVALID_SHORT_URL: {
            'title': 'Invalid short_url',
            'detail_template': string.Template("short_url:`$short_url` cannot match pattern: ^[A-Za-z0-9]{1,32}$$"),
            'status_code': status.HTTP_400_BAD_REQUEST,
        },
        ErrorReason.SHORT_URL_ALREADY_EXISTS: {
            'title': 'short_url already exists',
            'detail_template': string.Template("short_url:`$short_url` is occupied. Please pick another short_url"),
            'status_code': status.HTTP_409_CONFLICT,
        },
        ErrorReason.SHORT_URL_MAPPING_NOT_EXISTS: {
            'title': 'short_url has no mapping',
            'detail_template': string.Template("There is no URL to redirect for short_url:`$short_url`"),
            'status_code': status.HTTP_404_NOT_FOUND,
        },
        ErrorReason.MALFORMED_DATA: {
            'title': 'Malformed data',
            'detail_template': string.Template('Are you malicious?'),
            'status_code': status.HTTP_400_BAD_REQUEST,
        },
    }

    def __init__(self, reason: ErrorReason, *, long_url: str = '', short_url: str = '') -> None:
        '''Build Response with JSON:API format error content according to reason.'''

        attributes = type(self).ATTRIBUTES_FOR_REASON[reason]
        status_code = attributes['status_code']

        error = {
            'code': str(reason.value),
            'title': attributes['title'],
            'detail': attributes['detail_template'].substitute(long_url=long_url, short_url=short_url),
            'status': str(status_code),
        }
        super().__init__({'errors': [error]}, status=status_code)


class UrlRecordListCreateView(generics.ListCreateAPIView):
    MAX_RECORDS = 10
    serializer_class = UrlRecordSerializer

    def get(self, request):
        logger.info(f'[{get_client_ip(request)}] API List: {request.data}')
        records = UrlRecord.objects.all().order_by(
            '-last_activity_time')[:type(self).MAX_RECORDS]
        serializer = UrlRecordSerializer(records, many=True)
        return Response(serializer.data)

    def create(self, request, format=None):
        logger.info(f'[{get_client_ip(request)}] API Create: {request.data}')
        long_url = request.data.get('long_url', '')
        long_url = convert_to_absolute_url(long_url)
        if not is_valid_long_url(long_url):
            return UrlAPIErrorResponse(ErrorReason.INVALID_LONG_URL, long_url=long_url)

        short_url = request.data.get('short_url', '')
        if short_url == '':
            short_url = generate_random_short_url()

        data = request.data.copy()  # get a mutable copy
        data['long_url'] = long_url
        data['short_url'] = short_url

        serializer = UrlRecordSerializer(data=data)
        if serializer.is_valid():
            long_url = serializer.validated_data['long_url']
            short_url = serializer.validated_data['short_url']

            if not is_valid_short_url(short_url):
                return UrlAPIErrorResponse(ErrorReason.INVALID_SHORT_URL, short_url=short_url)

            if UrlRecord.objects.filter(short_url=short_url).exists():
                return UrlAPIErrorResponse(ErrorReason.SHORT_URL_ALREADY_EXISTS, short_url=short_url)

            serializer.save()
            logger.info(
                f'[{get_client_ip(request)}] Created mapping: "{short_url}" -> "{long_url}"')
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return UrlAPIErrorResponse(ErrorReason.MALFORMED_DATA)


class UrlRecordRetrieveView(generics.RetrieveAPIView):
    serializer_class = UrlRecordSerializer

    def get(self, request, format=None):
        logger.info(
            f'[{get_client_ip(request)}] API Retrieve: {request.data} / {request.query_params}')
        for params in (request.data, request.query_params):
            if short_url := params.get('short_url', ''):
                if is_valid_short_url(short_url):
                    try:
                        record = UrlRecord.objects.get(short_url=short_url)
                        serializer = UrlRecordSerializer(record)
                        return Response(serializer.data)
                    except:
                        return UrlAPIErrorResponse(ErrorReason.SHORT_URL_MAPPING_NOT_EXISTS, short_url=short_url)
                else:
                    return UrlAPIErrorResponse(ErrorReason.INVALID_SHORT_URL, short_url=short_url)

        return UrlAPIErrorResponse(ErrorReason.INVALID_SHORT_URL)


def handle_redirect(request, short_url):
    try:
        if record := UrlRecord.objects.get(short_url=short_url):
            record.visit_count += 1
            record.save()
            logger.info(
                f'[{get_client_ip(request)}] Redirect "{short_url}" -> {record.long_url} (Total {record.visit_count} times)')
            return HttpResponseRedirect(record.long_url)
    except UrlRecord.DoesNotExist:
        pass
    except UrlRecord.MultipleObjectsReturned:
        logger.error(
            f'Impossible! Multiple mappings for short_url={short_url}')

    logger.info(f'[{get_client_ip(request)}] Redirect "{short_url}" failed...')
    response = render(request, 'redirect_failed.html')
    response.status_code = status.HTTP_404_NOT_FOUND
    return response


def index(request):
    if request.method == 'POST':
        form = UrlMappingForm(request.POST)
        if form.is_valid():
            logger.info(
                f'[{get_client_ip(request)}] POST valid form: {form.cleaned_data}')
            query_dict = QueryDict(mutable=True)
            query_dict.update(form.cleaned_data)
            request.data = query_dict
            response = UrlRecordListCreateView().create(request)
            context = {
                'form': form,
                'status_code': response.status_code,
                'data': response.data
            }
            return render(request, 'index.html', context)
    else:
        form = UrlMappingForm()

    return render(request, 'index.html', {'form': form})
