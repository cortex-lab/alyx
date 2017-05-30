from rest_framework import generics, permissions, viewsets
from .models import Dataset, FileRecord, DataRepository
from electrophysiology.models import ExtracellularRecording

from .serializers import (DatasetSerializer,
                          DataRepositoryDetailSerializer,
                          DatasetFileRecordDetailSerializer,
                          FileRecordSerializer,
                          ExpMetadataDetailSerializer,
                          ExpMetadataSummarySerializer,
                          )


class DatasetViewSet(viewsets.ModelViewSet):
    """
    You can `list`, `create`, `retrieve`,`update` and `destroy` datasets.
    This API will probably change.
    """
    queryset = Dataset.objects.all()
    serializer_class = DatasetSerializer
    permission_classes = (permissions.IsAuthenticated,)


class DataRepositoryDetail(generics.RetrieveAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = DataRepositoryDetailSerializer
    queryset = DataRepository.objects.all()
    lookup_field = 'name'


class DatasetFileRecordDetail(generics.CreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = DatasetFileRecordDetailSerializer
    queryset = FileRecord.objects.all()


class FileRecordViewSet(viewsets.ModelViewSet):
    """
    You can `list`, `create`, `retrieve`,`update` and `destroy` datasets.
    This API will probably change.
    """
    queryset = FileRecord.objects.all()
    serializer_class = FileRecordSerializer
    permission_classes = (permissions.IsAuthenticated,)


class ExpMetadataList(generics.ListCreateAPIView):
    """
    Lists experimental metadata classes. For now just supports ExtracellularRecording
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ExpMetadataSummarySerializer
    queryset = ExtracellularRecording.objects.all()


class ExpMetadataDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Lists experimental metadata classes. For now just supports ExtracellularRecording
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ExpMetadataDetailSerializer
    queryset = ExtracellularRecording.objects.all()
