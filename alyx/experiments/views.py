from rest_framework import generics, permissions
from django_filters.rest_framework import FilterSet, CharFilter, UUIDFilter

from experiments.models import ProbeInsertion, TrajectoryEstimate, Channel
from experiments.serializers import (ProbeInsertionSerializer, TrajectoryEstimateSerializer,
                                     ChannelSerializer)

"""
Probe insertion objects REST filters and views
"""


class ProbeInsertionFilter(FilterSet):
    subject = CharFilter('session__subject__nickname')
    date = CharFilter('session__start_time__date')
    experiment_number = CharFilter('session__number')
    name = CharFilter('name')
    session = UUIDFilter('session')

    class Meta:
        model = ProbeInsertion
        exclude = ['json']


class ProbeInsertionList(generics.ListCreateAPIView):
    queryset = ProbeInsertion.objects.all()
    serializer_class = ProbeInsertionSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_class = ProbeInsertionFilter


class ProbeInsertionDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProbeInsertion.objects.all()
    serializer_class = ProbeInsertionSerializer
    permission_classes = (permissions.IsAuthenticated,)


"""
Trajectory Estimates objects REST filters and views
"""


class TrajectoryEstimateFilter(FilterSet):
    provenance = CharFilter(method='provenance_filter')
    subject = CharFilter('probe_insertion__session__subject__nickname')
    project = CharFilter('probe_insertion__session__project__name')
    date = CharFilter('probe_insertion__session__start_time__date')
    experiment_number = CharFilter('probe_insertion__session__number')
    session = UUIDFilter('probe_insertion__session__id')

    class Meta:
        model = TrajectoryEstimate
        exclude = ['json']

    def provenance_filter(self, queryset, name, value):
        choices = TrajectoryEstimate._meta.get_field('provenance').choices
        # create a dictionary string -> integer
        value_map = {v.lower(): k for k, v in choices}
        # get the integer value for the input string
        try:
            value = value_map[value.lower().strip()]
        except KeyError:
            raise ValueError("Invalid provenance, choices are: " +
                             ', '.join([ch[1] for ch in choices]))
        return queryset.filter(provenance=value)


class TrajectoryEstimateList(generics.ListCreateAPIView):
    queryset = TrajectoryEstimate.objects.all()
    serializer_class = TrajectoryEstimateSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_class = TrajectoryEstimateFilter


class TrajectoryEstimateDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = TrajectoryEstimate.objects.all()
    serializer_class = TrajectoryEstimateSerializer
    permission_classes = (permissions.IsAuthenticated,)


class ChannelFilter(FilterSet):
    session = UUIDFilter('trajectory_estimate__probe_insertion__session')
    probe_insertion = UUIDFilter('trajectory_estimate__probe_insertion')

    class Meta:
        model = Channel
        exclude = ['json']


class ChannelList(generics.ListCreateAPIView):

    def get_serializer(self, *args, **kwargs):
        """ if an array is passed, set serializer to many """
        if isinstance(kwargs.get('data', {}), list):
            kwargs['many'] = True
        return super(generics.ListCreateAPIView, self).get_serializer(*args, **kwargs)

    queryset = Channel.objects.all()
    serializer_class = ChannelSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_class = ChannelFilter


class ChannelDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Channel.objects.all()
    serializer_class = ChannelSerializer
    permission_classes = (permissions.IsAuthenticated,)
