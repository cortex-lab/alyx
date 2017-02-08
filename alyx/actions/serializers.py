from rest_framework import serializers
from .models import *
from subjects.models import Subject
from equipment.models import LabLocation
from django.contrib.auth.models import User
from data.serializers import DatasetSerializer

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

class ExperimentListSerializer(BaseActionSerializer):

    class Meta:
        model = Experiment
        fields = ('subject', 'users', 'location', 'procedures', 'narrative', 'date_time', 'url')

class ExperimentDetailSerializer(BaseActionSerializer):

    datasets_related = DatasetSerializer(many=True, read_only=True)

    class Meta:
        model = Experiment
        fields = ('subject', 'users', 'location', 'procedures', 'narrative', 'date_time', 'url', 'json', 'datasets_related')

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
        return Weighing.objects.create(**validated_data)

    class Meta:
        model = Weighing
        fields = ('subject', 'date_time', 'weight', 'user', 'weighing_scale', 'url')

class WaterAdministrationListSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = WaterAdministration
        fields = ('date_time', 'water_administered', 'url')
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
        return WaterAdministration.objects.create(**validated_data)

    class Meta:
        model = WaterAdministration
        fields = ('subject', 'date_time', 'water_administered', 'user', 'url')
        extra_kwargs = {'url': {'view_name': 'water-administration-detail'}}
