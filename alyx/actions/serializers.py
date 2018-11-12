from rest_framework import serializers
from django.contrib.admin.models import LogEntry, ADDITION
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from .models import (ProcedureType, Session, WaterAdministration, Weighing, WaterType)
from subjects.models import Subject
from data.models import Dataset, DatasetType, DataFormat
from misc.models import LabLocation, Lab


def _log_entry(instance, user):
    if instance.pk:
        LogEntry.objects.log_action(
            user_id=user.pk,
            content_type_id=ContentType.objects.get_for_model(instance).pk,
            object_id=instance.pk,
            object_repr=str(instance),
            action_flag=ADDITION,
            change_message=[{'added': {}}],
        )
    return instance


class BaseActionSerializer(serializers.HyperlinkedModelSerializer):
    subject = serializers.SlugRelatedField(
        read_only=False,
        slug_field='nickname',
        queryset=Subject.objects.all()
    )

    users = serializers.SlugRelatedField(
        read_only=False,
        many=True,
        slug_field='username',
        queryset=get_user_model().objects.all(),
        required=False,
    )

    location = serializers.SlugRelatedField(
        read_only=False,
        slug_field='name',
        queryset=LabLocation.objects.all(),
        allow_null=True,
        required=False,

    )

    procedures = serializers.SlugRelatedField(
        read_only=False,
        many=True,
        slug_field='name',
        queryset=ProcedureType.objects.all(),
        allow_null=True,
        required=False,
    )

    lab = serializers.SlugRelatedField(
        read_only=False,
        slug_field='name',
        queryset=Lab.objects.all(),
        many=False,
        required=False,)


class SessionDatasetsSerializer(serializers.ModelSerializer):

    dataset_type = serializers.SlugRelatedField(
        read_only=False, slug_field='name',
        queryset=DatasetType.objects.all(),
    )

    data_format = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='name',
        queryset=DataFormat.objects.all(),
    )

    class Meta:
        model = Dataset
        fields = ('id', 'name', 'dataset_type', 'data_url', 'data_format', 'url')


class SessionListSerializer(BaseActionSerializer):

    data_dataset_session_related = SessionDatasetsSerializer(read_only=True, many=True)

    @staticmethod
    def setup_eager_loading(queryset):
        """ Perform necessary eager loading of data to avoid horrible performance."""
        queryset = queryset.select_related('subject', 'location', 'parent_session', 'lab')
        queryset = queryset.prefetch_related(
            'users', 'procedures',
            'data_dataset_session_related',
            'data_dataset_session_related__dataset_type',
            'data_dataset_session_related__data_format',
            'data_dataset_session_related__file_records',
            'data_dataset_session_related__file_records__data_repository',
        )
        return queryset

    class Meta:
        model = Session
        fields = ('subject', 'users', 'location', 'procedures', 'lab',
                  'type', 'number', 'parent_session', 'data_dataset_session_related',
                  'narrative', 'start_time', 'end_time', 'url', 'n_correct_trials', 'n_trials')


class SessionDetailSerializer(BaseActionSerializer):

    data_dataset_session_related = SessionDatasetsSerializer(read_only=True, many=True)

    @staticmethod
    def setup_eager_loading(queryset):
        queryset = queryset.prefetch_related(
            'data_dataset_session_related',
            'data_dataset_session_related__dataset_type',
            'data_dataset_session_related__data_format',
            'data_dataset_session_related__file_records',
            'data_dataset_session_related__file_records__data_repository',
        )
        return queryset

    class Meta:
        model = Session
        fields = ('subject', 'users', 'location', 'procedures', 'lab',
                  'narrative', 'start_time', 'end_time', 'url', 'json',
                  'data_dataset_session_related', 'parent_session', 'n_correct_trials', 'n_trials')


class WeighingDetailSerializer(serializers.HyperlinkedModelSerializer):

    subject = serializers.SlugRelatedField(
        read_only=False,
        slug_field='nickname',
        queryset=Subject.objects.all()
    )

    user = serializers.SlugRelatedField(
        read_only=False,
        slug_field='username',
        queryset=get_user_model().objects.all(),
        required=False,
    )

    def create(self, validated_data):
        user = self.context['request'].user
        instance = Weighing.objects.create(**validated_data)
        _log_entry(instance, user)
        return instance

    @staticmethod
    def setup_eager_loading(queryset):
        return queryset.select_related('subject', 'user')

    class Meta:
        model = Weighing
        fields = ('subject', 'date_time', 'weight',
                  'user', 'url')


class WaterTypeDetailSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = WaterType
        fields = ('__all__')
        extra_kwargs = {'url': {'view_name': 'watertype-detail', 'lookup_field': 'name'}}


class WaterAdministrationDetailSerializer(serializers.HyperlinkedModelSerializer):

    subject = serializers.SlugRelatedField(
        read_only=False,
        slug_field='nickname',
        queryset=Subject.objects.all()
    )

    user = serializers.SlugRelatedField(
        read_only=False,
        slug_field='username',
        queryset=get_user_model().objects.all(),
        required=False,
    )

    water_type = serializers.SlugRelatedField(
        read_only=False,
        slug_field='name',
        queryset=WaterType.objects.all(),
        required=False,
    )

    @staticmethod
    def setup_eager_loading(queryset):
        return queryset.select_related('subject', 'user')

    def create(self, validated_data):
        user = self.context['request'].user
        instance = WaterAdministration.objects.create(**validated_data)
        _log_entry(instance, user)
        return instance

    class Meta:
        model = WaterAdministration
        fields = ('subject', 'date_time', 'water_administered', 'water_type', 'user', 'url')
        extra_kwargs = {'url': {'view_name': 'water-administration-detail'}}
