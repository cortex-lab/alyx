from django.shortcuts import render
from rest_framework import generics, permissions, renderers, viewsets
from .models import *

from .serializers import DatasetSerializer, FileRecordSerializer

class DatasetViewSet(viewsets.ModelViewSet):
    """
    You can `list`, `create`, `retrieve`,`update` and `destroy` datasets.
    This API will probably change.
    """
    queryset = Dataset.objects.all()
    serializer_class = DatasetSerializer
    permission_classes = (permissions.IsAuthenticated,)

class FileRecordViewSet(viewsets.ModelViewSet):
    """
    You can `list`, `create`, `retrieve`,`update` and `destroy` datasets.
    This API will probably change.
    """
    queryset = FileRecord.objects.all()
    serializer_class = FileRecordSerializer
    permission_classes = (permissions.IsAuthenticated,)