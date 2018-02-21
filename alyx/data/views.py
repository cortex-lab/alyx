import os.path as op
import re

from rest_framework import generics, permissions, viewsets, mixins
from rest_framework.response import Response
import django_filters
from django_filters.rest_framework import FilterSet
from django.db.models.functions import Length

from .models import (DataRepositoryType,
                     DataRepository,
                     DataFormat,
                     DatasetType,
                     Dataset,
                     FileRecord,
                     Timescale,
                     _get_or_create_session,
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
from subjects.models import Subject
from . import globus


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


def _get_data_type_format(filename):
    """Return the DatasetType and DataFormat associated to an ALF filename."""

    dataset_type = None
    for dt in (DatasetType.objects.filter(alf_filename__isnull=False).
               order_by(Length('alf_filename').desc())):
        if not dt.alf_filename.strip():
            continue
        reg = dt.alf_filename.replace('.', r'\.').replace('*', r'[^\.]+')
        if re.match(reg, filename):
            dataset_type = dt
            break

    data_format = None
    for df in DataFormat.objects.filter(alf_filename__isnull=False):
        reg = df.alf_filename.replace('.', r'\.').replace('*', r'[^\.]+')
        if not df.alf_filename.strip():
            continue
        if re.match(reg, filename):
            data_format = df
            break

    return dataset_type, data_format


class RegisterFileViewSet(mixins.CreateModelMixin,
                          viewsets.GenericViewSet):
    def create(self, request):
        user = request.user
        number = request.data.get('session_number', None)
        date = request.data.get('date', None)

        relative_path = request.data.get('relative_path', None)
        assert relative_path
        filename = op.basename(relative_path)

        subject = request.data.get('subject', None)
        subject = Subject.objects.get(nickname=subject)

        session = _get_or_create_session(subject=subject, date=date, number=number, user=user)

        dataset_type, data_format = _get_data_type_format(filename)

        # Create the dataset.
        dataset = Dataset.objects.create(
            name=filename, session=session, created_by=user,
            dataset_type=dataset_type, data_format=data_format)

        # List of data repositories associated to the subject's projects.
        repositories = set()
        for project in subject.projects.all():
            repositories.update(project.repositories.all())

        # Create one file record per repository.
        file_records = []
        for repo in repositories:
            fr = FileRecord.objects.create(
                dataset=dataset, data_repository=repo, relative_path=relative_path, exists=False)
            file_records.append({
                'data_repository': fr.data_repository.name,
                'relative_path': fr.relative_path,
                'exists': fr.exists,
            })

        # Sync files and launch transfer tasks.
        globus.update_file_exists(dataset)
        for t in globus.transfers_required(dataset):
            globus.start_globus_transfer(t['source_file_record'], t['destination_file_record'],
                                         dry_run=True)

        # Note the use of `get_queryset()` instead of `self.queryset`
        return Response({
            'id': dataset.pk,
            'name': dataset.name,
            'session': getattr(session, 'pk', ''),
            'created_by': user.username,
            'created_datetime': dataset.created_datetime,
            'dataset_type': getattr(dataset_type, 'name', ''),
            'data_format': getattr(data_format, 'name', ''),
            'file_records': file_records,
        })


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
