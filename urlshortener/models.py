from string import Template
from django import forms
from django.db import models
from django.utils import timezone


def one_minute_later():
    return timezone.now() + timezone.timedelta(minutes=1)


MAX_LONG_URL_LENGTH = 2048
MAX_SHORT_URL_LENGTH = 32


class UrlRecord(models.Model):
    '''Main model for the mapping of "short_url" -> "long_url" redirect record.'''

    long_url = models.URLField(max_length=MAX_LONG_URL_LENGTH)
    short_url = models.CharField(max_length=MAX_SHORT_URL_LENGTH)
    # create_time = models.DateTimeField(auto_now_add=True)
    # expire_time = models.DateTimeField(default=one_minute_later)
    last_activity_time = models.DateTimeField(auto_now=True)
    visit_count = models.IntegerField(default=0)

    def __str__(self):
        return Template('`$short_url`->`$long_url`($visit_count)').substitute(short_url=self.short_url, long_url=self.long_url, visit_count=self.visit_count)

    class Meta:
        db_table = 'urlrecords'


class UrlMappingForm(forms.ModelForm):
    '''Form for validating user input "short_url" and "long_url".'''

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
