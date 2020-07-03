from rest_framework import serializers
from actions.models import Session
from jobs.models import Task


class TaskStatusField(serializers.Field):

    def to_representation(self, int_status):
        choices = Task._meta.get_field('status').choices
        status = [ch for ch in choices if ch[0] == int_status]
        return status[0][1]

    def to_internal_value(self, str_status):
        choices = Task._meta.get_field('status').choices
        status = [ch for ch in choices if ch[1] == str_status]
        if len(status) == 0:
            raise serializers.ValidationError("Invalid status, choices are: " +
                                              ', '.join([ch[1] for ch in choices]))
        return status[0][0]


class TaskSerializer(serializers.ModelSerializer):
    parents = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='id', many=True,
        queryset=Task.objects.all(),
    )
    session = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='id', many=False,
        queryset=Session.objects.all()
    )
    status = TaskStatusField(required=False)

    class Meta:
        model = Task
        fields = '__all__'
