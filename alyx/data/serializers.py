import os.path as op

from rest_framework import serializers
from .models import Dataset, FileRecord, DataRepository, DataRepositoryType
from actions.models import Session
from electrophysiology.models import ExtracellularRecording


class DatasetSerializer(serializers.HyperlinkedModelSerializer):
    file_records = serializers.SlugRelatedField(many=True,
                                                read_only=False,
                                                queryset=FileRecord.objects.all(),
                                                slug_field='filename',
                                                allow_null=True,
                                                required=False)

    session = serializers.HyperlinkedRelatedField(
        read_only=False, view_name="session-detail",
        queryset=Session.objects.all())

    def create(self, validated_data):
        return Dataset.objects.create(**validated_data)

    class Meta:
        model = Dataset
        fields = ('__all__')


class DataRepositoryDetailSerializer(serializers.HyperlinkedModelSerializer):

    repository_type = serializers.SlugRelatedField(
        read_only=False,
        slug_field='name',
        queryset=DataRepositoryType.objects.all(),
        allow_null=True,
        required=False)

    class Meta:
        model = DataRepository
        extra_kwargs = {'url': {'view_name': 'datarepository-detail', 'lookup_field': 'name'}}
        extra_kwargs = {
            'url': {'lookup_field': 'name'},
        }
        fields = ('name', 'path', 'repository_type')


class DatasetFileRecordDetailSerializer(serializers.HyperlinkedModelSerializer):
    dataset = serializers.HyperlinkedRelatedField(
        read_only=False, view_name="dataset-detail",
        queryset=Dataset.objects.all())

    def create(self, validated_data):
        dr = validated_data['data_repository']
        date = validated_data['created_date']
        relpath = validated_data['relative_path']

        name = op.basename(relpath)
        # TODO: dataset type
        dt = None
        user = self.context['request'].user

        dataset = Dataset.objects.create(name=name,
                                         dataset_type=dt,
                                         created_by=user,
                                         created_date=date,
                                         )

        file_record = FileRecord.objects.create(dataset=dataset,
                                                relative_path=relpath,
                                                data_repository=dr,
                                                )

        return (dataset, file_record)

    class Meta:
        model = FileRecord
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


class ExpMetadataSummarySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = ExtracellularRecording
        fields = ('classname', 'json', 'start_time', 'end_time', 'session', 'url')
        extra_kwargs = {'url': {'view_name': 'exp-metadata-detail', 'lookup_field': 'pk'}}


class ExpMetadataDetailSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = ExtracellularRecording
        fields = ('__all__')
        extra_kwargs = {'url': {'view_name': 'exp-metadata-detail', 'lookup_field': 'pk'}}
