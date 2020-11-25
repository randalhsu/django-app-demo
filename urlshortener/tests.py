from django.test import TestCase, Client
from django.urls import reverse
from rest_framework import status
from rest_framework.response import Response
from .models import UrlRecord
from .serializers import UrlRecordSerializer
from .views import UrlRecordListCreateView, DEFAULT_SHORT_URL_LENGTH, VALID_SHORT_URL_REGEX


class RestAPITestCase(TestCase):
    fixtures = ['test_data.json']

    def setUp(self):
        self.client = Client()

    def test_list_record(self):
        response = self.client.get(reverse('list_create_url'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        serializer = UrlRecordSerializer(response.data, many=True)
        self.assertEqual(response.data, serializer.data)

        self.assertLessEqual(len(serializer.data), 7)

        # create more records then check returned list length
        for i in range(5):
            response = self.client.post(reverse('list_create_url'), {
                                        'long_url': 'w3.org', 'short_url': str(i)})

        response = self.client.get(reverse('list_create_url'))
        serializer = UrlRecordSerializer(response.data, many=True)
        self.assertEqual(len(serializer.data),
                         UrlRecordListCreateView.MAX_RECORDS)

    def test_retrieve_valid_record(self):
        response = self.client.get(
            reverse('retrieve_url'), {'short_url': 'short'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['long_url']), 1898)
        self.assertEqual(response.data['visit_count'], 2020)

        response = self.client.get(
            reverse('retrieve_url'), {'short_url': 'VeryVeryShortUrl'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['long_url']), 83)
        self.assertEqual(response.data['visit_count'], 313)

    def test_retrieve_invalid_record(self):
        # not exists
        response = self.client.get(
            reverse('retrieve_url'), {'short_url': '1mp0ssib1eR3c0rd'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        error = response.data['errors'][0]
        self.assertEqual(error['title'], 'short_url has no mapping')

        # should use short_url
        response = self.client.get(
            reverse('retrieve_url'), {'long_url': 'python.org'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # invalid pattern
        response = self.client.get(
            reverse('retrieve_url'), {'short_url': 'und3rsc0red_patt3rn/withS1ash'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_valid_record(self):
        LONG_URLS = ['https://w3.org/', 'https://w3.org',
                     'http://w3.org', 'w3.org', 'w3.org/']
        STORED_LONG_URLS = ['https://w3.org/', 'https://w3.org',
                            'http://w3.org', 'http://w3.org', 'http://w3.org/']

        for i, long_url in enumerate(LONG_URLS):
            short_url = f'temp{i}'
            data = {'long_url': long_url, 'short_url': short_url}
            response = self.client.post(reverse('list_create_url'), data)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

            response = self.client.get(reverse('retrieve_url'), {
                                       'short_url': short_url})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['long_url'], STORED_LONG_URLS[i])
            self.assertEqual(response.data['short_url'], short_url)
            self.assertEqual(response.data['visit_count'], 0)

        # json content type
        data = {'long_url': 'https://w3.org/', 'short_url': 'json'}
        response = self.client.post(
            reverse('list_create_url'), data, content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # POST with empty short_url, check generated short_url
        response = self.client.post(
            reverse('list_create_url'), {'long_url': 'w3.org'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        short_url = response.data['short_url']
        self.assertRegex(short_url, VALID_SHORT_URL_REGEX)
        self.assertEqual(len(short_url), DEFAULT_SHORT_URL_LENGTH)

    def test_create_invalid_record(self):
        # long_url invalid
        for long_url in ('wtf', 'htt://w3.org', 'http://www.' + ('0' * 3000) + '.com'):
            data = {'long_url': long_url, 'short_url': ''}
            response = self.client.post(reverse('list_create_url'), data)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            error = response.data['errors'][0]
            self.assertEqual(error['title'], 'Invalid long_url')

        # short_url pattern not match
        for short_url in ('; drop urlrecords --', '#', '/*', '/* --', '--', "'''", '"""'):
            data = {'long_url': 'w3.org', 'short_url': short_url}
            response = self.client.post(reverse('list_create_url'), data)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            error = response.data['errors'][0]
            self.assertEqual(error['title'], 'Invalid short_url')

        # short_url pattern too long, trying to bypass form validation
        for length in (33, 34, 3000):
            data = {'long_url': 'w3.org', 'short_url': '0' * length}
            response = self.client.post(reverse('list_create_url'), data)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            error = response.data['errors'][0]
            self.assertEqual(error['title'], 'Invalid short_url')

        # already exists
        data = {'long_url': 'w3.org', 'short_url': 'short'}
        response = self.client.post(reverse('list_create_url'), data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        error = response.data['errors'][0]
        self.assertEqual(error['title'], 'short_url already exists')


class UrlRecordSerializerTestCase(TestCase):
    fixtures = ['test_data.json']

    def test_serializer(self):
        record = UrlRecord.objects.get(pk=1)
        serializer = UrlRecordSerializer(record)
        data = {
            'long_url': 'https://www.google.com',
            'short_url': 'g',
            'visit_count': 19,
        }
        self.assertEqual(serializer.data, data)
