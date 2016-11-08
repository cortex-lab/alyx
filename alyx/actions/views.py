import uuid
from django.shortcuts import render
from subjects.models import Subject
from rest_framework import generics, permissions, renderers, viewsets

from .models import *
from .serializers import *

class ExperimentViewSet(viewsets.ModelViewSet):
    """
    You can `list`, `create`, `retrieve`,`update` and `destroy` actions.
    This API will probably change.
    """
    queryset = Experiment.objects.all()
    serializer_class = ExperimentSerializer
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


class WeighingAPIDetail(generics.RetrieveDestroyAPIView):
    """
    Allows viewing of full detail and deleting a weighing.
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = WeighingDetailSerializer
    queryset = Weighing.objects.all()

    # def perform_create(self, serializer):
    #     # Lookup UUID of subject's nickname
    #     subject = Subject.objects.get(nickname=self.kwargs['nickname'])
    #     serializer.save(subject_id=subject.id)

class WaterAdministrationAPIList(generics.ListCreateAPIView):
    """
    Lists all water administrations to a given subject, sorted by time/date.
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = WaterAdministrationSerializer

    def get_queryset(self):
        queryset = WaterAdministration.objects.all()
        queryset = queryset.filter(subject__nickname=self.kwargs['nickname']).order_by('start_date_time')
        return queryset

    def perform_create(self, serializer):
        # Lookup UUID of subject's nickname
        subject = Subject.objects.get(nickname=self.kwargs['nickname'])
        serializer.save(subject_id=subject.id)