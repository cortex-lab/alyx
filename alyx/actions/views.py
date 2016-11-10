import uuid
from django.shortcuts import render
from subjects.models import Subject
from rest_framework import generics, permissions, renderers, viewsets

from .models import *
from .serializers import *

class ExperimentAPIList(generics.ListCreateAPIView):
    """
    List and create experiments - view in summary form
    """
    queryset = Experiment.objects.all()
    serializer_class = ExperimentListSerializer
    permission_classes = (permissions.IsAuthenticated,)

class ExperimentAPIDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Detail of one experiment
    """
    queryset = Experiment.objects.all()
    serializer_class = ExperimentDetailSerializer
    permission_classes = (permissions.IsAuthenticated,)

class WeighingAPIList(generics.ListAPIView):
    """
    Lists all the subject weights, sorted by time/date.
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = WeighingListSerializer

    def get_queryset(self):
        queryset = Weighing.objects.all()
        queryset = queryset.filter(subject__nickname=self.kwargs['nickname']).order_by('date_time')
        return queryset

class WeighingAPICreate(generics.CreateAPIView):
    """
    Creates a new weighing.
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
        queryset = queryset.filter(subject__nickname=self.kwargs['nickname']).order_by('date_time')
        return queryset

class WaterAdministrationAPICreate(generics.CreateAPIView):
    """
    Creates a new water administration.
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