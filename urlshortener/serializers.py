from rest_framework import serializers
from .models import UrlRecord


class UrlRecordSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = UrlRecord
        fields = ('long_url', 'short_url', 'visit_count')
