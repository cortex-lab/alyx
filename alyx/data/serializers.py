from django.contrib.auth.models import User
from rest_framework import serializers
from .models import (DataRepositoryType, DataRepository, DataFormat, DatasetType,
                     Dataset, FileRecord, Timescale)
from actions.models import Session
from subjects.models import Subject
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


class DataFormatSerializer(serializers.ModelSerializer):
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
        fields = ('__all__')


class DatasetFileRecordsSerializer(serializers.ModelSerializer):
    data_repository_path = serializers.SerializerMethodField()

    def get_data_repository_path(self, obj):
        return obj.data_repository.path

    class Meta:
        model = FileRecord
        fields = ('id', 'data_repository_path', 'relative_path')


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

    # If session is not provided, use subject, start_time, number
    subject = serializers.SlugRelatedField(
        write_only=True, required=False, slug_field='nickname',
        queryset=Subject.objects.all(),
    )

    date = serializers.DateField(required=False)

    number = serializers.IntegerField(required=False)

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

        # https://github.com/cortex-lab/alyx/issues/408
        # If a base session for that subject and date already exists, use it;
        base = Session.objects.filter(
            subject=subject, start_time__date=date, parent_session__isnull=True).first()
        # otherwise create a base session for that subject and date.
        if not base:
            base = Session.objects.create(
                subject=subject, start_time=date, type='Base', narrative="auto-generated session")
            if user:
                base.users.add(user.pk)
                base.save()
        # If a subsession for that subject, date, and expNum already exists, use it;
        session = Session.objects.filter(
            subject=subject, start_time__date=date, number=number).first()
        # otherwise create the subsession.
        if not session:
            session = Session.objects.create(
                subject=subject, start_time=date, number=number,
                type='Experiment', narrative="auto-generated session")
            if user:
                session.users.add(user.pk)
                session.save()
        # Attach the subsession to the base session if not already attached.
        if not session.parent_session:
            session.parent_session = base
            session.save()
        # Create the dataset, attached to the subsession.
        validated_data['session'] = session
        return super(DatasetSerializer, self).create(validated_data)

    class Meta:
        model = Dataset
        fields = ('url', 'name', 'created_by', 'created_datetime',
                  'dataset_type', 'data_format', 'parent_dataset',
                  'timescale', 'session', 'md5', 'experiment_number', 'file_records',
                  'subject', 'date', 'number')
        extra_kwargs = {
            'subject': {'write_only': True},
            'date': {'write_only': True},
            'number': {'write_only': True},
        }


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
