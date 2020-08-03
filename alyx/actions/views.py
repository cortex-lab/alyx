from datetime import timedelta, date
import itertools
from operator import itemgetter

from django.contrib.postgres.fields import JSONField
from django.db.models import Count, Q, F, ExpressionWrapper, FloatField
from django.db.models.deletion import Collector
from django_filters.rest_framework.filters import CharFilter
from django.http import HttpResponse
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.generic.list import ListView

import django_filters
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from alyx.base import base_json_filter, BaseFilterSet
from subjects.models import Subject
from .water_control import water_control, to_date
from .models import (
    BaseAction, Session, WaterAdministration, WaterRestriction,
    Weighing, WaterType, LabLocation)
from .serializers import (LabLocationSerializer,
                          SessionListSerializer,
                          SessionDetailSerializer,
                          WaterAdministrationDetailSerializer,
                          WeighingDetailSerializer,
                          WaterTypeDetailSerializer,
                          WaterRestrictionListSerializer,
                          )


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


class SessionFilter(BaseFilterSet):
    subject = django_filters.CharFilter(field_name='subject__nickname', lookup_expr=('iexact'))
    dataset_types = django_filters.CharFilter(field_name='dataset_types',
                                              method='filter_dataset_types')
    performance_gte = django_filters.NumberFilter(field_name='performance',
                                                  method=('filter_performance_gte'))
    performance_lte = django_filters.NumberFilter(field_name='performance',
                                                  method=('filter_performance_lte'))
    users = django_filters.CharFilter(field_name='users__username', method=('filter_users'))
    date_range = django_filters.CharFilter(field_name='date_range', method=('filter_date_range'))
    type = django_filters.CharFilter(field_name='type', lookup_expr=('iexact'))
    lab = django_filters.CharFilter(field_name='lab__name', lookup_expr=('iexact'))
    task_protocol = django_filters.CharFilter(field_name='task_protocol',
                                              lookup_expr=('icontains'))
    qc = django_filters.CharFilter(method='enum_field_filter')
    json = django_filters.CharFilter(field_name='json', method=('filter_json'))
    location = django_filters.CharFilter(field_name='location__name', lookup_expr=('icontains'))
    extended_qc = django_filters.CharFilter(field_name='extended_qc',
                                            method=('filter_extended_qc'))
    project = django_filters.CharFilter(field_name='project__name', lookup_expr=('icontains'))
    # brain region filters
    atlas_name = django_filters.CharFilter(field_name='name__icontains', method='atlas')
    atlas_acronym = django_filters.CharFilter(field_name='acronym__iexact', method='atlas')
    atlas_id = django_filters.NumberFilter(field_name='pk', method='atlas')
    histology = django_filters.BooleanFilter(field_name='histology', method='has_histology')

    def atlas(self, queryset, name, value):
        """
        returns sessions containing at least one channel in the given brain region.
        Hierarchical tree search"
        """
        from experiments.models import BrainRegion
        brs = BrainRegion.objects.filter(**{name: value}).get_descendants(include_self=True)
        return queryset.filter(
            probe_insertion__trajectory_estimate__channels__brain_region__in=brs).distinct()

    def has_histology(self, queryset, name, value):
        """returns sessions whose subjects have an histology session available"""
        if value:
            fcn_query = queryset.filter
        else:
            fcn_query = queryset.exclude
        return fcn_query(subject__actions_sessions__procedures__name='Histology').distinct()

    def filter_json(self, queryset, name, value):
        return base_json_filter('json', queryset, name, value)

    def filter_extended_qc(self, queryset, name, value):
        return base_json_filter('extended_qc', queryset, name, value)

    def filter_users(self, queryset, name, value):
        users = value.split(',')
        queryset = queryset.filter(users__username__in=users)
        queryset = queryset.annotate(
            users_count=Count('users__username'))
        queryset = queryset.filter(users_count__gte=len(users))
        return queryset

    def filter_date_range(self, queryset, name, value):
        drange = value.split(',')
        queryset = queryset.filter(
            Q(start_time__date__gte=drange[0]),
            Q(start_time__date__lte=drange[1]),
        )
        return queryset

    def filter_dataset_types(self, queryset, name, value):
        dtypes = value.split(',')
        queryset = queryset.filter(data_dataset_session_related__dataset_type__name__in=dtypes)
        queryset = queryset.annotate(
            dtypes_count=Count('data_dataset_session_related__dataset_type', distinct=True))
        queryset = queryset.filter(dtypes_count__gte=len(dtypes))
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

    class Meta:
        model = Session
        exclude = []
        filter_overrides = {
            JSONField: {
                'filter_class': CharFilter,
            },
        }


class WeighingFilter(BaseFilterSet):
    nickname = django_filters.CharFilter(field_name='subject__nickname', lookup_expr='iexact')

    class Meta:
        model = Weighing
        exclude = ['json']


class WaterAdministrationFilter(BaseFilterSet):
    nickname = django_filters.CharFilter(field_name='subject__nickname', lookup_expr='iexact')

    class Meta:
        model = WaterAdministration
        exclude = ['json']


class SessionAPIList(generics.ListCreateAPIView):
    """
        get: **FILTERS**

    -   **subject**: subject nickname `/sessions?subject=Algernon`
    -   **dataset_types**: dataset type
    -   **number**: session number
    -   **users**: experimenters (exact)
    -   **date_range**: date `/sessions?date_range=2020-01-12,2020-01-16`
    -   **lab**: lab name (exact)
    -   **task_protocol** (icontains)
    -   **location**: location name (icontains)
    -   **project**: project name (icontains)
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
        `/sessions?brain_region=vis`
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
        `/sessions?django=project__name__icontains,matlab
        filters sessions that have matlab in the project name
        `/sessions?django=~project__name__icontains,matlab
        does the exclusive set: filters sessions that do not have matlab in the project name
    """
    queryset = Session.objects.all()
    queryset = SessionListSerializer.setup_eager_loading(queryset)
    permission_classes = (permissions.IsAuthenticated,)
    filter_class = SessionFilter

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
    permission_classes = (permissions.IsAuthenticated,)


class WeighingAPIListCreate(generics.ListCreateAPIView):
    """
    Lists or creates a new weighing.
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = WeighingDetailSerializer
    queryset = Weighing.objects.all()
    queryset = WeighingDetailSerializer.setup_eager_loading(queryset)
    filter_class = WeighingFilter


class WeighingAPIDetail(generics.RetrieveDestroyAPIView):
    """
    Allows viewing of full detail and deleting a weighing.
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = WeighingDetailSerializer
    queryset = Weighing.objects.all()


class WaterTypeList(generics.ListCreateAPIView):
    queryset = WaterType.objects.all()
    serializer_class = WaterTypeDetailSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'name'


class WaterAdministrationAPIListCreate(generics.ListCreateAPIView):
    """
    Lists or creates a new water administration.
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = WaterAdministrationDetailSerializer
    queryset = WaterAdministration.objects.all()
    queryset = WaterAdministrationDetailSerializer.setup_eager_loading(queryset)
    filter_class = WaterAdministrationFilter


class WaterAdministrationAPIDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Allows viewing of full detail and deleting a water administration.
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = WaterAdministrationDetailSerializer
    queryset = WaterAdministration.objects.all()


def _merge_lists_dicts(la, lb, key):
    lst = sorted(itertools.chain(la, lb), key=itemgetter(key))
    out = []
    for k, v in itertools.groupby(lst, key=itemgetter(key)):
        d = {}
        for dct in v:
            d.update(dct)
        out.append(d)
    return out


class WaterRequirement(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, format=None, nickname=None):
        assert nickname
        start_date = request.query_params.get('start_date', None)
        end_date = request.query_params.get('end_date', None)
        subject = Subject.objects.get(nickname=nickname)
        records = subject.water_control.to_jsonable(start_date=start_date, end_date=end_date)
        data = {'subject': nickname, 'implant_weight': subject.implant_weight, 'records': records}
        return Response(data)


class WaterRestrictionFilter(BaseFilterSet):
    subject = django_filters.CharFilter(field_name='subject__nickname', lookup_expr='iexact')

    class Meta:
        model = WaterRestriction
        exclude = ['json']


class WaterRestrictionList(generics.ListAPIView):
    """
    Lists water restriction.
    """
    queryset = WaterRestriction.objects.all().order_by('-end_time', '-start_time')
    serializer_class = WaterRestrictionListSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_class = WaterRestrictionFilter


class LabLocationList(generics.ListAPIView):
    """
    Lists Lab Location
    """
    queryset = LabLocation.objects.all()
    serializer_class = LabLocationSerializer
    permission_classes = (permissions.IsAuthenticated,)


class LabLocationAPIDetails(generics.RetrieveUpdateAPIView):
    """
    Allows viewing of full detail and deleting a water administration.
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = LabLocationSerializer
    queryset = LabLocation.objects.all()
    lookup_field = 'name'
