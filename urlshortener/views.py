import enum
import logging
import random
import string
from string import Template
import re
import sys
from urllib.parse import urlsplit
from django.core.validators import ValidationError
from django.forms import URLField
from django.http import HttpResponse, HttpResponseRedirect, QueryDict
from django.shortcuts import render
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import generics, status
from .models import MAX_LONG_URL_LENGTH, UrlRecord, UrlMappingForm
from .serializers import UrlRecordSerializer


logging.basicConfig(
    format='[%(asctime)s] %(levelname)s {%(name)s:%(lineno)d} %(message)s',
    datefmt='%d/%b/%Y %H:%M:%S',
    level=logging.INFO
)

logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    '''Parse client's IP string from request.

    Args:
        request(Request): The incoming request.

    Returns:
        str: Client's IP string.
    '''
    if x_forwarded_for := request.META.get('HTTP_X_FORWARDED_FOR'):
        ip = x_forwarded_for.split(',')[-1]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip.strip()


def convert_to_absolute_url(url: str) -> str:
    '''Convert a relative URL like "python.org" to "http://python.org" by simple prepending.
    The url will remain untouched if it is already an absolute URL.

    Args:
        url(str): An URL.

    Returns:
        str: An absolute URL.
    '''

    try:
        if urlsplit(url).netloc:
            return url
        else:
            return 'http://' + url
    except:
        return url


def is_valid_long_url(url: str) -> bool:
    '''Check if the url is a valid aboslute URL.

    Args:
        url(str): The URL to check.

    Returns:
        bool: Whether the URL is valid or not.
    '''
    field = URLField()
    try:
        url = field.clean(url)
    except ValidationError:
        return False

    if len(url) > MAX_LONG_URL_LENGTH:
        return False
    return True


VALID_SHORT_URL_REGEX = r'(?P<short_url>^[A-Za-z0-9]{1,32}$)'
DEFAULT_SHORT_URL_LENGTH = 6


def is_valid_short_url(short_url: str) -> bool:
    '''Check if the short_url is a valid for REST API.

    Args:
        short_url (str): The short_url to check.

    Returns:
        bool: Whether the short_url is valid or not.
    '''
    if re.match(VALID_SHORT_URL_REGEX, short_url) is None:
        return False
    if short_url == 'api':
        return False
    return True


def generate_random_short_url(length: int = DEFAULT_SHORT_URL_LENGTH) -> str:
    '''Generate a uncollided short_url with certain length.

    Args:
        length(int, optional): The length of short_url. Defaults to DEFAULT_SHORT_URL_LENGTH.

    Raises:
        RuntimeError: Cannot generate a valid short_url.

    Returns:
        str: The generated short_url for REST API.
    '''
    CHAR_SET = string.ascii_letters + string.digits
    RETRY_LIMIT = 5

    for _ in range(RETRY_LIMIT):
        short_url = ''.join(random.sample(CHAR_SET, length))
        if not UrlRecord.objects.filter(short_url=short_url).exists():
            return short_url
    raise RuntimeError('Unable to generate any available random short_url!')


@enum.unique
class ErrorReason(enum.Enum):
    '''Aggregated class for REST API error codes.'''

    INTERNAL_SERVER_ERROR = 1000
    INVALID_LONG_URL = 1001
    INVALID_SHORT_URL = 1002
    SHORT_URL_ALREADY_EXISTS = 1003
    SHORT_URL_MAPPING_NOT_EXISTS = 1004
    MALFORMED_DATA = 1005


class UrlAPIErrorResponse(Response):
    '''Response class specialized for responding an REST API error.'''

    ATTRIBUTES_FOR_REASON = {
        ErrorReason.INTERNAL_SERVER_ERROR: {
            'title': 'Internal server error',
            'detail_template': Template("The server cannot handle this request."),
            'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
        },
        ErrorReason.INVALID_LONG_URL: {
            'title': 'Invalid long_url',
            'detail_template': Template("long_url:`$long_url` is not a valid URL"),
            'status_code': status.HTTP_400_BAD_REQUEST,
        },
        ErrorReason.INVALID_SHORT_URL: {
            'title': 'Invalid short_url',
            'detail_template': Template("short_url:`$short_url` cannot match pattern: ^[A-Za-z0-9]{1,32}$$"),
            'status_code': status.HTTP_400_BAD_REQUEST,
        },
        ErrorReason.SHORT_URL_ALREADY_EXISTS: {
            'title': 'short_url already exists',
            'detail_template': Template("short_url:`$short_url` is occupied. Please pick another short_url"),
            'status_code': status.HTTP_409_CONFLICT,
        },
        ErrorReason.SHORT_URL_MAPPING_NOT_EXISTS: {
            'title': 'short_url has no mapping',
            'detail_template': Template("There is no URL to redirect for short_url:`$short_url`"),
            'status_code': status.HTTP_404_NOT_FOUND,
        },
        ErrorReason.MALFORMED_DATA: {
            'title': 'Malformed data',
            'detail_template': Template('Are you malicious?'),
            'status_code': status.HTTP_400_BAD_REQUEST,
        },
    }

    def __init__(self, reason: ErrorReason, *, long_url: str = '', short_url: str = '') -> None:
        '''Build Response with JSON:API format error content according to reason.

        Args:
            reason(ErrorReason): The reason causing this UrlAPIErrorResponse.
            long_url(str, optional): Error triggerer's long_url. Defaults to ''.
            short_url(str, optional): Error triggerer's short_url. Defaults to ''.
        '''

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
    '''View class specialized for handling List and Create REST API.'''

    MAX_LIST_SIZE = 50
    queryset = UrlRecord.objects.all().order_by(
        '-last_activity_time')[:MAX_LIST_SIZE]
    serializer_class = UrlRecordSerializer

    def get(self, request: Request) -> Response:
        '''Handler for GET API listing recent URL mapping records.

        Args:
            request (Request): The incoming request.

        Returns:
            Response: Response for API listing URL mapping records.
        '''
        logger.info(Template('[$ip] API List: $data').substitute(
            ip=get_client_ip(request), data=request.data))
        try:
            serializer = UrlRecordSerializer(self.get_queryset(), many=True)
            return Response(serializer.data)
        except:
            logger.error('Unexpected error:', sys.exc_info()[0])

        return UrlAPIErrorResponse(ErrorReason.INTERNAL_SERVER_ERROR)

    def create(self, request: Request) -> Response:
        '''Handler for POST API creating a new URL mapping record.

        Args:
            request (Request): The incoming request.

        Returns:
            Response: Response for API creating a new URL mapping record.
        '''
        logger.info(Template('[$ip] API Create: $data').substitute(
            ip=get_client_ip(request), data=request.data))

        long_url = request.data.get('long_url', '')
        long_url = convert_to_absolute_url(long_url)
        if not is_valid_long_url(long_url):
            return UrlAPIErrorResponse(ErrorReason.INVALID_LONG_URL, long_url=long_url)

        short_url = request.data.get('short_url', '')
        if short_url == '':
            try:
                short_url = generate_random_short_url()
            except RuntimeError:
                return UrlAPIErrorResponse(ErrorReason.INVALID_SHORT_URL, short_url=short_url)

        if not is_valid_short_url(short_url):
            return UrlAPIErrorResponse(ErrorReason.INVALID_SHORT_URL, short_url=short_url)

        # Now both long_url and short_url should be valid.
        # Write long_url (converted to absolute URL) and short_url (maybe generated) back to data.
        data = request.data.copy()  # get a mutable copy
        data['long_url'] = long_url
        data['short_url'] = short_url
        data['visit_count'] = 0  # always start from zero

        serializer = UrlRecordSerializer(data=data)
        if serializer.is_valid():
            long_url = serializer.validated_data['long_url']
            short_url = serializer.validated_data['short_url']

            if UrlRecord.objects.filter(short_url=short_url).exists():
                return UrlAPIErrorResponse(ErrorReason.SHORT_URL_ALREADY_EXISTS, short_url=short_url)

            serializer.save()
            logger.info(Template('[$ip] Created mapping: `$short_url` -> `$long_url`').substitute(
                ip=get_client_ip(request), short_url=short_url, long_url=long_url))
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return UrlAPIErrorResponse(ErrorReason.MALFORMED_DATA)


class UrlRecordRetrieveView(generics.RetrieveAPIView):
    '''View class specialized for handling Retrieve REST API.'''

    serializer_class = UrlRecordSerializer

    def get(self, request: Request, short_url: str = '') -> Response:
        '''Handler for GET API retrieving an URL mapping record.

        Args:
            request (Request): The incoming request.
            short_url(str): Parsed from URL if the request was sent from Browsable API. Defaults to ''.

        Returns:
            Response: Response for API retrieving an URL mapping record.
        '''
        if short_url:
            # Request comes from Browsable API
            if short_url.endswith('/'):
                short_url = short_url[:-1]
        elif short_url := request.data.get('short_url', ''):
            # Request comes from GET body
            pass
        elif short_url := request.query_params.get('short_url', ''):
            # Request comes from URL param
            pass

        logger.info(Template('[$ip] API Retrieve: `$short_url`').substitute(
            ip=get_client_ip(request), short_url=short_url))

        if is_valid_short_url(short_url):
            try:
                record = UrlRecord.objects.get(short_url=short_url)
                serializer = UrlRecordSerializer(record)
                return Response(serializer.data)
            except:
                return UrlAPIErrorResponse(ErrorReason.SHORT_URL_MAPPING_NOT_EXISTS, short_url=short_url)

        return UrlAPIErrorResponse(ErrorReason.INVALID_SHORT_URL, short_url=short_url)


def handle_redirect(request: Request, short_url: str) -> Response:
    '''Handler for requesting a redirect from short_url.
    If failed to find the mapping record, return 404 Response.

    Args:
        request (Request): The incoming request.
        short_url (str): Requested short_url to redirect.

    Returns:
        Response: Redirect response.
    '''
    try:
        if record := UrlRecord.objects.get(short_url=short_url):
            record.visit_count += 1
            record.save()
            logger.info(Template('[$ip] Redirect `$short_url` -> `$long_url` (total $count times)').substitute(
                ip=get_client_ip(request), short_url=short_url, long_url=record.long_url, count=record.visit_count))
            return HttpResponseRedirect(record.long_url)
    except UrlRecord.DoesNotExist:
        pass
    except UrlRecord.MultipleObjectsReturned:
        logger.error(Template('[$ip] Impossible! Multiple mappings for short_url=`$short_url`').substitute(
            ip=get_client_ip(request), short_url=short_url))

    logger.info(Template('[$ip] Redirect `$short_url` failed...').substitute(
        ip=get_client_ip(request), short_url=short_url))
    response = render(request, 'redirect_failed.html')
    response.status_code = status.HTTP_404_NOT_FOUND
    return response


def index(request: Request) -> HttpResponse:
    '''Handler for requesting the index page of this app.

    Args:
        request (Request): The incoming request.

    Returns:
        Response: Http response.
    '''
    if request.method == 'POST':
        form = UrlMappingForm(request.POST)
        if form.is_valid():
            logger.info(Template('[$ip] POST valid form: `$data`').substitute(
                ip=get_client_ip(request), data=form.cleaned_data))
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
