# Django URL Shortener

## [Live Demo](https://veryshort.herokuapp.com/)

A Django app implementing URL shortening.

It handles <code>http(s)://{app_url}/{short_url} ➜ {long_url}</code> mapping for redirection, and increase <code>visit_count</code> upon accessed.


## RESTful APIs

It provides the following APIs:

| Endpoint      | Method  | Action   | Example params  | Example result |
| ------------- |:-------:|:--------:|----------------- | ------------- |
| api/v1/urls   | GET     | List     | (None)         | Returns shortened mappings |
| api/v1/urls   | POST    | Create   | {'long_url': 'https://www.google.com/search?q=a+very+long+query', 'short_url': 'g'} | Creates a URL link <code>{app_url}/g</code> which redirects to the long link upon accessed |
| api/v1/urls/  | GET     | Retrieve | {'short_url': 'g'} | {'long_url': 'https://www.google.com/search?q=a+very+long+query', 'short_url': 'g'} |

If <code>short_url</code> is ommitted when creating mapping, will generate a random one and assign to it.

See [Live Demo](https://veryshort.herokuapp.com/) for more concrete examples.


## Deploy this app to Heroku

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
