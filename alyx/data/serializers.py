from rest_framework import serializers
from .models import *

class DatasetSerializer(serializers.ModelSerializer):

    logical_files = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = Dataset
        fields = ('__all__')
