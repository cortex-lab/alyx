from django.contrib.auth.models import User
from rest_framework import serializers
from .models import (DataRepositoryType, DataRepository, DataFormat, DatasetType,
                     Dataset, FileRecord, Timescale)
from actions.models import Session
from electrophysiology.models import ExtracellularRecording


class DataRepositoryTypeSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = DataRepositoryType
        fields = ('__all__')
        extra_kwargs = {'url': {'view_name': 'datarepositorytype-detail', 'lookup_field': 'name'}}


class DataRepositoryDetailSerializer(serializers.HyperlinkedModelSerializer):

    repository_type = serializers.SlugRelatedField(
        read_only=False,
        slug_field='name',
        queryset=DataRepositoryType.objects.all(),
        allow_null=True,
        required=False)

    class Meta:
        model = DataRepository
        fields = ('name', 'path', 'repository_type', 'globus_endpoint_id', 'globus_is_personal')
        extra_kwargs = {'url': {'view_name': 'datarepository-detail', 'lookup_field': 'name'}}


class DataFormatSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = DataFormat
        fields = ('__all__')
        extra_kwargs = {'url': {'view_name': 'dataformat-detail', 'lookup_field': 'name'}}


class DatasetTypeSerializer(serializers.HyperlinkedModelSerializer):
    created_by = serializers.SlugRelatedField(
        read_only=False,
        slug_field='username',
        queryset=User.objects.all(),
        allow_null=True,
        required=False,
        default=serializers.CurrentUserDefault(),
    )

    class Meta:
        model = DatasetType
        fields = ('__all__')
        extra_kwargs = {'url': {'view_name': 'datasettype-detail', 'lookup_field': 'name'}}


class FileRecordSerializer(serializers.HyperlinkedModelSerializer):
    dataset = serializers.HyperlinkedRelatedField(
        read_only=False, view_name="dataset-detail",
        queryset=Dataset.objects.all())

    data_repository = serializers.SlugRelatedField(
        read_only=False, slug_field='name',
        queryset=DataRepository.objects.all())

    class Meta:
        model = FileRecord
        fields = ('id', 'url', 'dataset', 'data_repository', 'relative_path', 'exists')


class DatasetFileRecordsSerializer(serializers.ModelSerializer):
    data_repository_path = serializers.SerializerMethodField()

    def get_data_repository_path(self, obj):
        return obj.data_repository.path

    class Meta:
        model = FileRecord
        fields = ('id', 'data_repository_path', 'relative_path', 'exists')


class DatasetSerializer(serializers.HyperlinkedModelSerializer):
    created_by = serializers.SlugRelatedField(
        read_only=False, slug_field='username',
        queryset=User.objects.all(),
        default=serializers.CurrentUserDefault(),
    )

    dataset_type = serializers.SlugRelatedField(
        read_only=False, slug_field='name',
        queryset=DatasetType.objects.all(),
    )

    data_format = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='name',
        queryset=DataFormat.objects.all(),
    )

    parent_dataset = serializers.HyperlinkedRelatedField(
        read_only=False, required=False, view_name="dataset-detail",
        queryset=Dataset.objects.all(),
    )

    timescale = serializers.HyperlinkedRelatedField(
        read_only=False, required=False, view_name="timescale-detail",
        queryset=Timescale.objects.all(),
    )

    session = serializers.HyperlinkedRelatedField(
        read_only=False, required=False, view_name="session-detail",
        queryset=Session.objects.all(),
    )

    md5 = serializers.UUIDField(
        format='hex_verbose', allow_null=True, required=False,
    )

    experiment_number = serializers.SerializerMethodField()

    file_records = DatasetFileRecordsSerializer(read_only=True, many=True)

    def get_experiment_number(self, obj):
        return obj.session.number if obj and obj.session else None

    class Meta:
        model = Dataset
        fields = ('url', 'name', 'created_by', 'created_datetime',
                  'dataset_type', 'data_format', 'parent_dataset',
                  'timescale', 'session', 'md5', 'experiment_number', 'file_records')


class TimescaleSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Timescale
        fields = ('__all__')
        extra_kwargs = {'url': {'view_name': 'timescale-detail', 'lookup_field': 'name'}}


class ExpMetadataSummarySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = ExtracellularRecording
        fields = ('classname', 'json', 'nominal_start_time', 'nominal_end_time', 'session', 'url')
        extra_kwargs = {'url': {'view_name': 'exp-metadata-detail', 'lookup_field': 'pk'}}


class ExpMetadataDetailSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = ExtracellularRecording
        fields = ('__all__')
        extra_kwargs = {'url': {'view_name': 'exp-metadata-detail', 'lookup_field': 'pk'}}
