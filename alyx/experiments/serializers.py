from rest_framework import serializers
from actions.models import EphysSession
from experiments.models import (ProbeInsertion, TrajectoryEstimate, ProbeModel, CoordinateSystem,
                                Channel, BrainRegion)
from actions.serializers import SessionListSerializer


class ProbeInsertionSerializer(serializers.HyperlinkedModelSerializer):
    session = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='id',
        queryset=EphysSession.objects.filter(task_protocol__icontains='ephys'),
    )
    model = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='probe_model',
        queryset=ProbeModel.objects.all(),
    )

    class Meta:
        model = ProbeInsertion
        fields = '__all__'


class TrajectoryProvenanceField(serializers.Field):

    def to_representation(self, int_provenance):
        choices = TrajectoryEstimate._meta.get_field('provenance').choices
        provenance = [ch for ch in choices if ch[0] == int_provenance]
        return provenance[0][1]

    def to_internal_value(self, str_provenance):
        choices = TrajectoryEstimate._meta.get_field('provenance').choices
        provenance = [ch for ch in choices if ch[1] == str_provenance]
        if len(provenance) == 0:
            raise serializers.ValidationError("Invalid provenance, choices are: " +
                                              ', '.join([ch[1] for ch in choices]))
        return provenance[0][0]


class TrajectoryEstimateSerializer(serializers.HyperlinkedModelSerializer):
    probe_insertion = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='id', many=False,
        queryset=ProbeInsertion.objects.all(),
    )
    x = serializers.FloatField(required=True)
    y = serializers.FloatField(required=True)
    z = serializers.FloatField(required=False)
    depth = serializers.FloatField(required=True)
    theta = serializers.FloatField(required=True)
    phi = serializers.FloatField(required=True)
    roll = serializers.FloatField(required=False)
    provenance = TrajectoryProvenanceField(required=True)
    session = SessionListSerializer(read_only=True)
    probe_name = serializers.CharField(read_only=True)
    coordinate_system = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='name', many=False,
        queryset=CoordinateSystem.objects.all(),
    )

    class Meta:
        model = TrajectoryEstimate
        fields = '__all__'


class ChannelSerializer(serializers.HyperlinkedModelSerializer):
    probe_insertion = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='id', many=False,
        queryset=ProbeInsertion.objects.all(),
    )
    brain_region = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='id', many=False,
        queryset=BrainRegion.objects.all(),
    )

    class Meta:
        model = Channel
        fields = '__all__'
