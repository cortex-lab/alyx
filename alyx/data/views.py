import logging
import re
from pathlib import Path

from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, viewsets, mixins, serializers
from rest_framework.response import Response
import django_filters
from django_filters.rest_framework import FilterSet

from subjects.models import Subject, Project
from misc.models import Lab
from .models import (DataRepositoryType,
                     DataRepository,
                     DataFormat,
                     DatasetType,
                     Dataset,
                     Download,
                     FileRecord,
                     new_download,
                     )
from .serializers import (DataRepositoryTypeSerializer,
                          DataRepositorySerializer,
                          DataFormatSerializer,
                          DatasetTypeSerializer,
                          DatasetSerializer,
                          DownloadSerializer,
                          FileRecordSerializer,
                          )
from .transfers import (_get_session, _get_repositories_for_labs,
                        _create_dataset_file_records, bulk_sync)

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
    subject = django_filters.CharFilter('session__subject__nickname')
    created_date = django_filters.CharFilter('created_datetime__date')
    date = django_filters.CharFilter('session__start_time__date')
    created_by = django_filters.CharFilter('created_by__username')
    dataset_type = django_filters.CharFilter('dataset_type__name')
    experiment_number = django_filters.CharFilter('session__number')
    created_date_gte = django_filters.DateTimeFilter('created_datetime__date',
                                                     lookup_expr='gte')
    created_date_lte = django_filters.DateTimeFilter('created_datetime__date',
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
        'file_size': dataset.file_size,
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
        """
        The session is retrieved by the ALF convention in the relative path, so this field has to
        match the format Subject/Date/Number as shown below.

        The set of repositories are given through the labs. The lab is by default the subject lab,
        but if it is specified, it overrides the subject lab entirely.

        One repository or lab is mandatory, as this is the repository where the files
        currently exist It can be identified either by name (recommended) or hostname
        (compatibility).

        The client side REST query should look like this:

        ```
        r_ = {'created_by': 'user_name_alyx',
              'name': 'repository_name_alyx',  # optional, will be added if doesn't match lab
              'path': 'ZM_1085/2019-02-12/002/alf',  # relative path to repo path
              'filenames': ['file1', 'file2'],
              'labs': 'alyxlabname1',  # optional, will get the subjects lab if not used
              'hash': ['f9c26e42-8f22-4f07-8fdd-bb51a63bedaa',
                       'f9c26e42-8f22-4f07-8fdd-bb51a63bedad']  # optional
              'filesizes': [145684, 354213],    # optional
              'server_only': True   # optional, defaults to False. Will only create file
              # records in the server repositories and skips local repositories
              }
        ```

        For backward compatibility the following is allowed (projects are labs the repo lookup
        is done on the hostname instead of the repository name):
        ```
         r_ = {
              ...
              'hostname': 'repo_hostname_alyx', # optional, will be added if doesn't match lab
              'projects': 'alyx_lab_name',  # optional, serves the same purpose as lab field
              ...
              }
        ```

        """
        user = request.data.get('created_by', None)
        if user:
            user = get_user_model().objects.get(username=user)
        else:
            user = request.user

        # get the concerned repository using the name/hostname combination
        name = request.data.get('name', None)
        hostname = request.data.get('hostname', None)
        if name:
            repo = DataRepository.objects.get(name=name)
        elif hostname:
            repo = DataRepository.objects.get(hostname=hostname)
        else:
            repo = None
        exists_in = (repo,)

        rel_dir_path = request.data.get('path', '')
        if not rel_dir_path:
            raise ValueError("The path argument is required.")

        # Extract the data repository from the hostname, the subject, the directory path.
        rel_dir_path = rel_dir_path.replace('\\', '/')
        rel_dir_path = rel_dir_path.replace('//', '/')
        subject, date, session_number = _parse_path(rel_dir_path)

        filenames = request.data.get('filenames', ())
        if isinstance(filenames, str):
            # comma-separated filenames
            filenames = filenames.split(',')

        # file hashes if provided
        hashes = request.data.get('hashes', [None for f in filenames])
        if isinstance(hashes, str):
            hashes = hashes.split(',')

        # filesizes if provided
        filesizes = request.data.get('filesizes', [None for f in filenames])
        if isinstance(filesizes, str):
            filesizes = filesizes.split(',')

        # flag to discard file records creation on local repositories, defaults to False
        server_only = request.data.get('server_only', False)

        # Multiple labs
        labs = request.data.get('projects', '') + request.data.get('labs', '')
        labs = labs.split(',')
        labs = [Lab.objects.get(name=lab) for lab in labs if lab]
        repositories = _get_repositories_for_labs(labs or [subject.lab], server_only=server_only)
        if repo and repo not in repositories:
            repositories += [repo]

        session = _get_session(
            subject=subject, date=date, number=session_number, user=user)
        assert session

        response = []
        for filename, hash, fsize in zip(filenames, hashes, filesizes):
            if not filename:
                continue
            # if filename contains path elements, interpret them as the collection field, otherwise
            # collection field is None
            collection = str(Path(filename.replace('\\', '/')).parent)
            collection = None if collection == '.' else collection
            filename = Path(filename).name
            dataset = _create_dataset_file_records(
                collection=collection, rel_dir_path=rel_dir_path, filename=filename,
                session=session, user=user, repositories=repositories, exists_in=exists_in,
                hash=hash, file_size=fsize)
            out = _make_dataset_response(dataset)
            response.append(out)

        return Response(response, status=201)


class SyncViewSet(viewsets.GenericViewSet):

    serializer_class = serializers.Serializer

    def sync(self, request):
        bulk_sync()
        return Response("ok", status=200)

    def sync_status(self, request):
        rep = bulk_sync(dry_run=True)
        return Response(rep, status=200)


class DownloadViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    REST query data field to log a download:
    ```
    data = {'user': 'labmember_name',
            'datasets': 'pk1',    # supports multiple pks as a list
            'projects': 'project_name')   # supports multiple projects as a list
    ```

    If there are multiple projects and multiple datasets, each datasets will be logged as
    downloaded for all projects.
    """  # noqa

    serializer_class = serializers.Serializer

    def create(self, request):
        user = request.user

        # this should work for bulk downloads, but they will all be assigned the same projects set
        datasets = request.data.get('datasets', None)
        if isinstance(datasets, str):
            datasets = datasets.split(',')
        datasets = [Dataset.objects.get(pk=ds) for ds in datasets]

        # Multiple projects, or the subject's projects
        projects = request.data.get('projects', ())
        if isinstance(projects, str):
            projects = projects.split(',')
        projects = [Project.objects.get(name=project) for project in projects if project]

        # loop over datasets
        dpk = []
        dcount = []
        for dataset in datasets:
            download = new_download(dataset, user, projects=projects)
            dpk.append(str(download.pk))
            dcount.append(download.count)

        return Response({'download': dpk, 'count': dcount}, status=201)


class DownloadDetail(generics.RetrieveUpdateAPIView):
    """
    Example: https://alyx.internationalbrainlab.org/downloads/151f5f77-c9bd-42e6-b31e-5a0e5b080afe
    """
    queryset = Download.objects.all()
    serializer_class = DownloadSerializer
    permission_classes = (permissions.IsAuthenticated,)


class DownloadFilter(FilterSet):
    json = django_filters.CharFilter(field_name='json', lookup_expr=('icontains'))
    dataset = django_filters.CharFilter('dataset__name')
    user = django_filters.CharFilter('user__username')
    dataset_type = django_filters.CharFilter(field_name='dataset__dataset_type__name',
                                             lookup_expr=('icontains'))

    class Meta:
        model = Download
        fields = ('count', )


class DownloadList(generics.ListAPIView):
    """
    Example: `https://alyx.internationalbrainlab.org/downloads`

    Filter implementation examples:

    -   `/downloads?user=jimmyjazz` on User
    -   `/downloads?json=processing` insensitive contains on JSON
    -   `/downloads?count=5`  download counts
    -   `/downloads?dataset_type=camera` insensitive contains on dataset type
    """  # noqa
    queryset = Download.objects.all()
    serializer_class = DownloadSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_class = DownloadFilter
