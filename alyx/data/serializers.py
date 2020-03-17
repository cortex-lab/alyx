from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (DataRepositoryType, DataRepository, DataFormat, DatasetType,
                     Dataset, Download, FileRecord,)
from .transfers import _get_session
from actions.models import Session
from subjects.models import Subject
from misc.models import LabMember


class DataRepositoryTypeSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = DataRepositoryType
        fields = ('__all__')
        extra_kwargs = {'url': {'view_name': 'datarepositorytype-detail', 'lookup_field': 'name'}}


class DataRepositorySerializer(serializers.HyperlinkedModelSerializer):

    repository_type = serializers.SlugRelatedField(
        read_only=False,
        slug_field='name',
        queryset=DataRepositoryType.objects.all(),
        allow_null=True,
        required=False)

    class Meta:
        model = DataRepository
        fields = ('name', 'timezone', 'globus_path', 'hostname', 'data_url', 'repository_type',
                  'globus_endpoint_id', 'globus_is_personal')
        extra_kwargs = {'url': {'view_name': 'datarepository-detail', 'lookup_field': 'name'}}


class DataFormatSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataFormat
        fields = ('__all__')
        extra_kwargs = {'url': {'view_name': 'dataformat-detail', 'lookup_field': 'name'}}


class DatasetTypeSerializer(serializers.HyperlinkedModelSerializer):
    created_by = serializers.SlugRelatedField(
        read_only=False,
        slug_field='username',
        queryset=get_user_model().objects.all(),
        allow_null=True,
        required=False,
        default=serializers.CurrentUserDefault(),
    )

    class Meta:
        model = DatasetType
        fields = ('id', 'name', 'created_by', 'description', 'filename_pattern')
        extra_kwargs = {'url': {'view_name': 'datasettype-detail', 'lookup_field': 'name'}}


class FileRecordSerializer(serializers.HyperlinkedModelSerializer):
    dataset = serializers.HyperlinkedRelatedField(
        read_only=False, view_name="dataset-detail",
        queryset=Dataset.objects.all())

    data_repository = serializers.SlugRelatedField(
        read_only=False, slug_field='name',
        queryset=DataRepository.objects.all())

    @staticmethod
    def setup_eager_loading(queryset):
        """ Perform necessary eager loading of data to avoid horrible performance."""
        queryset = queryset.select_related('dataset', 'data_repository')
        return queryset

    class Meta:
        model = FileRecord
        fields = ('__all__')


class DatasetFileRecordsSerializer(serializers.ModelSerializer):

    data_repository = serializers.SlugRelatedField(
        read_only=False, slug_field='name',
        queryset=DataRepository.objects.all())

    data_repository_path = serializers.SerializerMethodField()

    def get_data_repository_path(self, obj):
        return obj.data_repository.globus_path

    class Meta:
        model = FileRecord
        fields = ('id', 'data_repository', 'data_repository_path', 'relative_path', 'data_url',
                  'exists')


class DatasetSerializer(serializers.HyperlinkedModelSerializer):
    created_by = serializers.SlugRelatedField(
        read_only=False, slug_field='username',
        queryset=get_user_model().objects.all(),
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

    session = serializers.HyperlinkedRelatedField(
        read_only=False, required=False, view_name="session-detail",
        queryset=Session.objects.all(),
    )

    hash = serializers.CharField(required=False, allow_null=True)
    version = serializers.CharField(required=False, allow_null=True)
    file_size = serializers.IntegerField(required=False, allow_null=True)
    collection = serializers.CharField(required=False, allow_null=True)
    file_records = DatasetFileRecordsSerializer(read_only=True, many=True)

    experiment_number = serializers.SerializerMethodField()
    # If session is not provided, use subject, start_time, number
    subject = serializers.SlugRelatedField(
        write_only=True, required=False, slug_field='nickname',
        queryset=Subject.objects.all(),
    )

    date = serializers.DateField(required=False)

    number = serializers.IntegerField(required=False)

    @staticmethod
    def setup_eager_loading(queryset):
        """ Perform necessary eager loading of data to avoid horrible performance."""
        queryset = queryset.select_related(
            'created_by', 'dataset_type', 'data_format', 'session',
            'session__subject')
        queryset = queryset.prefetch_related(
            'file_records', 'file_records__data_repository')
        return queryset

    def get_experiment_number(self, obj):
        return obj.session.number if obj and obj.session else None

    def create(self, validated_data):
        if validated_data.get('session', None):
            return super(DatasetSerializer, self).create(validated_data)

        # Find or create an appropriate session for the dataset.
        subject = validated_data.pop('subject', None)
        date = validated_data.pop('date', None)
        if not subject or not date:
            return super(DatasetSerializer, self).create(validated_data)

        # Only get or create the appropriate session if at least the subject and
        # date are provided.
        number = validated_data.pop('number', None)
        user = validated_data.pop('created_by', None)

        session = _get_session(subject=subject, date=date, number=number, user=user)

        # Create the dataset, attached to the subsession.
        validated_data['session'] = session
        return super(DatasetSerializer, self).create(validated_data)

    class Meta:
        model = Dataset
        fields = ('url', 'name', 'created_by', 'created_datetime',
                  'dataset_type', 'data_format', 'collection',
                  'session', 'file_size', 'hash', 'version',
                  'experiment_number', 'file_records',
                  'subject', 'date', 'number')
        extra_kwargs = {
            'subject': {'write_only': True},
            'date': {'write_only': True},
            'number': {'write_only': True},
        }


class DownloadSerializer(serializers.HyperlinkedModelSerializer):

    # dataset = DatasetSerializer(many=False, read_only=True)
    dataset = serializers.PrimaryKeyRelatedField(many=False, read_only=True)

    user = serializers.SlugRelatedField(
        read_only=False, slug_field='username',
        queryset=LabMember.objects.all())

    class Meta:
        model = Download
        fields = ('id', 'user', 'dataset', 'count', 'json')
