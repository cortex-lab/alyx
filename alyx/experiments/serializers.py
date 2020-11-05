from rest_framework import serializers
from alyx.base import BaseSerializerEnumField
from actions.models import EphysSession, Session
from experiments.models import (ProbeInsertion, TrajectoryEstimate, ProbeModel, CoordinateSystem,
                                Channel, BrainRegion)


class SessionListSerializer(serializers.ModelSerializer):

    @staticmethod
    def setup_eager_loading(queryset):
        """ Perform necessary eager loading of data to avoid horrible performance."""
        queryset = queryset.select_related('subject', 'lab')
        return queryset.order_by('-start_time')

    subject = serializers.SlugRelatedField(read_only=True, slug_field='nickname')
    lab = serializers.SlugRelatedField(read_only=True, slug_field='name')

    class Meta:
        model = Session
        fields = ('subject', 'start_time', 'number', 'lab', 'id', 'task_protocol')


class TrajectoryEstimateSerializer(serializers.ModelSerializer):
    probe_insertion = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='id', many=False,
        queryset=ProbeInsertion.objects.all(),
    )
    x = serializers.FloatField(required=True, allow_null=True)
    y = serializers.FloatField(required=True, allow_null=True)
    z = serializers.FloatField(required=False, allow_null=True)
    depth = serializers.FloatField(required=True, allow_null=True)
    theta = serializers.FloatField(required=True, allow_null=True)
    phi = serializers.FloatField(required=True, allow_null=True)
    roll = serializers.FloatField(required=False, allow_null=True)
    provenance = BaseSerializerEnumField(required=True)
    session = SessionListSerializer(read_only=True)
    probe_name = serializers.CharField(read_only=True)
    coordinate_system = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='name', many=False,
        queryset=CoordinateSystem.objects.all(),
    )

    class Meta:
        model = TrajectoryEstimate
        fields = '__all__'


class ChannelSerializer(serializers.ModelSerializer):
    trajectory_estimate = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='id', many=False,
        queryset=TrajectoryEstimate.objects.all(),
    )
    brain_region = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='id', many=False,
        queryset=BrainRegion.objects.all(),
    )

    class Meta:
        model = Channel
        fields = '__all__'


class ProbeInsertionSerializer(serializers.ModelSerializer):
    session = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='id',
        queryset=EphysSession.objects.filter(task_protocol__icontains='ephys'),
    )
    model = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='probe_model',
        queryset=ProbeModel.objects.all(),
    )
    session_info = SessionListSerializer(read_only=True, source='session')

    class Meta:
        model = ProbeInsertion
        fields = '__all__'


class BrainRegionSerializer(serializers.ModelSerializer):
    # we do not want anybody to update the ontology from rest ! Only the description
    id = serializers.IntegerField(read_only=True)
    acronym = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    parent = serializers.SlugRelatedField(read_only=True, slug_field='id')

    class Meta:
        model = BrainRegion
        fields = ('id', 'acronym', 'name', 'description', 'parent', 'related_descriptions')
