import logging

from one.alf.spec import QC
from rest_framework import generics
from django_filters.rest_framework import CharFilter, UUIDFilter, NumberFilter
from django.db.models import Count, Exists, OuterRef


from alyx.base import BaseFilterSet, rest_permission_classes
from data.models import Dataset
from experiments.models import (ProbeInsertion, TrajectoryEstimate, Channel, BrainRegion,
                                ChronicInsertion, FOV, FOVLocation, ImagingStack)
from experiments.serializers import (ProbeInsertionListSerializer, ProbeInsertionDetailSerializer,
                                     TrajectoryEstimateSerializer, ChannelSerializer,
                                     BrainRegionSerializer, ChronicInsertionDetailSerializer,
                                     ChronicInsertionListSerializer, FOVSerializer,
                                     FOVLocationListSerializer, FOVLocationDetailSerializer,
                                     ImagingStackListSerializer, ImagingStackDetailSerializer)

logger = logging.getLogger(__name__)
"""
Probe insertion objects REST filters and views
"""


def _filter_qs_with_brain_regions(queryset, region_field: str, region_value: str):
    """
    Filter a Session, ProbeInsertion, ChronicInsertion or FOV queryset for those recording a given
    brain region.

    :param queryset: A QuerySet object (NB: must not have already been filtered.
    :param region_field: The BrainRegion model field to filter, e.g. id, name, acronym.
    :param region_value: The brain region to filter.
    :return: The filtered queryset.

    The IDs of the matching rows are resolved from the trajectories and field of view locations
    first, rather than joining those into the outer query: a row was previously returned once per
    matching channel, and the Session and ImagingStack branches had no DISTINCT to remove the
    duplicates again, so both the paginated rows and the reported count came back inflated.
    """
    brs = (BrainRegion.objects
           .filter(**{region_field: region_value})
           .get_descendants(include_self=True))
    qs_trajs = (TrajectoryEstimate.objects
                .filter(provenance__gte=70)
                .filter(channels__brain_region__in=brs))
    qs_fov_loc = (FOVLocation.objects
                  .filter(default_provenance=True)
                  .filter(brain_region__in=brs))

    def ids_of(queryset_, field):
        """The distinct non-null values of `field`, e.g. the insertions of the trajectories.

        Restricting the subquery to rows that have the field set matters: it lets the planner
        start from those rows instead of resolving every trajectory in the region first, which
        is what makes this cheap for the models few trajectories point at.
        """
        values = (queryset_
                  .filter(**{f'{field}__isnull': False})
                  .values_list(field, flat=True))
        return set(values)

    model = queryset.model.__name__
    if model == 'Session':
        ids = (ids_of(qs_trajs, 'probe_insertion__session') |
               ids_of(qs_fov_loc, 'field_of_view__session'))
    elif model in ('ProbeInsertion', 'ChronicInsertion'):
        # both models are the target of a TrajectoryEstimate foreign key named after them
        insertion = 'probe_insertion' if model == 'ProbeInsertion' else 'chronic_insertion'
        ids = ids_of(qs_trajs, insertion)
    elif model == 'FOV':
        ids = ids_of(qs_fov_loc, 'field_of_view')
    elif model == 'ImagingStack':
        ids = ids_of(qs_fov_loc, 'field_of_view__stack')
    else:
        logger.error('Filtering by brain region with a %s query set not supported', model)
        raise NotImplementedError(f'brain region filter not supported for {model}')
    return queryset.filter(pk__in=list(ids))


class ProbeInsertionFilter(BaseFilterSet):
    subject = CharFilter('session__subject__nickname')
    date = CharFilter('session__start_time__date')
    experiment_number = CharFilter('session__number')
    name = CharFilter('name')
    session = UUIDFilter('session')
    model = CharFilter('model__name')
    dataset_types = CharFilter(field_name='dataset_types', method='filter_dataset_types')
    datasets = CharFilter(field_name='datasets', method='filter_datasets')
    dataset_qc_lte = CharFilter(field_name='dataset_qc', method='filter_dataset_qc_lte')
    lab = CharFilter(field_name='session__lab__name', lookup_expr='iexact')
    project = CharFilter(field_name='session__projects__name', lookup_expr='icontains')
    task_protocol = CharFilter(field_name='session__task_protocol', lookup_expr='icontains')
    tag = CharFilter(field_name='tag', method='filter_tag')
    # brain region filters
    atlas_name = CharFilter(field_name='name__icontains', method='atlas')
    atlas_acronym = CharFilter(field_name='acronym__iexact', method='atlas')
    atlas_id = NumberFilter(field_name='pk', method='atlas')

    def filter_tag(self, queryset, _, value):
        """
        returns insertions that contain datasets tagged as
        :param queryset:
        :param value:
        :return:

        The matching insertions are resolved in a separate query rather than joining the datasets
        into the insertion query. A tag covers tens of thousands of datasets but only a few
        hundred insertions, and joining them in fans the insertion rows out by that ratio, then
        forces the DISTINCT to deduplicate over the full insertion, model, session, subject and
        lab row. Passing the insertion IDs in as a literal list also keeps the query planner from
        re-planning this as a correlated sub-plan over the whole insertion table.
        """
        insertion_ids = (Dataset.objects
                         .filter(tags__name__icontains=value, probe_insertion__isnull=False)
                         .values_list('probe_insertion', flat=True).distinct())
        return queryset.filter(pk__in=list(insertion_ids)).distinct()

    def atlas(self, queryset, name, value):
        """
        Returns probe insertions containing at least one channel in the given brain region.
        """
        return _filter_qs_with_brain_regions(queryset, name, value)

    def filter_dataset_types(self, queryset, _, value):
        """
        Returns insertions associated with datasets of all of the given type(s)

        The datasets are counted per insertion in a subquery instead of being joined into the
        insertion query and grouped there: the GROUP BY then covers the full insertion, model,
        session, subject and lab row rather than a single ID column.
        """
        dtypes = value.split(',')
        insertions = (Dataset.objects
                      .filter(dataset_type__name__in=dtypes, probe_insertion__isnull=False)
                      .values('probe_insertion')
                      .annotate(dtypes_count=Count('dataset_type__name', distinct=True))
                      .filter(dtypes_count__gte=len(dtypes))
                      .values_list('probe_insertion', flat=True))
        return queryset.filter(pk__in=insertions)

    def filter_datasets(self, queryset, _, value):
        """
        Returns insertions associated with all of the given dataset(s)

        As for `filter_dataset_types`, the datasets are counted per insertion in a subquery. The
        sessions filter of the same name special-cases a single dataset name into an Exists
        semi-join; that is deliberately not done here, as it measured no faster either way. There
        are two orders of magnitude fewer insertions than sessions to probe, which leaves the whole
        query under 100 ms whichever form is used.

        The distinct dataset *names* are counted, not the datasets: one name routinely matches
        several datasets of an insertion, across collections and revisions, and counting those
        instead let an insertion holding two copies of one requested name satisfy a request for
        two different names.
        """
        qc = QC.validate(self.request.query_params.get('dataset_qc_lte', QC.FAIL))
        dsets = sorted(set(value.split(',')))
        insertions = (Dataset.objects
                      .filter(name__in=dsets, qc__lte=qc, probe_insertion__isnull=False)
                      .values('probe_insertion')
                      .annotate(dsets_count=Count('name', distinct=True))
                      .filter(dsets_count__gte=len(dsets))
                      .values_list('probe_insertion', flat=True))
        return queryset.filter(pk__in=insertions)

    def filter_dataset_qc_lte(self, queryset, _, value):
        """
        Returns insertions with at least one dataset whose QC is at most the given value

        An Exists semi-join, so an insertion is returned once no matter how many of its datasets
        qualify. The previous join returned it once per qualifying dataset, which duplicated the
        rows across the paginated response and inflated the reported count to the number of
        (insertion, dataset) pairs.
        """
        # If filtering on datasets too, `filter_datasets` handles both QC and Datasets
        if 'datasets' in self.request.query_params:
            return queryset
        qc = QC.validate(value)
        return queryset.filter(
            Exists(Dataset.objects.filter(probe_insertion=OuterRef('pk'), qc__lte=qc)))

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
    -   **lab**: lab name (exact)
    -   **tag**: tag name (icontains)
    -   **dataset_types**: dataset type(s)
    -   **datasets**: datasets name(s)
    -   **dataset_qc_lte**: dataset QC value, e.g. PASS, WARNING, FAIL, CRITICAL
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
    filterset_class = ProbeInsertionFilter


class ProbeInsertionDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProbeInsertion.objects.all()
    queryset = ProbeInsertionDetailSerializer.setup_eager_loading(queryset)
    serializer_class = ProbeInsertionDetailSerializer
    permission_classes = rest_permission_classes()


class ChronicInsertionFilter(BaseFilterSet):
    subject = CharFilter('subject__nickname')
    lab = CharFilter('lab__name')
    model = CharFilter('model__name')
    probe = UUIDFilter('probe_insertion__id')
    session = UUIDFilter('probe_insertion__session__id')
    serial = CharFilter('serial')

    # brain region filters
    atlas_name = CharFilter(field_name='name__icontains', method='atlas')
    atlas_acronym = CharFilter(field_name='acronym__iexact', method='atlas')
    atlas_id = NumberFilter(field_name='pk', method='atlas')

    def atlas(self, queryset, name, value):
        """
        returns sessions containing at least one channel in the given brain region.
        Hierarchical tree search"
        """
        return _filter_qs_with_brain_regions(queryset, name, value)

    class Meta:
        model = ChronicInsertion
        exclude = ['json']


class ChronicInsertionList(generics.ListCreateAPIView):
    """
    get: **FILTERS**

    -   **name**: chronic insertion name `/chronic-insertions?name=probe00`
    -   **subject**: subject nickname: `/chronic-insertions?subject=Algernon`
    -   **lab**: lab name `/chronic-insertions?lab=UCLA`
    -   **model**: probe model name `/insertions?model=3A`
    -   **probe**: probe UUID
    `/chronic-insertions?probe=aad23144-0e52-4eac-80c5-c4ee2decb198`
    -   **session**: session UUID
    `/chronic-insertions?session=aad23144-0e52-4eac-80c5-c4ee2decb198`
    -   **serial**: serial no. of probe `/chronic-insertions?serial=101010`
    -   **atlas_name**: returns a session if any channel name icontains
     the value: `/chronic-insertions?brain_region=visual cortex`
    -   **atlas_acronym**: returns a session if any of its channels name exactly
     matches the value `/chronic-insertions?atlas_acronym=SSp-m4`, cf Allen CCFv2017
    -   **atlas_id**: returns a session if any of its channels id matches the
     provided value: `/chronic-insertions?atlas_id=950`, cf Allen CCFv2017

    [===> chronic insertion model reference](/admin/doc/models/experiments.chronicinsertion)
    """
    queryset = ChronicInsertion.objects.all()
    queryset = ChronicInsertionListSerializer.setup_eager_loading(queryset)
    serializer_class = ChronicInsertionListSerializer
    permission_classes = rest_permission_classes()
    filterset_class = ChronicInsertionFilter


class ChronicInsertionDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = ChronicInsertion.objects.all()
    serializer_class = ChronicInsertionDetailSerializer
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
    filterset_class = TrajectoryEstimateFilter


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
    filterset_class = ChannelFilter


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
    filterset_class = BrainRegionFilter


class BrainRegionDetail(generics.RetrieveUpdateAPIView):
    queryset = BrainRegion.objects.all()
    serializer_class = BrainRegionSerializer
    permission_classes = rest_permission_classes()


"""
FOV objects REST filters and views
"""


class FOVFilter(BaseFilterSet):
    subject = CharFilter('session__subject__nickname')
    lab = CharFilter(field_name='session__lab__name', lookup_expr='iexact')
    project = CharFilter('session__projects__name')
    date = CharFilter('session__start_time__date')
    experiment_number = CharFilter('session__number')
    dataset_types = CharFilter(field_name='dataset_types', method='filter_dataset_types')
    datasets = CharFilter(field_name='datasets', method='filter_datasets')
    dataset_qc_lte = CharFilter(field_name='dataset_qc', method='filter_dataset_qc_lte')
    imaging_type = CharFilter(field_name='imaging_type__name', lookup_expr='icontains')
    tag = CharFilter(field_name='tag', method='filter_tag')
    # brain region filters
    atlas_name = CharFilter(field_name='name__icontains', method='atlas')
    atlas_acronym = CharFilter(field_name='acronym__iexact', method='atlas')
    atlas_id = NumberFilter(field_name='pk', method='atlas')

    def atlas(self, queryset, name, value):
        """
        Returns FOVs in the given brain region.
        """
        return _filter_qs_with_brain_regions(queryset, name, value)

    def filter_tag(self, queryset, _, value):
        """
        Returns FOVs that contain datasets with the provided tag

        As for the sessions and probe insertions tag filters, the matching FOVs are resolved in a
        separate query: joining the datasets in fans the FOV rows out by the number of tagged
        datasets each one has, and the DISTINCT that removes them then has to deduplicate over the
        full FOV row. No FOV datasets are tagged yet, so this is currently cheap either way.
        """
        fov_ids = (Dataset.objects
                   .filter(tags__name__icontains=value, field_of_view__isnull=False)
                   .values_list('field_of_view', flat=True).distinct())
        return queryset.filter(pk__in=list(fov_ids)).distinct()

    def filter_dataset_types(self, queryset, _, value):
        """
        Returns FOVs associated with the given dataset type(s)

        As for the probe insertions filter of the same name, the datasets are counted per field of
        view in a subquery rather than joined into this query and grouped there.
        """
        dtypes = value.split(',')
        fovs = (Dataset.objects
                .filter(dataset_type__name__in=dtypes, field_of_view__isnull=False)
                .values('field_of_view')
                .annotate(dtypes_count=Count('dataset_type__name', distinct=True))
                .filter(dtypes_count__gte=len(dtypes))
                .values_list('field_of_view', flat=True))
        return queryset.filter(pk__in=fovs)

    def filter_datasets(self, queryset, _, value):
        """
        Returns FOVs associated with the given dataset(s)

        Only datasets whose QC is at most `dataset_qc_lte` count, as for the sessions and probe
        insertions filters of the same name.

        As for the probe insertions filter, the datasets are counted per field of view in a
        subquery, it is the distinct dataset names that are counted rather than the datasets, and a
        single name is not special-cased: no dataset is currently associated with any field of
        view, so there is nothing to measure such a special case against.
        """
        qc = QC.validate(self.request.query_params.get('dataset_qc_lte', QC.FAIL))
        dsets = sorted(set(value.split(',')))
        fovs = (Dataset.objects
                .filter(name__in=dsets, qc__lte=qc, field_of_view__isnull=False)
                .values('field_of_view')
                .annotate(dsets_count=Count('name', distinct=True))
                .filter(dsets_count__gte=len(dsets))
                .values_list('field_of_view', flat=True))
        return queryset.filter(pk__in=fovs)

    def filter_dataset_qc_lte(self, queryset, _, value):
        """
        Returns FOVs with at least one dataset whose QC is at most the given value

        An Exists semi-join, so a field of view is returned once no matter how many of its datasets
        qualify.
        """
        # If filtering on datasets too, `filter_datasets` handles both QC and Datasets
        if 'datasets' in self.request.query_params:
            return queryset
        qc = QC.validate(value)
        return queryset.filter(
            Exists(Dataset.objects.filter(field_of_view=OuterRef('pk'), qc__lte=qc)))

    class Meta:
        model = FOV
        exclude = ['json']


class FOVList(generics.ListCreateAPIView):
    """
    get: **FILTERS**

    -   **provenance**: field of view provenance
        must one of the strings among those choices:
        'Estimate', 'Functional', 'Landmark', 'Histology'.
        `/fields-of-view?provenance=Estimate`
    -   **atlas**: One or more brain regions covered by a field of view
    -   **subject**: subject nickname: `/fields-of-view?subject=Algernon`
    -   **project**: the project name
    -   **date**: session date: `/fields-of-view?date=2020-01-15`
    -   **experiment_number**: session number `/fields-of-view?experiment_number=1`
    -   **session**: `/fields-of-view?session=aad23144-0e52-4eac-80c5-c4ee2decb198`
    -   **name**: field of view name `/trajectories?name=FOV_01`
    -   **tag**: tag name of the associated datasets (icontains)
        `/fields-of-view?tag=2021_Q1_IBL_et_al_Behaviour`
    -   **dataset_types**: dataset type(s)
    -   **datasets**: dataset name(s)
    -   **dataset_qc_lte**: dataset QC value, e.g. PASS, WARNING, FAIL, CRITICAL
        `/fields-of-view?dataset_qc_lte=WARNING`
    -   **imaging_type**: imaging type name (icontains)

    [===> FOV model reference](/admin/doc/models/experiments.fov)
    """
    queryset = FOV.objects.all()
    queryset = FOVSerializer.setup_eager_loading(queryset)
    serializer_class = FOVSerializer
    permission_classes = rest_permission_classes()
    filterset_class = FOVFilter


class FOVDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = FOV.objects.all()
    serializer_class = FOVSerializer
    permission_classes = rest_permission_classes()


class FOVLocationFilter(BaseFilterSet):
    provenance = CharFilter(method='enum_field_filter')
    coordinate_system = CharFilter('coordinate_system__name')
    x = NumberFilter(lookup_expr='contains')
    y = NumberFilter(lookup_expr='contains')
    z = NumberFilter(lookup_expr='contains')
    n_xyz = NumberFilter(lookup_expr='contains')

    class Meta:
        model = FOVLocation
        exclude = ['json']


class FOVLocationList(generics.ListCreateAPIView):
    """
    get: **FILTERS**

    -   **provenance**: field of view provenance
        must one of the strings among those choices:
        'Estimate', 'Functional', 'Landmark', 'Histology'
        `/fov-location?provenance=Estimate`
    -   **fov: field of view: `/fov-location?fov=aad23144-0e52-4eac-80c5-c4ee2decb198`
    -   **default_provenance**: default provenance: `/fov-location?default_provenance=True`
    -   **brain_location**: one or more brain location IDs:
        `/fov-location?brain_location=[10, 263]`

    [===> FOVLocation model reference](/admin/doc/models/experiments.fovlocation)
    """
    queryset = FOVLocation.objects.all()
    queryset = FOVLocationListSerializer.setup_eager_loading(queryset)
    permission_classes = rest_permission_classes()
    filterset_class = FOVLocationFilter

    def get_serializer_class(self):
        if not self.request:
            return FOVLocationListSerializer
        if self.request.method == 'GET':
            return FOVLocationListSerializer
        if self.request.method == 'POST':
            return FOVLocationDetailSerializer


class FOVLocationDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = FOVLocation.objects.all()
    queryset = FOVLocationDetailSerializer.setup_eager_loading(queryset)
    serializer_class = FOVLocationDetailSerializer
    permission_classes = rest_permission_classes()


class ImagingStackFilter(BaseFilterSet):
    """Basic support for filtering stacks by brain regions covered.

    Most situations are already covered by the field of view filter, using the stack ID.
    """
    # brain region filters
    atlas_name = CharFilter(field_name='name__icontains', method='atlas')
    atlas_acronym = CharFilter(field_name='acronym__iexact', method='atlas')
    atlas_id = NumberFilter(field_name='pk', method='atlas')

    def atlas(self, queryset, name, value):
        """
        Returns stacks covering the given brain region.
        """
        return _filter_qs_with_brain_regions(queryset, name, value)

    class Meta:
        model = ImagingStack
        exclude = ('json',)


class ImagingStackList(generics.ListCreateAPIView):
    """
    get: **FILTERS**

    -   **atlas**: One or more brain regions covered by a stack
    -   **name**: The image stack name

    [===> ImagingStack model reference](/admin/doc/models/experiments.imagingstack)
    """
    queryset = ImagingStack.objects.all()
    queryset = ImagingStackDetailSerializer.setup_eager_loading(queryset)
    permission_classes = rest_permission_classes()
    filterset_class = ImagingStackFilter

    def get_serializer_class(self):
        if not self.request or self.request.method == 'GET':
            return ImagingStackListSerializer
        if self.request.method == 'POST':
            return ImagingStackDetailSerializer


class ImagingStackDetail(generics.RetrieveAPIView):
    """
    [===> ImagingStack model reference](/admin/doc/models/experiments.imagingstack)
    """
    queryset = ImagingStack.objects.all()
    queryset = ImagingStackDetailSerializer.setup_eager_loading(queryset)
    serializer_class = ImagingStackDetailSerializer
    permission_classes = rest_permission_classes()
