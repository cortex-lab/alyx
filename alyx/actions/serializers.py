from rest_framework import serializers
from .models import *

class ExperimentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Experiment
        fields = ('__all__')

class WeighingListSerializer(serializers.HyperlinkedModelSerializer):

    user = serializers.SlugRelatedField(
        read_only=True,
        slug_field='username',
     )

    class Meta:
        model = Weighing
        fields = ('date_time', 'weight', 'user', 'url')

class WeighingDetailSerializer(serializers.HyperlinkedModelSerializer):

    user = serializers.SlugRelatedField(
        read_only=False,
        slug_field='username',
        queryset=Weighing.objects.all()
     )

    def create(self, validated_data):
        return Weighing.objects.create(**validated_data)

    class Meta:
        model = Weighing
        fields = ('date_time', 'weight', 'user', 'weighing_scale', 'url')




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