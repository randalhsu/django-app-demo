from django import forms
from django.db import models
from django.utils import timezone


def one_minute_later():
    return timezone.now() + timezone.timedelta(minutes=1)


MAX_LONG_URL_LENGTH = 2048
MAX_SHORT_URL_LENGTH = 32


class UrlRecord(models.Model):
    long_url = models.URLField(max_length=MAX_LONG_URL_LENGTH)
    short_url = models.CharField(max_length=MAX_SHORT_URL_LENGTH)
    last_modified = models.DateTimeField(auto_now=True)
    expire_time = models.DateTimeField(default=one_minute_later)
    visit_count = models.IntegerField(default=0)
    # TODO: add owner?

    class Meta:
        db_table = 'urlrecords'


class UrlMappingForm(forms.ModelForm):
    long_url = forms.URLField(
        label='Your URL:',
        max_length=MAX_LONG_URL_LENGTH,
        widget=forms.URLInput(
            attrs={'placeholder': 'https://www.djangoproject.com'}
        ),
    )
    short_url = forms.CharField(
        label='Shorten to:',
        max_length=MAX_SHORT_URL_LENGTH,
        required=False,
        widget=forms.TextInput(
            attrs={'placeholder': 'Empty or [A-Za-z0-9]+'}
        ),
    )

    class Meta:
        model = UrlRecord
        fields = ('long_url', 'short_url')
