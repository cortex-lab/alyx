from collections import defaultdict
import itertools
from operator import itemgetter

import django_filters
from django_filters.rest_framework import FilterSet
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

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


class SessionFilter(FilterSet):
    subject = django_filters.CharFilter(name='subject__nickname')
    start_date = django_filters.DateFilter(name='start_time__date', lookup_expr=('exact'))
    end_date = django_filters.DateFilter(name='end_time__date', lookup_expr=('exact'))
    starts_before = django_filters.DateFilter(name='start_time', lookup_expr=('lte'))
    starts_after = django_filters.DateFilter(name='start_time', lookup_expr=('gte'))
    ends_before = django_filters.DateFilter(name='start_time', lookup_expr=('lte'))
    ends_after = django_filters.DateFilter(name='start_time', lookup_expr=('gte'))

    class Meta:
        model = Session
        exclude = ['json']


class SessionAPIList(generics.ListCreateAPIView):
    """
    List and create sessions - view in summary form
    """
    queryset = Session.objects.all()
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
            was_out[date][name] += wa['administered']
            was_out[date]['date'] = date
        was_out = [was_out[d] for d in sorted(was_out.keys())]
        for wa in was_out:
            wa['water_expected'] = water.water_requirement_total(subject, wa['date'])
            wa['weight_expected'] = water.expected_weighing(subject, wa['date'])
        records = _merge_lists_dicts(wl, was_out, 'date')
        data = {'subject': nickname, 'records': records}
        return Response(data)
