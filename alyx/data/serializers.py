from rest_framework import serializers
from .models import *
from actions.models import Experiment

class DatasetSerializer(serializers.HyperlinkedModelSerializer):

    file_records = serializers.SlugRelatedField(many=True,
        read_only=False,
        queryset = FileRecord.objects.all(),
        slug_field='filename',
        allow_null=True)

    experiment = serializers.HyperlinkedRelatedField(
        read_only=False, view_name="experiment-detail",
        queryset=Experiment.objects.all())

    def create(self, validated_data):
        return Dataset.objects.create(**validated_data)

    class Meta:
        model = Dataset
        fields = ('__all__')

class FileRecordSerializer(serializers.HyperlinkedModelSerializer):

    dataset = serializers.HyperlinkedRelatedField(
        read_only=False, view_name="dataset-detail",
        queryset=Dataset.objects.all())

    def create(self, validated_data):
        return FileRecord.objects.create(**validated_data)

    class Meta:
        model = FileRecord
        fields = ('__all__')
