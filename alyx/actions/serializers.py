from rest_framework import serializers
from .models import *
from subjects.models import Subject
from django.contrib.auth.models import User

class ExperimentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Experiment
        fields = ('__all__')

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
        queryset=User.objects.all()
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
        queryset=User.objects.all()
     )

    def create(self, validated_data):
        return WaterAdministration.objects.create(**validated_data)

    class Meta:
        model = WaterAdministration
        fields = ('subject', 'date_time', 'water_administered', 'user')