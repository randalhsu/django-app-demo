# Django URL Shortener

## [Live Demo](https://veryshort.herokuapp.com/) (For demo purpose only!)

A Django app which implements URL shortening backend mechanism, and a Vue.js frontend interacts with it.

It handles <code>http(s)://{app_url}/{short_url} ➜ {long_url}</code> mapping for redirection, and increase <code>visit_count</code> upon accessed.


## RESTful APIs

It provides the following APIs:

| Endpoint         | Method   | Action   | Example request  | Example result |
| ---------------- |:--------:|:--------:|----------------- | -------------- |
| ``api/v1/urls``  | ``GET``  | List     | (empty)           | Returns shortened mappings as list. |
| ``api/v1/urls``  | ``POST`` | Create   | ``{"long_url": "https://www.google.com/search?q=a+very+long+query", "short_url": "g"}`` | Creates a relative URL <code>g</code> which redirects to the long link upon accessed. |
| ``api/v1/urls/`` | ``GET``  | Retrieve | ``{"short_url": "g"}`` | ``{"long_url": "https://www.google.com/search?q=a+very+long+query", "short_url": "g", "visit_count": 1}`` |


If <code>short_url</code> is ommitted when creating mapping, will generate a random one such as ``y5xVCn`` and assign to it.

See [Live Demo](https://veryshort.herokuapp.com/) for more concrete examples.


## Error Handling

It also features massive error handling for various cases. For example:

| Endpoint         | Method   | Action   | Example request  | Example response |
| ---------------- |:--------:|:--------:|----------------- | ---------------- |
| ``api/v1/urls``  | ``POST`` | Create   | ``{"long_url": "yeah", "short_url": "y"}`` | ``{"errors": [{"code": "1001", "title": "Invalid long_url", "detail": "long_url:`http://yeah` is not a valid URL", "status": "400"}]}`` |
| ``api/v1/urls``  | ``POST`` | Create   | ``{"long_url": "//w3.org", "short_url": "w"}`` | ``{"errors": [{"code": "1005", "title": "Malformed data", "detail": "Are you malicious?", "status": "400"}]}`` |
| ``api/v1/urls``  | ``POST`` | Create   | ``{"long_url": "http://w3.org", "short_url": "; drop urlrecords --"}`` | ``{"errors": [{"code": "1002", "title": "Invalid short_url", "detail": "short_url:`; drop urlrecords --` cannot match pattern: ^[A-Za-z0-9]{1,32}$", "status": "400"}]}`` |


See [Live Demo](https://veryshort.herokuapp.com/) in action.


## Deploy to Heroku

This app can be easily deployed to Heroku by the following commands:

<pre>
(git clone this project and cd into it)
heroku login
heroku create {my_app_name}
heroku git:remote -a {my_app_name}
heroku config:set SECRET_KEY="a Rand0m pR3c10us-secR3t f0r my_APP"  # Set a secret for Django
git push heroku main
heroku run python manage.py migrate
heroku run python manage.py loaddata urlshortener/fixtures/test_data.json  # If you want to populate some sample mapping data
heroku ps:scale web=1
heroku open
heroku logs --tail
</pre>

By default, <code>settings.py</code> is configured as <code>DEBUG = True</code>.
