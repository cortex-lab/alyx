from rest_framework import serializers
from experiments.models import TrajectoryEstimate
from actions.models import Session
from jobs.models import Job, Task


class JobStatusField(serializers.Field):

    def to_representation(self, int_provenance):
        choices = TrajectoryEstimate._meta.get_field('status').choices
        status = [ch for ch in choices if ch[0] == int_provenance]
        return status[0][1]

    def to_internal_value(self, str_provenance):
        choices = TrajectoryEstimate._meta.get_field('status').choices
        status = [ch for ch in choices if ch[1] == str_provenance]
        if len(status) == 0:
            raise serializers.ValidationError("Invalid status, choices are: " +
                                              ', '.join([ch[1] for ch in choices]))
        return status[0][0]


class JobSerializer(serializers.HyperlinkedModelSerializer):
    task = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='name', many=False,
        queryset=Task.objects.all(),
    )
    data_repository = serializers.SlugRelatedField(
        read_only=True, required=False, slug_field='name', many=False,
    )
    session = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='id', many=False,
        queryset=Session.objects.all()
    )
    version = serializers.FloatField(required=False)

    class Meta:
        model = Job
        fields = ['task', 'version', 'session', 'data_repository']
