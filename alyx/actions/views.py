from collections import defaultdict
from datetime import timedelta, datetime
import itertools
from operator import itemgetter

from django.db.models import Sum, Count, Q, F, ExpressionWrapper, FloatField
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.views.generic.list import ListView

import django_filters
from django_filters.rest_framework import FilterSet
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from alyx.base import Bunch
from subjects.models import Subject
from . import water
from .models import Session, WaterAdministration, Weighing, WaterType
from .serializers import (SessionListSerializer,
                          SessionDetailSerializer,
                          WaterAdministrationDetailSerializer,
                          WeighingDetailSerializer,
                          WaterTypeDetailSerializer,
                          )


def date_range(start_date, end_date):
    for n in range(int((end_date - start_date).days) + 1):
        yield (start_date + timedelta(n))


class WaterHistoryListView(ListView):
    template_name = 'water_history.html'

    def get_context_data(self, **kwargs):
        context = super(WaterHistoryListView, self).get_context_data(**kwargs)
        subject = Subject.objects.get(pk=self.kwargs['subject_id'])
        context['title'] = 'Water history of %s' % subject.nickname
        context['site_header'] = 'Alyx'
        url = reverse('weighing-plot', kwargs={'subject_id': subject.id})
        context['plot_url'] = url
        return context

    def get_queryset(self):
        """
        date, weight, 80% weight, weight percentage, water, hydrogel, total, min water, excess
        """
        subject = Subject.objects.get(pk=self.kwargs['subject_id'])
        weighings = Weighing.objects.filter(subject=subject,
                                            date_time__isnull=False).order_by('date_time')
        if not weighings:
            return []
        weighings = list(weighings)
        start, end = weighings[0].date_time.date(), datetime.now().date()
        weighings = {w.date_time.date(): w.weight for w in weighings}

        # Sum all water administrations for any given day.
        was = {}
        was[True] = (WaterAdministration.objects.filter(
            subject=subject, water_type__name='Hydrogel').
            annotate(date=TruncDate('date_time')).values('date').
            annotate(sum=Sum('water_administered')).order_by('date')
        )
        was[False] = (WaterAdministration.objects.filter(
            subject=subject).exclude(water_type__name='Hydrogel').
            annotate(date=TruncDate('date_time')).values('date').
            annotate(sum=Sum('water_administered')).order_by('date')
        )

        # Do it for hydrogel and no hydrogel.
        for boo in (False, True):
            was[boo] = {w['date']: w['sum'] for w in was[boo]}

        out = []
        for date in list(date_range(start, end))[::-1]:
            b = Bunch()
            b.date = date
            rw = water.reference_weighing(subject, date=date)
            b.required = water.water_requirement_total(subject, date=date)
            b.weight = weighings.get(date, 0.)
            b.expected = water.expected_weighing(subject, date=date, rw=rw)
            b.expected_80 = .8 * b.expected
            b.percentage = b.weight / b.expected * 100 if b.expected else None
            b.water = was[False].get(date, 0.)
            b.hydrogel = was[True].get(date, 0.)
            b.total = b.water + b.hydrogel
            b.excess = b.total - b.required
            if b.weight == 0.:
                b.weight = None
            if b.percentage == 0.:
                b.percentage = None
            out.append(b)
        return out


class SessionFilter(FilterSet):
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
            Q(start_time__date__gte=drange[0]) | Q(end_time__date__gte=drange[0]),
            Q(start_time__date__lte=drange[1]) | Q(end_time__date__lte=drange[1]),
        )
        return queryset

    def filter_dataset_types(self, queryset, name, value):
        dtypes = value.split(',')
        queryset = queryset.filter(data_dataset_session_related__dataset_type__name__in=dtypes)
        queryset = queryset.annotate(
            dtypes_count=Count('data_dataset_session_related__dataset_type'))
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
        exclude = ['json']


class WeighingFilter(FilterSet):
    nickname = django_filters.CharFilter(field_name='subject__nickname', lookup_expr='iexact')

    class Meta:
        model = Weighing
        exclude = ['json']


class WaterAdministrationFilter(FilterSet):
    nickname = django_filters.CharFilter(field_name='subject__nickname', lookup_expr='iexact')

    class Meta:
        model = WaterAdministration
        exclude = ['json']


class SessionAPIList(generics.ListCreateAPIView):
    """
    List and create sessions - view in summary form
    """
    queryset = Session.objects.all()
    queryset = SessionListSerializer.setup_eager_loading(queryset)
    serializer_class = SessionListSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_class = SessionFilter


class SessionAPIDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Detail of one session
    """
    queryset = Session.objects.all()
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


class WaterAdministrationAPIDetail(generics.RetrieveDestroyAPIView):
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
        ws = Weighing.objects.filter(subject__nickname=nickname,
                                     date_time__date__gte=start_date,
                                     date_time__date__lte=end_date,
                                     )
        was = WaterAdministration.objects.filter(subject__nickname=nickname,
                                                 date_time__date__gte=start_date,
                                                 date_time__date__lte=end_date,
                                                 ).order_by('date_time', 'water_type__name')
        wl = [{'date': w.date_time.date(),
               'weight_measured': w.weight or None,
               } for w in ws]
        was = [{'date': wa.date_time.date(),
                'hydrogel': wa.hydrogel,
                'administered': wa.water_administered or None,
                } for wa in was]
        was_out = {}
        # Group by date and hydrogel and make the sum of the water administered.
        for wa in was:
            date = wa['date']
            if date not in was_out:
                was_out[date] = defaultdict(float)
            h = wa['hydrogel']
            name = 'hydrogel_given' if h else 'water_given'
            was_out[date][name] += (wa['administered'] or 0.)
            was_out[date]['date'] = date
        was_out = [was_out[d] for d in sorted(was_out.keys())]
        records = _merge_lists_dicts(wl, was_out, 'date')
        for r in records:
            r['water_expected'] = water.water_requirement_total(subject, r['date'])
            r['weight_expected'] = water.expected_weighing(subject, r['date'])
            if 'water_given' not in r:
                r['water_given'] = 0.
            if 'hydrogel_given' not in r:
                r['hydrogel_given'] = 0.
        data = {'subject': nickname, 'implant_weight': subject.implant_weight, 'records': records}
        return Response(data)
