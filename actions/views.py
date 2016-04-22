import uuid
from django.shortcuts import render
from subjects.models import Subject
from rest_framework import generics, permissions, renderers, viewsets
from .models import *

from .serializers import ActionSerializer, WeighingSerializer

class ActionViewSet(viewsets.ModelViewSet):
    """
    You can `list`, `create`, `retrieve`,`update` and `destroy` actions.
    This API will probably change.
    """
    queryset = Action.objects.all()
    serializer_class = ActionSerializer
    permission_classes = (permissions.IsAuthenticated,)

class WeighingAPIList(generics.ListCreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = WeighingSerializer

    def get_queryset(self):
        queryset = Weighing.objects.all()
        queryset = queryset.filter(subject__nickname=self.kwargs['nickname']).order_by('start_date_time')
        return queryset

    def perform_create(self, serializer):
        # Lookup UUID of subject's nickname
        subject = Subject.objects.get(nickname=self.kwargs['nickname'])
        serializer.save(subject_id=subject.id)