from django.db import models
from django.utils import timezone


def one_minute_later():
    return timezone.now() + timezone.timedelta(minutes=1)


class UrlRecord(models.Model):
    long_url = models.CharField(max_length=2048)
    short_url = models.CharField(max_length=32)
    last_modified = models.DateTimeField(auto_now=True)
    expire_time = models.DateTimeField(default=one_minute_later)
    visit_count = models.IntegerField(default=0)
    # TODO: add owner?

    class Meta:
        db_table = 'urlrecords'
