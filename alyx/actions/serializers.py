from rest_framework import serializers
from .models import *

class ExperimentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Experiment
        fields = ('__all__')

class WeighingSerializer(serializers.ModelSerializer):

    user = serializers.SlugRelatedField(
        read_only=True,
        slug_field='username',
     )

    def create(self, validated_data):
        return Weighing.objects.create(**validated_data)

    class Meta:
        model = Weighing
        fields = ('date_time', 'weight', 'user')

class WaterAdministrationSerializer(serializers.ModelSerializer):

    user = serializers.SlugRelatedField(
        read_only=True,
        slug_field='username',
        many=True
     )

    def create(self, validated_data):
        return WaterAdministration.objects.create(**validated_data)

    class Meta:
        model = WaterAdministration
        fields = ('date_time', 'water_administered', 'user')