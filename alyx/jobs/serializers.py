from rest_framework import serializers
from actions.models import Session
from jobs.models import Task
from data.models import DataRepository
from alyx.base import BaseSerializerEnumField


class TaskSerializer(serializers.ModelSerializer):
    parents = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='id', many=True,
        queryset=Task.objects.all(),
    )
    session = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='id', many=False,
        queryset=Session.objects.all()
    )
    data_repository = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='name', many=False,
        queryset=DataRepository.objects.all()
    )
    status = BaseSerializerEnumField(required=False)

    class Meta:
        model = Task
        fields = '__all__'
