import errno
import re
import socket
from django.core.servers.basehttp import ThreadedWSGIServer
from django.test import LiveServerTestCase, TestCase
from django.test.testcases import QuietWSGIRequestHandler, LiveServerThread
from django.urls import reverse
from rest_framework import status
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from .models import UrlRecord
from .serializers import UrlRecordSerializer
from .views import UrlRecordListCreateView, DEFAULT_SHORT_URL_LENGTH, VALID_SHORT_URL_REGEX


# To suppress the warnings about 'An existing connection was forcibly closed by the remote host'
# https://code.djangoproject.com/ticket/21227
class ConnectionResetErrorSwallowingQuietWSGIRequestHandler(QuietWSGIRequestHandler):
    def handle_one_request(self):
        try:
            super().handle_one_request()
        except socket.error as err:
            if err.errno != errno.WSAECONNRESET:
                raise


class ConnectionResetErrorSwallowingLiveServerThread(LiveServerThread):
    def _create_server(self):
        return ThreadedWSGIServer((self.host, self.port), ConnectionResetErrorSwallowingQuietWSGIRequestHandler, allow_reuse_address=False)


class FrontendTest(LiveServerTestCase):
    server_thread_class = ConnectionResetErrorSwallowingLiveServerThread

    fixtures = ['test_data.json']
    TIMEOUT = 10

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument('--headless')
        options.add_argument('--window-size=1920,1080')
        # https://stackoverflow.com/questions/61325672/browser-switcher-service-cc238-xxx-init-error-with-python-selenium-script-w
        options.add_experimental_option('excludeSwitches', ['enable-logging'])

        cls.driver = webdriver.Chrome(options=options)
        cls.driver.implicitly_wait(cls.TIMEOUT)
        WebDriverWait(cls.driver, cls.TIMEOUT).until(
            lambda driver: driver.find_element_by_tag_name('body'))

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        super().tearDownClass()

    def test_create_valid_record(self):
        long_url = 'https://www.w3.org/'
        driver = self.driver
        driver.get(self.live_server_url)
        driver.find_element_by_id('long-url').send_keys(long_url)
        driver.find_element_by_id('short-url').send_keys('w3')
        driver.find_element_by_id('submit-button').click()
        self.assertIn('Congratulation',
                      driver.find_element_by_class_name('card-title').text)

        # click the created link and check url
        driver.find_element_by_id('created-link').click()
        window_after = driver.window_handles[1]
        driver.switch_to.window(window_after)
        self.assertEqual(driver.current_url, long_url)

    def test_input_url_change_submit_button_state(self):

        def element_has_disabled_attribute(element):
            return not (element.get_attribute('disabled') is None)

        driver = self.driver
        driver.get(self.live_server_url)
        long_url_field = driver.find_element_by_id('long-url')
        button = driver.find_element_by_id('submit-button')
        WebDriverWait(driver, type(self).TIMEOUT).until(
            lambda _: element_has_disabled_attribute(button))
        self.assertIsNotNone(button.get_attribute('disabled'))

        # invalid long_url
        long_url_field.send_keys('http')
        WebDriverWait(driver, type(self).TIMEOUT).until(
            lambda _: element_has_disabled_attribute(button))
        self.assertIsNotNone(button.get_attribute('disabled'))
        # valid long_url
        long_url_field.send_keys('://w3.org')
        self.assertEqual(
            'http://w3.org', long_url_field.get_attribute('value'))
        WebDriverWait(driver, type(self).TIMEOUT).until(
            lambda _: not element_has_disabled_attribute(button))
        self.assertIsNone(button.get_attribute('disabled'))

        # collided short_url
        driver.find_element_by_id('short-url').send_keys('short')
        WebDriverWait(driver, type(self).TIMEOUT).until(
            lambda _: element_has_disabled_attribute(button))
        self.assertIsNotNone(button.get_attribute('disabled'))


class RestAPITestCase(TestCase):
    fixtures = ['test_data.json']

    def test_list_record(self):
        response = self.client.get(reverse('urlshortener:list_create_url'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        serializer = UrlRecordSerializer(response.data, many=True)
        self.assertEqual(response.data, serializer.data)

        self.assertLessEqual(len(serializer.data), 7)

        # create more records then check returned list length
        for i in range(UrlRecordListCreateView.MAX_LIST_SIZE + 5):
            response = self.client.post(reverse('urlshortener:list_create_url'), {
                                        'long_url': 'w3.org', 'short_url': str(i)})

        response = self.client.get(reverse('urlshortener:list_create_url'))
        serializer = UrlRecordSerializer(response.data, many=True)
        self.assertEqual(len(serializer.data),
                         UrlRecordListCreateView.MAX_LIST_SIZE)

    def test_retrieve_valid_record(self):
        response = self.client.get(
            reverse('urlshortener:retrieve_url'), {'short_url': 'short'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['long_url']), 1898)
        self.assertEqual(response.data['visit_count'], 2020)

        response = self.client.get(
            reverse('urlshortener:retrieve_url'), {'short_url': 'VeryVeryShortUrl'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['long_url']), 83)
        self.assertEqual(response.data['visit_count'], 313)

    def test_retrieve_invalid_record(self):
        # not exists
        response = self.client.get(
            reverse('urlshortener:retrieve_url'), {'short_url': '1mp0ssib1eR3c0rd'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        error = response.data['errors'][0]
        self.assertEqual(error['title'], 'short_url has no mapping')

        # should use short_url
        response = self.client.get(
            reverse('urlshortener:retrieve_url'), {'long_url': 'python.org'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # invalid pattern
        response = self.client.get(
            reverse('urlshortener:retrieve_url'), {'short_url': 'und3rsc0red_patt3rn/withS1ash'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_valid_record(self):
        LONG_URLS = ['https://w3.org/', 'https://w3.org',
                     'http://w3.org', 'w3.org', 'w3.org/']
        STORED_LONG_URLS = ['https://w3.org/', 'https://w3.org',
                            'http://w3.org', 'http://w3.org', 'http://w3.org/']

        for i, long_url in enumerate(LONG_URLS):
            short_url = f'temp{i}'
            data = {'long_url': long_url, 'short_url': short_url}
            response = self.client.post(
                reverse('urlshortener:list_create_url'), data)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

            response = self.client.get(reverse('urlshortener:retrieve_url'), {
                                       'short_url': short_url})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['long_url'], STORED_LONG_URLS[i])
            self.assertEqual(response.data['short_url'], short_url)
            self.assertEqual(response.data['visit_count'], 0)

        # json content type
        data = {'long_url': 'https://w3.org/', 'short_url': 'json'}
        response = self.client.post(
            reverse('urlshortener:list_create_url'), data, content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # POST with empty short_url, check generated short_url
        response = self.client.post(
            reverse('urlshortener:list_create_url'), {'long_url': 'w3.org'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        short_url = response.data['short_url']
        self.assertRegex(short_url, VALID_SHORT_URL_REGEX)
        self.assertEqual(len(short_url), DEFAULT_SHORT_URL_LENGTH)

    def test_create_invalid_record(self):
        # long_url invalid
        for long_url in ('wtf', 'htt://w3.org', 'http://www.' + ('0' * 3000) + '.com'):
            data = {'long_url': long_url, 'short_url': ''}
            response = self.client.post(
                reverse('urlshortener:list_create_url'), data)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            error = response.data['errors'][0]
            self.assertEqual(error['title'], 'Invalid long_url')

        # short_url pattern not match
        for short_url in ('"; drop urlrecords --', '#', '/*', '/* --', '--', "'''", '"""'):
            data = {'long_url': 'w3.org', 'short_url': short_url}
            response = self.client.post(
                reverse('urlshortener:list_create_url'), data)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            error = response.data['errors'][0]
            self.assertEqual(error['title'], 'Invalid short_url')

        # short_url pattern too long, trying to bypass form validation
        for length in (33, 34, 3000):
            data = {'long_url': 'w3.org', 'short_url': '0' * length}
            response = self.client.post(
                reverse('urlshortener:list_create_url'), data)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            error = response.data['errors'][0]
            self.assertEqual(error['title'], 'Invalid short_url')

        # already exists
        data = {'long_url': 'w3.org', 'short_url': 'short'}
        response = self.client.post(
            reverse('urlshortener:list_create_url'), data)
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


class RedirectFunctionTestCase(TestCase):
    fixtures = ['test_data.json']

    def test_successful_redirect(self):
        for short_url in ('www', 'f', 'short'):
            long_url = UrlRecord.objects.all().get(short_url=short_url).long_url
            response = self.client.get('/' + short_url)
            self.assertEqual(response.status_code, status.HTTP_302_FOUND)
            self.assertEqual(response['Location'], long_url)

    def test_failed_redirect(self):
        for short_url in ('wtf', 'NotExists', 'wtf_not-exists', 'w t f i s t h i s'):
            if re.match(VALID_SHORT_URL_REGEX, short_url):
                error_text = 'Redirect to the shortener page'
            else:
                error_text = 'The requested resource was not found on this server.'

            response = self.client.get('/' + short_url)
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
            self.assertIn(error_text, response.content.decode('utf-8'))
