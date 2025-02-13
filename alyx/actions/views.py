from datetime import timedelta, date, datetime
from operator import itemgetter

from django.contrib.postgres.fields import JSONField
from django.db.models import Count, Q, F, ExpressionWrapper, FloatField, BooleanField
from django.db.models.deletion import Collector
from django_filters.rest_framework.filters import CharFilter
from django.http import HttpResponse
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.generic.list import ListView

import django_filters
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView
from one.alf.spec import QC

from alyx.base import base_json_filter, BaseFilterSet, rest_permission_classes
from data.models import Dataset
from subjects.models import Subject
from experiments.views import _filter_qs_with_brain_regions
from .water_control import water_control, to_date
from .models import (
    BaseAction, Session, WaterAdministration, WaterRestriction,
    Weighing, WaterType, LabLocation, Surgery, ProcedureType)
from .serializers import (LabLocationSerializer,
                          ProcedureTypeSerializer,
                          SessionListSerializer,
                          SessionDetailSerializer,
                          SurgerySerializer,
                          WaterAdministrationDetailSerializer,
                          WeighingDetailSerializer,
                          WaterTypeDetailSerializer,
                          WaterRestrictionListSerializer,
                          )


class BaseActionFilter(BaseFilterSet):
    subject = django_filters.CharFilter(field_name='subject__nickname', lookup_expr=('iexact'))
    nickname = django_filters.CharFilter(field_name='subject__nickname', lookup_expr='iexact')
    users = django_filters.CharFilter(field_name='users__username', method=('filter_users'))
    date_range = django_filters.CharFilter(field_name='date_range', method=('filter_date_range'))
    lab = django_filters.CharFilter(field_name='lab__name', lookup_expr=('iexact'))
    location = django_filters.CharFilter(field_name='location__name', lookup_expr=('icontains'))
    json = django_filters.CharFilter(field_name='json', method=('filter_json'))

    def filter_users(self, queryset, name, value):
        users = value.split(',')
        queryset = queryset.filter(users__username__in=users)
        queryset = queryset.annotate(
            users_count=Count('users__username'))
        queryset = queryset.filter(users_count__gte=len(users))
        return queryset

    def filter_date_range(self, queryset, _, value):
        drange = value.split(',')
        queryset = queryset.filter(
            Q(start_time__date__gte=drange[0]),
            Q(start_time__date__lte=drange[1]),
        )
        return queryset

    def filter_json(self, queryset, name, value):
        return base_json_filter('json', queryset, name, value)

    class Meta:
        exclude = []
        filter_overrides = {
            JSONField: {
                'filterset_class': CharFilter,
            },
        }


class SubjectHistoryListView(ListView):
    template_name = 'subject_history.html'

    CLASS_FIELDS = {
        'Session': ('number', 'n_correct_trials', 'n_trials'),
        'Weighing': ('weight',),
        'WaterRestriction': (),
    }

    CLASS_TYPE_FIELD = {
        'Session': 'type',
        'WaterRestriction': 'water_type',
    }

    def get_context_data(self, **kwargs):
        context = super(SubjectHistoryListView, self).get_context_data(**kwargs)
        subject = Subject.objects.get(pk=self.kwargs['subject_id'])
        context['title'] = mark_safe(
            'Subject history of <a href="%s">%s</a>' % (
                reverse('admin:subjects_subject_change',
                        args=[subject.id]),
                subject.nickname))
        context['site_header'] = 'Alyx'
        return context

    def get_queryset(self):
        subject = Subject.objects.get(pk=self.kwargs['subject_id'])
        collector = Collector(using="default")
        collector.collect([subject])
        out = []
        for model, instance in collector.instances_with_model():
            if model._meta.app_label == 'data':
                continue
            if not isinstance(instance, BaseAction):
                continue
            url = reverse('admin:%s_%s_change' % (instance._meta.app_label,
                                                  instance._meta.model_name), args=[instance.id])
            item = {}
            clsname = instance.__class__.__name__
            item['url'] = url
            item['name'] = model.__name__
            item['type'] = getattr(
                instance, self.CLASS_TYPE_FIELD.get(clsname, ''), None)
            item['date_time'] = instance.start_time
            i = 0
            for n in self.CLASS_FIELDS.get(clsname, ()):
                v = getattr(instance, n, None)
                if v is None:
                    continue
                item['arg%d' % i] = '%s: %s' % (n, v)
                i += 1
            out.append(item)
        out = sorted(out, key=itemgetter('date_time'), reverse=True)
        return out


def date_range(start_date, end_date):
    for n in range(int((end_date - start_date).days) + 1):
        yield (start_date + timedelta(n))


class WaterHistoryListView(ListView):
    template_name = 'water_history.html'

    def get_context_data(self, **kwargs):
        context = super(WaterHistoryListView, self).get_context_data(**kwargs)
        subject = Subject.objects.get(pk=self.kwargs['subject_id'])
        context['title'] = mark_safe(
            'Water history of <a href="%s">%s</a>' % (
                reverse('admin:subjects_subject_change',
                        args=[subject.id]),
                subject.nickname))
        context['site_header'] = 'Alyx'
        url = reverse('weighing-plot', kwargs={'subject_id': subject.id})
        context['plot_url'] = url
        return context

    def get_queryset(self):
        subject = Subject.objects.get(pk=self.kwargs['subject_id'])
        return water_control(subject).to_jsonable()[::-1]


def last_monday(reqdate=None):
    reqdate = reqdate or date.today()
    monday = reqdate - timedelta(days=reqdate.weekday())
    assert monday.weekday() == 0
    return monday


def training_days(reqdate=None):
    monday = last_monday(reqdate=reqdate)
    wr = WaterRestriction.objects.filter(
        start_time__isnull=False, end_time__isnull=True,
    ).order_by('subject__responsible_user__username', 'subject__nickname')
    next_monday = monday + timedelta(days=7)
    for w in wr:
        sessions = Session.objects.filter(
            subject=w.subject, start_time__gte=monday, start_time__lt=next_monday)
        dates = sorted(set([_[0] for _ in sessions.order_by('start_time').
                            values_list('start_time')]))
        wds = set(date.weekday() for date in dates)
        yield {
            'nickname': w.subject.nickname,
            'username': w.subject.responsible_user.username,
            'url': reverse('admin:subjects_subject_change', args=[w.subject.pk]),
            'n_training_days': len(wds),
            'training_ok': len(wds) >= 5,
            'training_days': [wd in wds for wd in range(7)],
        }


class TrainingListView(ListView):
    template_name = 'training.html'

    def get_context_data(self, **kwargs):
        context = super(TrainingListView, self).get_context_data(**kwargs)
        reqdate = self.kwargs.get('date', None) or date.today().strftime('%Y-%m-%d')
        reqdate = to_date(reqdate)
        monday = last_monday(reqdate=reqdate)
        self.monday = monday
        previous_week = (monday - timedelta(days=7)).strftime('%Y-%m-%d')
        today = (date.today()).strftime('%Y-%m-%d')
        next_week = (monday + timedelta(days=7)).strftime('%Y-%m-%d')
        context['title'] = 'Training history for %s' % monday.strftime('%Y-%m-%d')
        context['site_header'] = 'Alyx'
        context['prev_url'] = reverse('training', args=[previous_week])
        context['today_url'] = reverse('training', args=[today])
        context['next_url'] = reverse('training', args=[next_week])
        context['wds'] = [monday + timedelta(days=n) for n in range(7)]
        return context

    def get_queryset(self):
        yield from training_days(reqdate=self.monday)


def weighing_plot(request, subject_id=None):
    if not request.user.is_authenticated:
        return HttpResponse('')
    if subject_id in (None, 'None'):
        return HttpResponse('')
    wc = water_control(Subject.objects.get(pk=subject_id))
    return wc.plot()


class ProcedureTypeList(generics.ListCreateAPIView):
    queryset = ProcedureType.objects.all()
    permission_classes = rest_permission_classes()
    serializer_class = ProcedureTypeSerializer
    lookup_field = 'name'


class SessionFilter(BaseActionFilter):
    dataset_types = django_filters.CharFilter(
        field_name='dataset_types', method='filter_dataset_types')
    datasets = django_filters.CharFilter(field_name='datasets', method='filter_datasets')
    dataset_qc_lte = django_filters.CharFilter(
        field_name='dataset_qc', method='filter_dataset_qc_lte')
    performance_gte = django_filters.NumberFilter(field_name='performance',
                                                  method='filter_performance_gte')
    performance_lte = django_filters.NumberFilter(field_name='performance',
                                                  method='filter_performance_lte')

    type = django_filters.CharFilter(field_name='type', lookup_expr='iexact')
    task_protocol = django_filters.CharFilter(field_name='task_protocol', lookup_expr='icontains')
    qc = django_filters.CharFilter(method='enum_field_filter')
    extended_qc = django_filters.CharFilter(field_name='extended_qc', method='filter_extended_qc')
    procedures = django_filters.CharFilter(field_name='procedures__name', lookup_expr='icontains')
    projects = django_filters.CharFilter(field_name='projects__name', lookup_expr='icontains')
    # below is an alias to keep compatibility after moving project FK field to projects M2M
    project = django_filters.CharFilter(field_name='projects__name', lookup_expr='icontains')
    # brain region filters
    atlas_name = django_filters.CharFilter(field_name='name__icontains', method='atlas')
    atlas_acronym = django_filters.CharFilter(field_name='acronym__iexact', method='atlas')
    atlas_id = django_filters.NumberFilter(field_name='pk', method='atlas')
    histology = django_filters.BooleanFilter(field_name='histology', method='has_histology')
    tag = django_filters.CharFilter(field_name='tag', method='filter_tag')

    def filter_tag(self, queryset, name, value):
        """
        returns sessions that contain datasets tagged as
        """
        queryset = queryset.filter(
            data_dataset_session_related__tags__name__icontains=value).distinct()
        return queryset

    def atlas(self, queryset, name, value):
        """
        returns sessions containing at least one channel or field of view in the given brain
        region.

        Uses hierarchical tree search
        """
        return _filter_qs_with_brain_regions(queryset, name, value)

    def has_histology(self, queryset, name, value):
        """returns sessions whose subjects have an histology session available"""
        if value:
            fcn_query = queryset.filter
        else:
            fcn_query = queryset.exclude
        return fcn_query(subject__actions_sessions__procedures__name='Histology').distinct()

    def filter_extended_qc(self, queryset, name, value):
        return base_json_filter('extended_qc', queryset, name, value)

    def filter_dataset_types(self, queryset, _, value):
        dtypes = value.split(',')
        queryset = queryset.filter(data_dataset_session_related__dataset_type__name__in=dtypes)
        queryset = queryset.annotate(
            dtypes_count=Count('data_dataset_session_related__dataset_type', distinct=True))
        queryset = queryset.filter(dtypes_count__gte=len(dtypes))
        return queryset

    def filter_datasets(self, queryset, _, value):
        # Note this may later be modified to include collections, e.g. ?datasets=alf/obj.attr.ext
        qc = QC.validate(self.request.query_params.get('dataset_qc_lte', QC.FAIL))
        dataset_names = value.split(',')
        queryset = queryset.filter(data_dataset_session_related__name__in=dataset_names)
        dsets = Dataset.objects.filter(
            session__in=queryset,
            name__in=dataset_names,
            qc__lte=qc,
        ).annotate(
            exists=ExpressionWrapper(
                Q(
                    file_records__data_repository__globus_is_personal=False,
                    file_records__exists=True
                ),
                output_field=BooleanField()
            )
        ).filter(exists__gte=1)
        sessions = dsets.values_list('session', flat=True).distinct().annotate(
            dset_count=Count('name', distinct=True)).filter(dset_count__gte=len(dataset_names))
        queryset = queryset.filter(pk__in=sessions.values_list('session')).distinct()
        return queryset

    def filter_dataset_qc_lte(self, queryset, _, value):
        # If filtering on datasets too, `filter_datasets` handles both QC and Datasets
        if 'datasets' in self.request.query_params:
            return queryset
        qc = QC.validate(value)
        queryset = queryset.filter(data_dataset_session_related__qc__lte=qc)
        return queryset

    def filter_performance_gte(self, queryset, name, perf):
        queryset = queryset.exclude(n_trials__isnull=True)
        pf = ExpressionWrapper(100 * F('n_correct_trials') / F('n_trials'),
                               output_field=FloatField())
        queryset = queryset.annotate(performance=pf)
        return queryset.filter(performance__gte=float(perf))

    def filter_performance_lte(self, queryset, name, perf):
        queryset = queryset.exclude(n_trials__isnull=True)
        pf = ExpressionWrapper(100 * F('n_correct_trials') / F('n_trials'),
                               output_field=FloatField())
        queryset = queryset.annotate(performance=pf)
        return queryset.filter(performance__lte=float(perf))

    class Meta(BaseActionFilter.Meta):
        model = Session


class WeighingFilter(BaseActionFilter):
    class Meta(BaseActionFilter.Meta):
        model = Weighing


class WaterAdministrationFilter(BaseActionFilter):
    class Meta(BaseActionFilter.Meta):
        model = WaterAdministration


class SessionAPIList(generics.ListCreateAPIView):
    """
        get: **FILTERS**

    -   **subject**: subject nickname `/sessions?subject=Algernon`
    -   **dataset_types**: dataset type(s) `/sessions?dataset_types=trials.table,camera.times`
    -   **datasets**: dataset name(s) `/sessions?datasets=_ibl_leftCamera.times.npy`
    -   **dataset_qc_lte**: dataset QC values less than or equal to this
        `/sessions?dataset_qc_lte=WARNING`
    -   **number**: session number
    -   **users**: experimenters (exact)
    -   **date_range**: date `/sessions?date_range=2020-01-12,2020-01-16`
    -   **lab**: lab name (exact)
    -   **task_protocol** (icontains)
    -   **location**: location name (icontains)
    -   **projects**: project name (icontains)
    -   **json**: queries on json fields, for example here `tutu`
        -   exact/equal lookup: `/sessions?extended_qc=tutu,True`,
        -   gte lookup: `/sessions/?extended_qc=tutu__gte,0.5`,
    -   **extended_qc** queries on json fields, for example here `qc_bool` and `qc_pct`,
        values and fields come by pairs, using semi-colon as a separator
        -   exact/equal lookup: `/sessions?extended_qc=qc_bool;True`,
        -   gte lookup: `/sessions/?extended_qc=qc_pct__gte;0.5`,
        -   chained lookups: `/sessions/?extended_qc=qc_pct__gte;0.5;qc_bool;True`,
    -   **performance_gte**, **performance_lte**: percentage of successful trials gte/lte
    -   **brain_region**: returns a session if any channel name icontains the value:
        `/sessions?brain_region=visual cortex`
    -   **atlas_acronym**: returns a session if any of its channels name exactly matches the value
        `/sessions?atlas_acronym=SSp-m4`, cf Allen CCFv2017
    -   **atlas_id**: returns a session if any of its channels id matches the provided value:
        `/sessions?atlas_id=950`, cf Allen CCFv2017
    -   **qc**: returns sessions for which the qc statuses matches provided string. Should be
    one of CRITICAL, ERROR, WARNING, NOT_SET, PASS
        `/sessions?qc=CRITICAL`
    -   **histology**: returns sessions for which the subject has an histology session:
        `/sessions?histology=True`
    -   **django**: generic filter allowing lookups (same syntax as json filter)
        `/sessions?django=projects__name__icontains,matlab`
        filters sessions that have matlab in the project names
        `/sessions?django=~projects__name__icontains,matlab`
        does the exclusive set: filters sessions that do not have matlab in the project names

    [===> session model reference](/admin/doc/models/actions.session)
    """
    queryset = Session.objects.all()
    queryset = SessionListSerializer.setup_eager_loading(queryset)
    permission_classes = rest_permission_classes()

    filterset_class = SessionFilter

    def get_serializer_class(self):
        if not self.request:
            return SessionListSerializer
        if self.request.method == 'GET':
            return SessionListSerializer
        if self.request.method == 'POST':
            return SessionDetailSerializer


class SessionAPIDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Detail of one session
    """
    queryset = Session.objects.all().order_by('-start_time')
    queryset = SessionDetailSerializer.setup_eager_loading(queryset)
    serializer_class = SessionDetailSerializer
    permission_classes = rest_permission_classes()


class WeighingAPIListCreate(generics.ListCreateAPIView):
    """
    Lists or creates a new weighing.
    """
    permission_classes = rest_permission_classes()
    serializer_class = WeighingDetailSerializer
    queryset = Weighing.objects.all()
    queryset = WeighingDetailSerializer.setup_eager_loading(queryset)
    filterset_class = WeighingFilter


class WeighingAPIDetail(generics.RetrieveDestroyAPIView):
    """
    Allows viewing of full detail and deleting a weighing.
    """
    permission_classes = rest_permission_classes()
    serializer_class = WeighingDetailSerializer
    queryset = Weighing.objects.all()


class WaterTypeList(generics.ListCreateAPIView):
    queryset = WaterType.objects.all()
    serializer_class = WaterTypeDetailSerializer
    permission_classes = rest_permission_classes()
    lookup_field = 'name'


class WaterAdministrationAPIListCreate(generics.ListCreateAPIView):
    """
    Lists or creates a new water administration.
    """
    permission_classes = rest_permission_classes()
    serializer_class = WaterAdministrationDetailSerializer
    queryset = WaterAdministration.objects.all()
    queryset = WaterAdministrationDetailSerializer.setup_eager_loading(queryset)
    filterset_class = WaterAdministrationFilter


class WaterAdministrationAPIDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Allows viewing of full detail and deleting a water administration.
    """
    permission_classes = rest_permission_classes()
    serializer_class = WaterAdministrationDetailSerializer
    queryset = WaterAdministration.objects.all()


class WaterRequirement(APIView):
    permission_classes = rest_permission_classes()

    def get(self, request, format=None, nickname=None):
        assert nickname
        start_date = request.query_params.get('start_date', None)
        end_date = request.query_params.get('end_date', None)
        subject = Subject.objects.get(nickname=nickname)
        records = subject.water_control.to_jsonable(start_date=start_date, end_date=end_date)
        date_str = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
        ref_iw = subject.water_control.reference_implant_weight_at(date_str)
        data = {'subject': nickname, 'implant_weight': ref_iw,
                'reference_weight_pct': subject.water_control.reference_weight_pct,
                'zscore_weight_pct': subject.water_control.zscore_weight_pct,
                'records': records}
        return Response(data)


class WaterRestrictionFilter(BaseActionFilter):
    class Meta(BaseActionFilter.Meta):
        model = WaterRestriction


class WaterRestrictionList(generics.ListAPIView):
    """
    Lists water restriction.
    """
    queryset = WaterRestriction.objects.all().order_by('-end_time', '-start_time')
    serializer_class = WaterRestrictionListSerializer
    permission_classes = rest_permission_classes()
    filterset_class = WaterRestrictionFilter


class LabLocationList(generics.ListAPIView):
    """
    Lists Lab Location
    """
    queryset = LabLocation.objects.all()
    serializer_class = LabLocationSerializer
    permission_classes = rest_permission_classes()


class LabLocationAPIDetail(generics.RetrieveUpdateAPIView):
    """
    Allows viewing of full detail and deleting a water administration.
    """
    permission_classes = rest_permission_classes()
    serializer_class = LabLocationSerializer
    queryset = LabLocation.objects.all()
    lookup_field = 'name'


class SurgeriesFilter(BaseActionFilter):
    procedure = django_filters.CharFilter(field_name='procedures__name', lookup_expr=('iexact'))

    class Meta(BaseActionFilter.Meta):
        model = Surgery


class SurgeriesList(generics.ListAPIView):
    """
        get: **FILTERS**

    -   **subject**: subject nickname `/sessions?subject=Algernon`
    [===> session model reference](/admin/doc/models/actions.surgery)
    """
    queryset = Surgery.objects.all().order_by('-start_time')
    serializer_class = SurgerySerializer
    permission_classes = rest_permission_classes()
    filterset_class = SurgeriesFilter


class SurgeriesAPIDetail(generics.RetrieveUpdateAPIView):
    """
    Allows viewing of full detail and update of a surgery.
    """
    permission_classes = rest_permission_classes()
    serializer_class = SurgerySerializer
    queryset = Surgery.objects.all()
