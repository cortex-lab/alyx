from rest_framework import serializers
from django.contrib.admin.models import LogEntry, ADDITION
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from .models import (ProcedureType, Session, WaterAdministration, Weighing)
from subjects.models import Subject
from data.serializers import ExpMetadataSummarySerializer
from equipment.models import LabLocation


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
        queryset=User.objects.all(),
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


class SessionListSerializer(BaseActionSerializer):

    class Meta:
        model = Session
        fields = ('subject', 'users', 'location', 'procedures',
                  'narrative', 'start_time', 'end_time', 'url')


class SessionDetailSerializer(BaseActionSerializer):

    exp_metadata_related = ExpMetadataSummarySerializer(many=True, read_only=True)

    class Meta:
        model = Session
        fields = ('subject', 'users', 'location', 'procedures',
                  'narrative', 'start_time', 'end_time', 'url', 'json', 'exp_metadata_related')


class WeighingListSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = Weighing
        fields = ('date_time', 'weight', 'url')


class WeighingDetailSerializer(serializers.HyperlinkedModelSerializer):

    subject = serializers.SlugRelatedField(
        read_only=False,
        slug_field='nickname',
        queryset=Subject.objects.all()
    )

    user = serializers.SlugRelatedField(
        read_only=False,
        slug_field='username',
        queryset=User.objects.all(),
        required=False,
    )

    def create(self, validated_data):
        user = self.context['request'].user
        instance = Weighing.objects.create(**validated_data)
        _log_entry(instance, user)
        return instance

    class Meta:
        model = Weighing
        fields = ('subject', 'date_time', 'weight',
                  'user', 'weighing_scale', 'url')


class WaterAdministrationListSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = WaterAdministration
        fields = ('date_time', 'water_administered', 'hydrogel', 'url')
        extra_kwargs = {'url': {'view_name': 'water-administration-detail'}}


class WaterAdministrationDetailSerializer(serializers.HyperlinkedModelSerializer):

    subject = serializers.SlugRelatedField(
        read_only=False,
        slug_field='nickname',
        queryset=Subject.objects.all()
    )

    user = serializers.SlugRelatedField(
        read_only=False,
        slug_field='username',
        queryset=User.objects.all(),
        required=False,
    )

    def create(self, validated_data):
        user = self.context['request'].user
        instance = WaterAdministration.objects.create(**validated_data)
        _log_entry(instance, user)
        return instance

    class Meta:
        model = WaterAdministration
        fields = ('subject', 'date_time', 'water_administered', 'hydrogel', 'user', 'url')
        extra_kwargs = {'url': {'view_name': 'water-administration-detail'}}
