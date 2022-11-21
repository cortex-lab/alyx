import structlog
import re

from django.contrib.auth import get_user_model
from rest_framework import generics, viewsets, mixins, serializers
from rest_framework.response import Response
import django_filters

from alyx.base import BaseFilterSet, rest_permission_classes
from subjects.models import Subject, Project
from experiments.models import ProbeInsertion
from misc.models import Lab
from .models import (DataRepositoryType,
                     DataRepository,
                     DataFormat,
                     DatasetType,
                     Dataset,
                     Download,
                     FileRecord,
                     new_download,
                     Revision,
                     Tag
                     )
from .serializers import (DataRepositoryTypeSerializer,
                          DataRepositorySerializer,
                          DataFormatSerializer,
                          DatasetTypeSerializer,
                          DatasetSerializer,
                          DownloadSerializer,
                          FileRecordSerializer,
                          RevisionSerializer,
                          TagSerializer
                          )
from .transfers import (_get_session, _get_repositories_for_labs,
                        _create_dataset_file_records, bulk_sync, _check_dataset_protected,
                        _get_name_collection_revision)

logger = structlog.get_logger(__name__)

# DataRepositoryType
# ------------------------------------------------------------------------------------------------


class DataRepositoryTypeList(generics.ListCreateAPIView):
    queryset = DataRepositoryType.objects.all()
    serializer_class = DataRepositoryTypeSerializer
    permission_classes = rest_permission_classes()
    lookup_field = 'name'


class DataRepositoryTypeDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = DataRepositoryType.objects.all()
    serializer_class = DataRepositoryTypeSerializer
    permission_classes = rest_permission_classes()
    lookup_field = 'name'


# DataRepository
# ------------------------------------------------------------------------------------------------

class DataRepositoryList(generics.ListCreateAPIView):
    queryset = DataRepository.objects.all()
    serializer_class = DataRepositorySerializer
    permission_classes = rest_permission_classes()
    filter_fields = ('name', 'globus_is_personal', 'globus_endpoint_id')
    lookup_field = 'name'


class DataRepositoryDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = DataRepository.objects.all()
    serializer_class = DataRepositorySerializer
    permission_classes = rest_permission_classes()
    lookup_field = 'name'


# DataFormat
# ------------------------------------------------------------------------------------------------

class DataFormatList(generics.ListCreateAPIView):
    queryset = DataFormat.objects.all()
    serializer_class = DataFormatSerializer
    permission_classes = rest_permission_classes()
    lookup_field = 'name'


class DataFormatDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = DataFormat.objects.all()
    serializer_class = DataFormatSerializer
    permission_classes = rest_permission_classes()
    lookup_field = 'name'


# DatasetType
# ------------------------------------------------------------------------------------------------

class DatasetTypeList(generics.ListCreateAPIView):
    queryset = DatasetType.objects.all()
    serializer_class = DatasetTypeSerializer
    permission_classes = rest_permission_classes()
    lookup_field = 'name'


class DatasetTypeDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = DatasetType.objects.all()
    serializer_class = DatasetTypeSerializer
    permission_classes = rest_permission_classes()
    lookup_field = 'name'


# Revision
# -------------------------------------------------------------------------------------------------

class RevisionList(generics.ListCreateAPIView):
    queryset = Revision.objects.all()
    serializer_class = RevisionSerializer
    permission_classes = rest_permission_classes()


class RevisionDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Revision.objects.all()
    serializer_class = RevisionSerializer
    permission_classes = rest_permission_classes()
    lookup_field = 'name'


class TagList(generics.ListCreateAPIView):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = rest_permission_classes()


class TagDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = rest_permission_classes()

# Dataset
# ------------------------------------------------------------------------------------------------


class DatasetFilter(BaseFilterSet):
    subject = django_filters.CharFilter('session__subject__nickname')
    lab = django_filters.CharFilter('session__lab__name')
    created_date = django_filters.CharFilter('created_datetime__date')
    date = django_filters.CharFilter('session__start_time__date')
    created_by = django_filters.CharFilter('created_by__username')
    dataset_type = django_filters.CharFilter('dataset_type__name')
    experiment_number = django_filters.CharFilter('session__number')
    created_date_gte = django_filters.DateTimeFilter('created_datetime__date',
                                                     lookup_expr='gte')
    created_date_lte = django_filters.DateTimeFilter('created_datetime__date',
                                                     lookup_expr='lte')
    exists = django_filters.BooleanFilter(method='filter_exists')
    probe_insertion = django_filters.UUIDFilter(method='probe_insertion_filter')
    public = django_filters.BooleanFilter(method='filter_public')
    protected = django_filters.BooleanFilter(method='filter_protected')
    tag = django_filters.CharFilter('tags__name')
    revision = django_filters.CharFilter('revision__name')

    class Meta:
        model = Dataset
        exclude = ['json']

    def filter_exists(self, dsets, name, value):
        """
        Filters datasets for which at least one file record Globus not personal exists.
        Only if the database has any globus non-personal repositories (ie. servers)
        """
        if len(DataRepository.objects.filter(globus_is_personal=False)) > 0:
            frs = FileRecord.objects.filter(pk__in=dsets.values_list("file_records", flat=True))
            pkd = frs.filter(exists=value, data_repository__globus_is_personal=False
                             ).values_list("dataset", flat=True)
            dsets = dsets.filter(pk__in=pkd)
        return dsets

    def probe_insertion_filter(self, dsets, _, pk):
        """
        Filter datasets that have collection name the same as probe id
        """
        probe = ProbeInsertion.objects.get(pk=pk)
        dsets = dsets.filter(session=probe.session, collection__icontains=probe.name)
        return dsets

    def filter_public(self, dsets, name, value):
        if value:
            return dsets.filter(tags__public=True).distinct()
        else:
            return dsets.exclude(tags__public=True)

    def filter_protected(self, dsets, name, value):
        if value:
            return dsets.filter(tags__protected=True).distinct()
        else:
            return dsets.exclude(tags__protected=True)


class DatasetList(generics.ListCreateAPIView):
    """
    get: **FILTERS**
    -   **subject**: subject nickname: `/datasets?subject=Algernon`
    -   **lab**: lab name `/datsets?lab=wittenlab`
    -   **created_date**: dataset registration date `/datasets?created_date=2020-02-16`
    -   **date**: session start time date `/datasets?date=2020-02-16`
    -   **created_by**: lab member creation `/datasets?created_by=root`
    -   **experiment_number**: session number  `/datasets?experiment_number=1`
    -   **created_date_gte**: greater/equal creation date  `/datasets?created_date_gte=2020-02-16`
    -   **created_date_lte**: lower/equal creation date  `/datasets?created_date_lte=2020-02-16`
    -   **exists**: only returns datasets for which a file record exists or doesn't exit on a
    server repo (boolean)  `/datasets?exists=True`
    -   **probe_insertions**: probe insertion id '/datasets?probe_insertion=uuid
    -   **tag**: tag name '/datasets?tag=repeated_site
    -   **public**: only returns datasets that are public or not public
    -   **protected**: only returns datasets that are protected or not protected

    [===> dataset model reference](/admin/doc/models/data.dataset)
    """
    queryset = Dataset.objects.all()
    queryset = DatasetSerializer.setup_eager_loading(queryset)
    serializer_class = DatasetSerializer
    permission_classes = rest_permission_classes()
    filter_class = DatasetFilter


class DatasetDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Dataset.objects.all()
    serializer_class = DatasetSerializer
    permission_classes = rest_permission_classes()


# FileRecord
# ------------------------------------------------------------------------------------------------
class FileRecordFilter(BaseFilterSet):
    lab = django_filters.CharFilter('dataset__session__lab__name')
    data_repository = django_filters.CharFilter('data_repository__name')
    globus_is_personal = django_filters.BooleanFilter('data_repository__globus_is_personal')

    class Meta:
        model = FileRecord
        exclude = ['json']


class FileRecordList(generics.ListCreateAPIView):
    """
    get: **FILTERS**

    -   **dataset**: dataset UUID: `/files?dataset=aad23144-0e52-4eac-80c5-c4ee2decb198`
    -   **exists**: Bool `/files?exists=False`
    -   **lab**: lab name `/files?lab=wittenlab`
    -   **data_repository**: data repository name `/files?data_repository=mainen_lab_SR`
    -   **globus_is_personal**: bool type of Globus endpoint `/files?globus_is_personal=True`

    [===> file record model reference](/admin/doc/models/data.filerecord)
    """
    queryset = FileRecord.objects.all()
    queryset = FileRecordSerializer.setup_eager_loading(queryset)
    serializer_class = FileRecordSerializer
    permission_classes = rest_permission_classes()
    filter_class = FileRecordFilter


class FileRecordDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = FileRecord.objects.all()
    serializer_class = FileRecordSerializer
    permission_classes = rest_permission_classes()


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
        'collection': dataset.collection,
        'revision': getattr(dataset.revision, 'name', None),
        'default': dataset.default_dataset,
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
        Endpoint to create a register a dataset record through the REST API.

        The session is retrieved by the ALF convention in the relative path, so this field has to
        match the format Subject/Date/Number as shown below.

        The set of repositories are given through the labs. The lab is by default the subject lab,
        but if it is specified, it overrides the subject lab entirely.

        One repository or lab is mandatory, as this is the repository where the files
        currently exist It can be identified either by name (recommended) or hostname
        (compatibility).
        The client side REST query should look like this:

        ```python
        r_ = {'created_by': 'user_name_alyx',
              'name': 'repository_name_alyx',  # optional, will be added if doesn't match lab
              'path': 'ZM_1085/2019-02-12/002/alf',  # relative path to repo path
              'filenames': ['file1', 'file2'],
              'labs': 'alyxlabname1',  # optional, will get the subjects lab if not used
              'hashes': ['f9c26e42-8f22-4f07-8fdd-bb51a63bedaa',
                       'f9c26e42-8f22-4f07-8fdd-bb51a63bedad']  # optional
              'filesizes': [145684, 354213],    # optional
              'server_only': True,   # optional, defaults to False. Will only create file
              # records in the server repositories and skips local repositories
              'versions': ['1.4.4', '1.4.4'],  # optional, usually refers to the software version
              # used to generate the file
              'default': False #optional , defaults to True, if more than one revision of dataset,
              whether to set current one as the default
              'check_protected: False # optional, defaults to False, before attempting to register
              datasets checks if any are protected
              }
        ```

        For backward compatibility the following is allowed (projects are labs the repo lookup
        is done on the hostname instead of the repository name):
        ```python
         r_ = {'hostname': 'repo_hostname_alyx', # optional, will be added if doesn't match lab
               'projects': 'alyx_lab_name',  # optional, alias of lab field above
              }
        ```

        If the dataset already exists, it will use the file hash to deduce if the file has been
        patched or not (ie. the filerecords will be created as not existing)
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
            filenames = filenames.split(',')

        # versions if provided
        versions = request.data.get('versions', [None] * len(filenames))
        if isinstance(versions, str):
            versions = versions.split(',')

        # file hashes if provided
        hashes = request.data.get('hashes', [None] * len(filenames))
        if isinstance(hashes, str):
            hashes = hashes.split(',')

        # file sizes if provided
        filesizes = request.data.get('filesizes', [None] * len(filenames))
        if isinstance(filesizes, str):
            filesizes = filesizes.split(',')

        # flag to discard file records creation on local repositories, defaults to False
        server_only = request.data.get('server_only', False)
        if isinstance(server_only, str):
            server_only = server_only == 'True'

        default = request.data.get('default', True)
        # Need to explicitly cast string to a bool
        if isinstance(default, str):
            default = default == 'True'

        check_protected = request.data.get('check_protected', False)
        # Need to explicitly cast string to a bool
        if isinstance(check_protected, str):
            check_protected = check_protected == 'True'

        # Multiple labs
        labs = request.data.get('projects', '') + request.data.get('labs', '')
        labs = labs.split(',')
        labs = [Lab.objects.get(name=lab) for lab in labs if lab]
        repositories = _get_repositories_for_labs(labs or [subject.lab], server_only=server_only)
        if repo and repo not in repositories:
            repositories += [repo]
        if server_only:
            exists_in = repositories

        # # If exists is specified to be false then we set the exists_in back to None
        exists = request.data.get('exists', True)
        # Need to explicitly cast string to a bool
        if isinstance(exists, str):
            exists = exists == 'True'
        if not exists:
            exists_in = (None,)

        session = _get_session(
            subject=subject, date=date, number=session_number, user=user)
        assert session

        # If the check protected flag is True, loop through the files to see if any are protected
        if check_protected:
            prot_response = []
            protected = []
            for file in filenames:

                info, resp = _get_name_collection_revision(file, rel_dir_path, subject, date)

                if resp:
                    return resp

                prot, prot_info = _check_dataset_protected(
                    session, info['collection'], info['filename'])
                protected.append(prot)
                prot_response.append({file: prot_info})

            if any(protected):
                data = {'status_code': 403,
                        'error': 'One or more datasets is protected',
                        'details': prot_response}
                return Response(data=data, status=403)

        response = []
        for filename, hash, fsize, version in zip(filenames, hashes, filesizes, versions):
            if not filename:
                continue
            info, resp = _get_name_collection_revision(filename, rel_dir_path, subject, date)

            if resp:
                return resp

            if info['revision'] is not None:
                revision, _ = Revision.objects.get_or_create(name=info['revision'])
            else:
                revision = None

            dataset, resp = _create_dataset_file_records(
                collection=info['collection'], rel_dir_path=info['rel_dir_path'],
                filename=info['filename'], session=session, user=user, repositories=repositories,
                exists_in=exists_in, hash=hash, file_size=fsize, version=version,
                revision=revision, default=default)
            if resp:
                return resp
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
    permission_classes = rest_permission_classes()


class DownloadFilter(BaseFilterSet):
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
    get: **FILTERS**

    -   **user**: Labmember name: `/downloads?user=jimmyjazz`
    -   **json**: icontains on json: `/downloads?json=processing`
    -   **count**: count number: `/downloads?count=5`
    -   **dataset_type**: icontains on dataset type`/downloads?dataset_type=camera`

    """
    queryset = Download.objects.all()
    serializer_class = DownloadSerializer
    permission_classes = rest_permission_classes()
    filter_class = DownloadFilter
