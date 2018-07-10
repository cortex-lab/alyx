import logging
import re

from rest_framework import generics, permissions, viewsets, mixins, serializers
from rest_framework.response import Response
import django_filters
from django_filters.rest_framework import FilterSet

from misc.models import OrderedUser
from subjects.models import Subject, Project
from electrophysiology.models import ExtracellularRecording
from .models import (DataRepositoryType,
                     DataRepository,
                     DataFormat,
                     DatasetType,
                     Dataset,
                     FileRecord,
                     Timescale,
                     _get_session,
                     )
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
from .transfers import _get_repositories_for_projects, _create_dataset_file_records

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
    created_datetime_gte = django_filters.DateTimeFilter(name='created_datetime',
                                                         lookup_expr='gte')
    created_datetime_lte = django_filters.DateTimeFilter(name='created_datetime',
                                                         lookup_expr='lte')

    class Meta:
        model = Dataset
        exclude = ['json']


class DatasetList(generics.ListCreateAPIView):
    queryset = Dataset.objects.all()
    queryset = DatasetSerializer.setup_eager_loading(queryset)
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
    queryset = FileRecordSerializer.setup_eager_loading(queryset)
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

def _make_dataset_response(dataset):
    if not dataset:
        return None

    # Return the file records.
    file_records = [
        {
            'id': fr.pk,
            'data_repository': fr.data_repository.name,
            'relative_path': fr.relative_path,
            'exists': fr.exists,
        }
        for fr in FileRecord.objects.filter(dataset=dataset)]

    out = {
        'id': dataset.pk,
        'name': dataset.name,
        'subject': dataset.session.subject.nickname,
        'created_by': dataset.created_by.username,
        'created_datetime': dataset.created_datetime,
        'dataset_type': getattr(dataset.dataset_type, 'name', ''),
        'data_format': getattr(dataset.data_format, 'name', ''),
        'session': getattr(dataset.session, 'pk', ''),
        'session_number': dataset.session.number,
        'session_users': ','.join(_.username for _ in dataset.session.users.all()),
        'session_start_time': dataset.session.start_time,
    }
    out['file_records'] = file_records
    return out


def _parse_path(path):
    pattern = (r'^(?P<nickname>[a-zA-Z0-9\-\_]+)/'
               # '(?P<year>[0-9]{4})\-(?P<month>[0-9]{2})\-(?P<day>[0-9]{2})/'
               r'(?P<date>[0-9\-]{10})/'
               r'(?P<session_number>[0-9]+)'
               r'(.*)$')
    m = re.match(pattern, path)
    if not m:
        raise ValueError(r"The path %s should be `nickname/YYYY-MM-DD/n/..." % path)
    # date_triplet = (m.group('year'), m.group('month'), m.group('day'))
    date = m.group('date')
    nickname = m.group('nickname')
    session_number = int(m.group('session_number'))
    # An error is raised if the subject or data repository do not exist.
    subject = Subject.objects.get(nickname=nickname)
    return subject, date, session_number


class RegisterFileViewSet(mixins.CreateModelMixin,
                          viewsets.GenericViewSet):

    serializer_class = serializers.Serializer

    def create(self, request):
        user = request.data.get('created_by', None)
        if user:
            user = OrderedUser.objects.get(username=user)
        else:
            user = request.user
        dns = request.data.get('dns', None)
        if not dns:
            raise ValueError("The dns argument is required.")
        repo = DataRepository.objects.get(dns=dns)
        exists_in = (repo,)

        rel_dir_path = request.data.get('path', '')
        if not rel_dir_path:
            raise ValueError("The path argument is required.")

        # Extract the data repository from the DNS, the subject, the directory path.
        rel_dir_path = rel_dir_path.replace('\\', '/')
        rel_dir_path = rel_dir_path.replace('//', '/')
        subject, date, session_number = _parse_path(rel_dir_path)

        filenames = request.data.get('filenames', ())
        if isinstance(filenames, str):
            # comma-separated filenames
            filenames = filenames.split(',')

        # Multiple projects, or the subject's projects
        projects = request.data.get('projects', ())
        if isinstance(projects, str):
            projects = projects.split(',')

        projects = [Project.objects.get(name=project) for project in projects if project]
        repositories = _get_repositories_for_projects(projects or list(subject.projects.all()))
        if repo not in repositories:
            repositories += [repo]

        session = _get_session(
            subject=subject, date=date, number=session_number, user=user)
        assert session

        response = []
        for filename in filenames:
            if not filename:
                continue
            dataset = _create_dataset_file_records(
                rel_dir_path=rel_dir_path, filename=filename, session=session, user=user,
                repositories=repositories, exists_in=exists_in)
            out = _make_dataset_response(dataset)
            response.append(out)

        return Response(response, status=201)
