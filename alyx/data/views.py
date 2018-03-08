import logging
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
                          DataRepositorySerializer,
                          DataFormatSerializer,
                          DatasetTypeSerializer,
                          DatasetSerializer,
                          FileRecordSerializer,
                          TimescaleSerializer,
                          ExpMetadataDetailSerializer,
                          ExpMetadataSummarySerializer,
                          )
from subjects.models import Subject, Project

logger = logging.getLogger(__name__)


# DataRepositoryType
# ------------------------------------------------------------------------------------------------

class DataRepositoryTypeList(generics.ListCreateAPIView):
    queryset = DataRepositoryType.objects.all()
    serializer_class = DataRepositoryTypeSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'name'


class DataRepositoryTypeDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = DataRepositoryType.objects.all()
    serializer_class = DataRepositoryTypeSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'name'


# DataRepository
# ------------------------------------------------------------------------------------------------

class DataRepositoryList(generics.ListCreateAPIView):
    queryset = DataRepository.objects.all()
    serializer_class = DataRepositorySerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'name'


class DataRepositoryDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = DataRepository.objects.all()
    serializer_class = DataRepositorySerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'name'


# DataFormat
# ------------------------------------------------------------------------------------------------

class DataFormatList(generics.ListCreateAPIView):
    queryset = DataFormat.objects.all()
    serializer_class = DataFormatSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'name'


class DataFormatDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = DataFormat.objects.all()
    serializer_class = DataFormatSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'name'


# DatasetType
# ------------------------------------------------------------------------------------------------

class DatasetTypeList(generics.ListCreateAPIView):
    queryset = DatasetType.objects.all()
    serializer_class = DatasetTypeSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'name'


class DatasetTypeDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = DatasetType.objects.all()
    serializer_class = DatasetTypeSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'name'


# Dataset
# ------------------------------------------------------------------------------------------------

class DatasetFilter(FilterSet):
    subject = django_filters.CharFilter(name='session__subject__nickname')
    date = django_filters.CharFilter(name='created_datetime__date')
    created_by = django_filters.CharFilter(name='created_by__username')
    dataset_type = django_filters.CharFilter(name='dataset_type__name')
    experiment_number = django_filters.CharFilter(name='session__number')

    class Meta:
        model = Dataset
        exclude = ['json']


class DatasetList(generics.ListCreateAPIView):
    queryset = Dataset.objects.all()
    serializer_class = DatasetSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_class = DatasetFilter


class DatasetDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Dataset.objects.all()
    serializer_class = DatasetSerializer
    permission_classes = (permissions.IsAuthenticated,)


# FileRecord
# ------------------------------------------------------------------------------------------------

class FileRecordList(generics.ListCreateAPIView):
    queryset = FileRecord.objects.all()
    serializer_class = FileRecordSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_fields = ('exists', 'dataset')


class FileRecordDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = FileRecord.objects.all()
    serializer_class = FileRecordSerializer
    permission_classes = (permissions.IsAuthenticated,)


# Timescale
# ------------------------------------------------------------------------------------------------

class TimescaleList(generics.ListCreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = TimescaleSerializer
    queryset = Timescale.objects.all()


class TimescaleDetail(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = TimescaleSerializer
    queryset = Timescale.objects.all()


# ExpMetadata
# ------------------------------------------------------------------------------------------------

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


# Register file
# ------------------------------------------------------------------------------------------------

def _get_data_type_format(filename):
    """Return the DatasetType and DataFormat associated to an ALF filename."""

    dataset_type = None
    # NOTE: we sort by decreasing alf_filename length, so that longer (more specific) alf
    # filenames are chosen. For example, foo.bar.* has higher priority than foo.*.* because
    # its length is higher. For 1-character-long parts, we use the fact that * < any character
    # which is why we sort by decreasing alf_filename.
    for dt in (DatasetType.objects.filter(alf_filename__isnull=False).
               order_by(Length('alf_filename').desc(), '-alf_filename')):
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


def _get_repositories_for_projects(projects):
    # List of data repositories associated to the subject's projects.
    repositories = set()
    for project in projects:
        repositories.update(project.repositories.all())
    return list(repositories)


def _create_dataset_file_records(
        dirname=None, filename=None, session=None, user=None,
        repositories=None, exists_in=None):

    relative_path = op.join(dirname, filename)
    dataset_type, data_format = _get_data_type_format(filename)
    if not dataset_type:
        logger.warn("No dataset type found for %s", filename)
    if not data_format:
        logger.warn("No data format found for %s", filename)

    # Create the dataset.
    dataset = Dataset.objects.create(
        name=filename, session=session, created_by=user,
        dataset_type=dataset_type, data_format=data_format)

    # Create the parent datasets, according to the parent dataset types.
    if dataset_type:
        dst = dataset_type.parent_dataset_type
        ds = dataset
        while dst is not None:
            ds.parent_dataset = Dataset.objects.get_or_create(
                session=session, created_by=user, dataset_type=dst)[0]
            ds.save()

            dst = dst.parent_dataset_type
            ds = ds.parent_dataset

    # Create one file record per repository.
    exists_in = exists_in or ()
    for repo in repositories:
        exists = repo.name in exists_in
        FileRecord.objects.create(
            dataset=dataset, data_repository=repo, relative_path=relative_path, exists=exists)

    return dataset


def _make_dataset_response(dataset, return_parent=True):
    if not dataset:
        return None

    # Return the file records.
    file_records = [
        {
            'data_repository': fr.data_repository.name,
            'relative_path': fr.relative_path,
            'exists': fr.exists,
        }
        for fr in FileRecord.objects.filter(dataset=dataset)]

    out = {
        'id': dataset.pk,
        'name': dataset.name,
        'created_by': dataset.created_by.username,
        'created_datetime': dataset.created_datetime,
        'dataset_type': getattr(dataset.dataset_type, 'name', ''),
        'data_format': getattr(dataset.data_format, 'name', ''),
        'session': getattr(dataset.session, 'pk', ''),
    }
    if return_parent:
        out['parent_dataset'] = _make_dataset_response(
            dataset.parent_dataset, return_parent=False)
    out['file_records'] = file_records
    return out


class RegisterFileViewSet(mixins.CreateModelMixin,
                          viewsets.GenericViewSet):
    def create(self, request):
        user = request.user
        number = request.data.get('session_number', None)
        date = request.data.get('date', None)
        dirname = request.data.get('dirname', None)
        exists_in = request.data.get('exists_in', None)

        # comma-separated filenames
        filenames = request.data.get('filenames', '').split(',')
        subject = request.data.get('subject', None)
        subject = Subject.objects.get(nickname=subject)

        # Multiple projects, or the subject's projects
        projects = request.data.get('projects', '').split(',')
        projects = [Project.objects.get(name=project) for project in projects if project]
        repositories = _get_repositories_for_projects(projects or list(subject.projects.all()))

        session = _get_or_create_session(subject=subject, date=date, number=number, user=user)

        response = []
        for filename in filenames:
            if not filename:
                continue
            dataset = _create_dataset_file_records(
                dirname=dirname, filename=filename, session=session, user=user,
                repositories=repositories, exists_in=exists_in)
            out = _make_dataset_response(dataset)
            response.append(out)

        return Response(response, status=201)
