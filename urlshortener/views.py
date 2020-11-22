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
from rest_framework import generics
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


def is_valid_long_url(url):
    field = URLField()
    try:
        url = field.clean(url)
    except ValidationError:
        return False
    return True


VALID_SHORT_URL_REGEX = r'(?P<short_url>^[A-Za-z0-9]{1,32}$)'


def is_valid_short_url(url):
    if re.match(VALID_SHORT_URL_REGEX, url) is None:
        return False
    if url == 'api':
        return False
    return True


def generate_random_short_url():
    CHAR_SET = string.ascii_letters + string.digits
    SHORT_URL_LENGTH = 6
    RETRY_LIMIT = 5

    while retry := RETRY_LIMIT > 0:
        short_url = ''.join(random.choice(CHAR_SET)
                            for _ in range(SHORT_URL_LENGTH))
        if not UrlRecord.objects.filter(short_url=short_url).exists():
            return short_url
        retry -= 1

    logger.error(f'Unable to generate any available random short_url!')
    return ''


class UrlRecordListCreateView(generics.ListCreateAPIView):
    MAX_RECORDS = 10
    serializer_class = UrlRecordSerializer

    def get(self, request):
        logger.info(f'[{get_client_ip(request)}] API List: {request.data}')
        records = UrlRecord.objects.all().order_by(
            '-last_modified')[:type(self).MAX_RECORDS]
        serializer = UrlRecordSerializer(records, many=True)
        return Response(serializer.data)

    @staticmethod
    def convert_to_absolute_url(url):
        try:
            if urlsplit(url).netloc:
                return url
            else:
                return 'http://' + url
        except:
            return url

    def create(self, request, format=None):
        # TODO: Rate Limit
        logger.info(f'[{get_client_ip(request)}] API Create: {request.data}')
        long_url = request.data.get('long_url', '')
        long_url = self.convert_to_absolute_url(long_url)
        if not is_valid_long_url(long_url):
            return Response({'long_url': ['Invalid URL']}, status=400)

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
                return Response({'short_url': [f'Must be "{VALID_SHORT_URL_REGEX}"']}, status=400)
            if UrlRecord.objects.filter(short_url=short_url).exists():
                return Response({'short_url': ['Already exists!']}, status=409)

            serializer.save()
            logger.info(
                f'[{get_client_ip(request)}] Created mapping: "{short_url}" -> "{long_url}"')
            return Response(serializer.data, status=201)
        else:
            return Response(serializer.errors, status=400)


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
                        return Response({'long_url': ['Not exists!'], 'short_url': short_url}, status=404)
                else:
                    return Response({'short_url': [f'Must be "{VALID_SHORT_URL_REGEX}"']}, status=400)
        return Response({'short_url': [f'Must be "{VALID_SHORT_URL_REGEX}"']}, status=400)


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
    return render(request, 'redirect_failed.html')


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
