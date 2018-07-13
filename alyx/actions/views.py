from collections import defaultdict
from datetime import timedelta
import itertools
from operator import itemgetter

from django.db.models import Sum, Count
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
from .models import Session, WaterAdministration, Weighing
from .serializers import (SessionListSerializer,
                          SessionDetailSerializer,
                          WaterAdministrationListSerializer,
                          WaterAdministrationDetailSerializer,
                          WeighingListSerializer,
                          WeighingDetailSerializer,
                          )


def date_range(start_date, end_date):
    for n in range(int((end_date - start_date).days) + 1):
        yield (start_date + timedelta(n)).date()


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
        start, end = weighings[0].date_time, weighings[-1].date_time
        weighings = {w.date_time.date(): w.weight for w in weighings}

        # Sum all water administrations for any given day.
        was = {boo: WaterAdministration.objects.filter(subject=subject, hydrogel=boo).
               annotate(date=TruncDate('date_time')).values('date').
               annotate(sum=Sum('water_administered')).order_by('date')
               for boo in (False, True)
               }
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
    subject = django_filters.CharFilter('subject__nickname')
    start_date = django_filters.CharFilter('start_time__date', lookup_expr=('exact'))
    end_date = django_filters.CharFilter('end_time__date', lookup_expr=('exact'))
    starts_before = django_filters.CharFilter('start_time__date', lookup_expr=('lte'))
    starts_after = django_filters.CharFilter('start_time__date', lookup_expr=('gte'))
    ends_before = django_filters.CharFilter('start_time__date', lookup_expr=('lte'))
    ends_after = django_filters.CharFilter('start_time__date', lookup_expr=('gte'))
    dataset_types = django_filters.CharFilter('dataset_types', method='filter_dataset_types')

    def filter_dataset_types(self, queryset, name, value):
        types = value.split(',')
        queryset = queryset.filter(data_dataset_session_related__dataset_type__name__in=types)
        queryset = queryset.annotate(
            dtypes_count=Count('data_dataset_session_related__dataset_type'))
        queryset = queryset.filter(dtypes_count__gte=len(types))
        return queryset

    class Meta:
        model = Session
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
    serializer_class = SessionDetailSerializer
    permission_classes = (permissions.IsAuthenticated,)


class WeighingAPIList(generics.ListAPIView):
    """
    Lists all the subject weights, sorted by time/date.
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = WeighingListSerializer

    def get_queryset(self):
        queryset = Weighing.objects.all()
        queryset = queryset.filter(subject__nickname=self.kwargs[
                                   'nickname']).order_by('date_time')
        return queryset


class WeighingAPIListCreate(generics.ListCreateAPIView):
    """
    Lists or creates a new weighing.
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = WeighingDetailSerializer
    queryset = Weighing.objects.all()


class WeighingAPIDetail(generics.RetrieveDestroyAPIView):
    """
    Allows viewing of full detail and deleting a weighing.
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = WeighingDetailSerializer
    queryset = Weighing.objects.all()


class WaterAdministrationAPIList(generics.ListAPIView):
    """
    Lists all the subject water administrations, sorted by time/date.
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = WaterAdministrationListSerializer

    def get_queryset(self):
        queryset = Weighing.objects.all()
        queryset = queryset.filter(subject__nickname=self.kwargs[
                                   'nickname']).order_by('date_time')
        return queryset


class WaterAdministrationAPIListCreate(generics.ListCreateAPIView):
    """
    Lists or creates a new water administration.
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = WaterAdministrationDetailSerializer
    queryset = WaterAdministration.objects.all()


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
                                                 ).order_by('date_time', 'hydrogel')
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
