from rest_framework import generics
from django_filters.rest_framework import CharFilter, UUIDFilter, NumberFilter
from django.db.models import F, Func, Value, CharField, functions, Q


from alyx.base import BaseFilterSet, rest_permission_classes
from data.models import Dataset
from experiments.models import ProbeInsertion, TrajectoryEstimate, Channel, BrainRegion
from experiments.serializers import (ProbeInsertionListSerializer, ProbeInsertionDetailSerializer,
                                     TrajectoryEstimateSerializer,
                                     ChannelSerializer, BrainRegionSerializer)

"""
Probe insertion objects REST filters and views
"""


def _filter_qs_with_brain_regions(self, queryset, region_field, region_value):
    brs = BrainRegion.objects.filter(
        **{region_field: region_value}).get_descendants(include_self=True)
    qs_trajs = TrajectoryEstimate.objects.filter(provenance__gte=70). \
        prefetch_related('channels__brain_region'). \
        filter(channels__brain_region__in=brs).distinct()
    if queryset.model.__name__ == 'Session':
        qs = queryset.prefetch_related('probe_insertion__trajectory_estimate').filter(
            probe_insertion__trajectory_estimate__in=qs_trajs)
    elif queryset.model.__name__ == 'ProbeInsertion':
        qs = queryset.prefetch_related('trajectory_estimate').filter(
            trajectory_estimate__in=qs_trajs)
    return qs


class ProbeInsertionFilter(BaseFilterSet):
    subject = CharFilter('session__subject__nickname')
    date = CharFilter('session__start_time__date')
    experiment_number = CharFilter('session__number')
    name = CharFilter('name')
    session = UUIDFilter('session')
    model = CharFilter('model__name')
    dataset_type = CharFilter(method='dtype_exists')
    no_dataset_type = CharFilter(method='dtype_not_exists')
    project = CharFilter(field_name='session__project__name', lookup_expr='icontains')
    task_protocol = CharFilter(field_name='session__task_protocol', lookup_expr='icontains')
    # brain region filters
    atlas_name = CharFilter(field_name='name__icontains', method='atlas')
    atlas_acronym = CharFilter(field_name='acronym__iexact', method='atlas')
    atlas_id = NumberFilter(field_name='pk', method='atlas')

    def atlas(self, queryset, name, value):
        """
        returns sessions containing at least one channel in the given brain region.
        Hierarchical tree search"
        """
        return _filter_qs_with_brain_regions(self, queryset, name, value)

    def dtype_exists(self, probes, _, dtype_name):
        """
        Filter for probe insertions that contain specified dataset type
        """
        dsets = Dataset.objects.filter(dataset_type__name=dtype_name)

        # Annotate with new column that contains unique session, probe name
        dsets = dsets.annotate(session_probe_name=functions.Concat(
            functions.Cast(F('session'), output_field=CharField()),
            Func(F('collection'), Value('/'), Value(2), function='split_part'),
            output_field=CharField()))

        probes = probes.annotate(session_probe_name=functions.Concat(
            functions.Cast(F('session'), output_field=CharField()), F('name'),
            output_field=CharField()))

        queryset = probes.filter(session_probe_name__in=dsets.values_list('session_probe_name',
                                                                          flat=True))
        return queryset

    def dtype_not_exists(self, probes, _, dtype_name):
        """
        Filter for probe insertions that don't contain specified dataset type
        """

        dsets = Dataset.objects.filter(dataset_type__name=dtype_name)

        # Annotate with new column that contains unique session, probe name
        dsets = dsets.annotate(session_probe_name=functions.Concat(
            functions.Cast(F('session'), output_field=CharField()),
            Func(F('collection'), Value('/'), Value(2), function='split_part'),
            output_field=CharField()))

        probes = probes.annotate(session_probe_name=functions.Concat(
            functions.Cast(F('session'), output_field=CharField()), F('name'),
            output_field=CharField()))

        queryset = probes.filter(~Q(session_probe_name__in=dsets.values_list('session_probe_name',
                                                                             flat=True)))
        return queryset

    class Meta:
        model = ProbeInsertion
        exclude = ['json']


class ProbeInsertionList(generics.ListCreateAPIView):
    """
    get: **FILTERS**

    -   **name**: probe insertion name `/trajectories?name=probe00`
    -   **subject**: subject nickname: `/insertions?subject=Algernon`
    -   **date**: session date: `/inssertions?date=2020-01-15`
    -   **experiment_number**: session number `/insertions?experiment_number=1`
    -   **session**: session UUID`/insertions?session=aad23144-0e52-4eac-80c5-c4ee2decb198`
    -   **task_protocol** (icontains)
    -   **location**: location name (icontains)
    -   **project**: project name (icontains)
    -   **model**: probe model name `/insertions?model=3A`
    -   **dataset_type**: contains dataset type `/insertions?dataset_type=clusters.metrics`
    -   **no_dataset_type**: doesn't contain dataset type
    `/insertions?no_dataset_type=clusters.metrics`
    -   **atlas_name**: returns a session if any channel name icontains
     the value: `/insertions?brain_region=visual cortex`
    -   **atlas_acronym**: returns a session if any of its channels name exactly
     matches the value `/insertions?atlas_acronym=SSp-m4`, cf Allen CCFv2017
    -   **atlas_id**: returns a session if any of its channels id matches the
     provided value: `/insertions?atlas_id=950`, cf Allen CCFv2017

    [===> probe insertion model reference](/admin/doc/models/experiments.probeinsertion)
    """
    queryset = ProbeInsertion.objects.all()
    queryset = ProbeInsertionListSerializer.setup_eager_loading(queryset)
    serializer_class = ProbeInsertionListSerializer
    permission_classes = rest_permission_classes()
    filter_class = ProbeInsertionFilter


class ProbeInsertionDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProbeInsertion.objects.all()
    serializer_class = ProbeInsertionDetailSerializer
    permission_classes = rest_permission_classes()


"""
Trajectory Estimates objects REST filters and views
"""


class TrajectoryEstimateFilter(BaseFilterSet):
    provenance = CharFilter(method='enum_field_filter')
    subject = CharFilter('probe_insertion__session__subject__nickname')
    project = CharFilter('probe_insertion__session__projects__name')
    date = CharFilter('probe_insertion__session__start_time__date')
    experiment_number = CharFilter('probe_insertion__session__number')
    session = UUIDFilter('probe_insertion__session__id')
    probe = CharFilter('probe_insertion__name')

    class Meta:
        model = TrajectoryEstimate
        exclude = ['json']


class TrajectoryEstimateList(generics.ListCreateAPIView):
    """
    get: **FILTERS**

    -   **provenance**: probe insertion provenance
        must one of the strings among those choices:
        'Ephys aligned histology track', 'Histology track', 'Micro-manipulator', 'Planned'
        `/trajectories?provenance=Planned`
    -   **subject: subject nickname: `/trajectories?subject=Algernon`
    -   **date**: session date: `/trajectories?date=2020-01-15`
    -   **experiment_number**: session number `/trajectories?experiment_number=1`
    -   **session**: `/trajectories?session=aad23144-0e52-4eac-80c5-c4ee2decb198`
    -   **probe**: probe_insertion name `/trajectories?probe=probe01`

    [===> trajectory model reference](/admin/doc/models/experiments.trajectoryestimate)
    """
    queryset = TrajectoryEstimate.objects.all()
    serializer_class = TrajectoryEstimateSerializer
    permission_classes = rest_permission_classes()
    filter_class = TrajectoryEstimateFilter


class TrajectoryEstimateDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = TrajectoryEstimate.objects.all()
    serializer_class = TrajectoryEstimateSerializer
    permission_classes = rest_permission_classes()


class ChannelFilter(BaseFilterSet):
    session = UUIDFilter('trajectory_estimate__probe_insertion__session')
    probe_insertion = UUIDFilter('trajectory_estimate__probe_insertion')
    subject = CharFilter('trajectory_estimate__probe_insertion__session__subject__nickname')
    lab = CharFilter('trajectory_estimate__probe_insertion__session__lab__name')

    class Meta:
        model = Channel
        exclude = ['json']


class ChannelList(generics.ListCreateAPIView):
    """
    get: **FILTERS**

    -   **subject**: subject nickname: `/channels?subject=Algernon`
    -   **session**: UUID `/channels?session=aad23144-0e52-4eac-80c5-c4ee2decb198`
    -   **lab**: lab name `/channels?lab=wittenlab`
    -   **probe_insertion**: UUID  `/channels?probe_insertion=aad23144-0e52-4eac-80c5-c4ee2decb198`

    [===> channel model reference](/admin/doc/models/experiments.channel)
    """

    def get_serializer(self, *args, **kwargs):
        """ if an array is passed, set serializer to many """
        if isinstance(kwargs.get('data', {}), list):
            kwargs['many'] = True
        return super(generics.ListCreateAPIView, self).get_serializer(*args, **kwargs)

    queryset = Channel.objects.all()
    serializer_class = ChannelSerializer
    permission_classes = rest_permission_classes()
    filter_class = ChannelFilter


class ChannelDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Channel.objects.all()
    serializer_class = ChannelSerializer
    permission_classes = rest_permission_classes()


class BrainRegionFilter(BaseFilterSet):
    acronym = CharFilter(lookup_expr='iexact')
    description = CharFilter(lookup_expr='icontains')
    name = CharFilter(lookup_expr='icontains')
    ancestors = CharFilter(field_name='ancestors', method='filter_ancestors')
    descendants = CharFilter(field_name='descendants', method='filter_descendants')

    class Meta:
        model = BrainRegion
        fields = ('id', 'acronym', 'description', 'name', 'parent')

    def filter_descendants(self, queryset, _, pk):
        r = BrainRegion.objects.get(pk=pk) if pk.isdigit() else BrainRegion.objects.get(acronym=pk)
        return r.get_descendants(include_self=True).exclude(id=0)

    def filter_ancestors(self, queryset, _, pk):
        r = BrainRegion.objects.get(pk=pk) if pk.isdigit() else BrainRegion.objects.get(acronym=pk)
        return r.get_ancestors(include_self=True).exclude(pk=0)


class BrainRegionList(generics.ListAPIView):
    """
    get: **FILTERS**

    -   **id**: Allen primary key: `/brain-regions?id=687`
    -   **acronym**: iexact on acronym `/brain-regions?acronym=RSPv5`
    -   **name**: icontains on name `/brain-regions?name=retrosplenial`
    -   **description**: icontains on description `/brain-regions?description=RSPv5`
    -   **parent**: get child nodes `/brain-regions?parent=315`
    -   **ancestors**: get all ancestors for a given ID
    -   **descendants**: get all descendants for a given ID

    [===> brain region model reference](/admin/doc/models/experiments.brainregion)
    """
    queryset = BrainRegion.objects.all()
    serializer_class = BrainRegionSerializer
    permission_classes = rest_permission_classes()
    filter_class = BrainRegionFilter


class BrainRegionDetail(generics.RetrieveUpdateAPIView):
    queryset = BrainRegion.objects.all()
    serializer_class = BrainRegionSerializer
    permission_classes = rest_permission_classes()
