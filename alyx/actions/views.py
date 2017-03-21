from rest_framework import generics, permissions

from .models import Session, WaterAdministration, Weighing
from .serializers import (SessionListSerializer,
                          SessionDetailSerializer,
                          WaterAdministrationListSerializer,
                          WaterAdministrationDetailSerializer,
                          WeighingListSerializer,
                          WeighingDetailSerializer,
                          )

import django_filters
from django_filters.rest_framework import FilterSet

class SessionFilter(FilterSet):
    subject = django_filters.CharFilter(name='subject__nickname')
    start_date = django_filters.DateFilter(name='start_time__date',lookup_expr=('exact'))
    end_date = django_filters.DateFilter(name='end_time__date',lookup_expr=('exact'))
    starts_before = django_filters.DateFilter(name='start_time',lookup_expr=('lte'))
    starts_after = django_filters.DateFilter(name='start_time',lookup_expr=('gte'))
    ends_before = django_filters.DateFilter(name='start_time',lookup_expr=('lte'))
    ends_after = django_filters.DateFilter(name='start_time',lookup_expr=('gte'))

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
