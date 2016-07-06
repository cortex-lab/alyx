from rest_framework import serializers
from .models import *

class ActionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Action
        fields = ('__all__')

class WeighingSerializer(serializers.ModelSerializer):

    users = serializers.SlugRelatedField(
        read_only=True,
        slug_field='username',
        many=True
     )

    subject = serializers.SlugRelatedField(
        slug_field='nickname',
        read_only=True)

    def create(self, validated_data):
        return Weighing.objects.create(**validated_data)

    class Meta:
        model = Weighing
        fields = ('id', 'users', 'subject', 'start_date_time', 'weight')

class WaterAdministrationSerializer(serializers.ModelSerializer):

    users = serializers.SlugRelatedField(
        read_only=True,
        slug_field='username',
        many=True
     )

    subject = serializers.SlugRelatedField(
        slug_field='nickname',
        read_only=True)

    def create(self, validated_data):
        return WaterAdministration.objects.create(**validated_data)

    class Meta:
        model = WaterAdministration
        fields = ('id', 'users', 'subject', 'start_date_time', 'water_administered')