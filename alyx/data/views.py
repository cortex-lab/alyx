from rest_framework import generics, permissions, viewsets
import django_filters
from django_filters.rest_framework import FilterSet

from .models import (DataRepositoryType,
                     DataRepository,
                     DataFormat,
                     DatasetType,
                     Dataset,
                     FileRecord,
                     Timescale,
                     )
from electrophysiology.models import ExtracellularRecording
from .serializers import (DataRepositoryTypeSerializer,
                          DataRepositoryDetailSerializer,
                          DataFormatSerializer,
                          DatasetTypeSerializer,
                          DatasetSerializer,
                          FileRecordSerializer,
                          TimescaleSerializer,
                          ExpMetadataDetailSerializer,
                          ExpMetadataSummarySerializer,
                          )


class DataRepositoryTypeViewSet(viewsets.ModelViewSet):
    """
    You can `list`, `create`, `retrieve`,`update` and `destroy` datasets.
    This API will probably change.
    """
    queryset = DataRepositoryType.objects.all()
    serializer_class = DataRepositoryTypeSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'name'


class DataRepositoryViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = DataRepositoryDetailSerializer
    queryset = DataRepository.objects.all()
    lookup_field = 'name'


class DataFormatViewSet(viewsets.ModelViewSet):
    """
    You can `list`, `create`, `retrieve`,`update` and `destroy` datasets.
    This API will probably change.
    """
    queryset = DataFormat.objects.all()
    serializer_class = DataFormatSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'name'


class DatasetTypeViewSet(viewsets.ModelViewSet):
    """
    You can `list`, `create`, `retrieve`,`update` and `destroy` datasets.
    This API will probably change.
    """
    queryset = DatasetType.objects.all()
    serializer_class = DatasetTypeSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'name'


class DatasetFilter(FilterSet):
    subject = django_filters.CharFilter(name='session__subject__nickname')
    date = django_filters.CharFilter(name='created_datetime__date')
    created_by = django_filters.CharFilter(name='created_by__username')
    dataset_type = django_filters.CharFilter(name='dataset_type__name')
    experiment_number = django_filters.CharFilter(name='session__number')

    class Meta:
        model = Dataset
        exclude = ['json']


class DatasetViewSet(viewsets.ModelViewSet):
    """
    You can `list`, `create`, `retrieve`,`update` and `destroy` datasets.
    This API will probably change.
    """
    queryset = Dataset.objects.all()
    serializer_class = DatasetSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_class = DatasetFilter


class FileRecordViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = FileRecordSerializer
    queryset = FileRecord.objects.all()
    filter_fields = ('exists', 'dataset')


class TimescaleViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = TimescaleSerializer
    queryset = Timescale.objects.all()


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
