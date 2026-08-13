from django.db.models import Count, Exists, OuterRef, ProtectedError, Subquery
from django.db.models.functions import Coalesce
from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django_admin_listfilter_dropdown.filters import (
    RelatedDropdownFilter,
    ChoiceDropdownFilter,
    SimpleDropdownFilter,
)
from rangefilter.filters import DateRangeFilter

from actions.models import Session
from subjects.models import Project
from .models import (DataRepositoryType, DataRepository, DataFormat, DatasetType,
                     Dataset, FileRecord, Download, Revision, Tag, DataNotice)
from alyx.base import (BaseAdmin, BaseInlineAdmin, DefaultListFilter, get_admin_url,
                       UserRelatedDropdownFilter)


class CreatedByListFilter(DefaultListFilter):
    title = 'created by'
    parameter_name = 'created_by'

    def lookups(self, request, model_admin):
        return (
            (None, 'Me'),
            ('all', 'All'),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.filter(created_by=request.user)
        elif self.value == 'all':
            return queryset.all()


class DataRepositoryTypeAdmin(BaseAdmin):
    fields = ('name', 'json')
    list_display = ('name',)
    ordering = ('name',)


class DataRepositoryAdmin(BaseAdmin):
    fields = ('name', 'repository_type', 'timezone', 'hostname', 'data_url', 'globus_path',
              'globus_endpoint_id', 'globus_is_personal')
    list_display = fields
    ordering = ('name',)


class DataFormatAdmin(BaseAdmin):
    fields = ['name', 'description', 'file_extension',
              'matlab_loader_function', 'python_loader_function']
    list_display = fields[:-1]
    ordering = ('name',)


class DatasetTypeAdmin(BaseAdmin):
    fields = ('name', 'description', 'filename_pattern', 'created_by')
    list_display = ('name', 'fcount', 'description', 'filename_pattern', 'created_by')
    ordering = ('name',)
    search_fields = ('name', 'description', 'filename_pattern', 'created_by__username')
    list_filter = [('created_by', UserRelatedDropdownFilter)]

    def get_queryset(self, request):
        qs = super(DatasetTypeAdmin, self).get_queryset(request)
        qs = qs.select_related('created_by')
        return qs

    def save_model(self, request, obj, form, change):
        if not obj.created_by and 'created_by' not in form.changed_data:
            obj.created_by = request.user
        super(DatasetTypeAdmin, self).save_model(request, obj, form, change)

    def fcount(self, dt):
        return Dataset.objects.filter(dataset_type=dt).count()


class BaseExperimentalDataAdmin(BaseAdmin):
    def __init__(self, *args, **kwargs):
        for field in ('created_by', 'created_datetime'):
            if self.fields and field not in self.fields:
                self.fields += (field,)
        super(BaseAdmin, self).__init__(*args, **kwargs)


class FileRecordInline(BaseInlineAdmin):
    model = FileRecord
    extra = 1
    fields = ('data_repository', 'relative_path', 'exists')


class DatasetAdmin(BaseExperimentalDataAdmin):
    fields = ['name', '_online', 'version', 'dataset_type', 'file_size', 'hash',
              'session_ro', 'collection', 'auto_datetime', 'revision_', 'default_dataset',
              '_protected', '_public', 'tags', 'qc']
    readonly_fields = ['name_', 'session_ro', '_online', 'auto_datetime', 'revision_',
                       '_protected', '_public', 'tags', 'qc']
    list_display = ['name_', '_online', 'version', 'collection', 'dataset_type_', 'file_size',
                    'session_ro', 'created_by', 'created_datetime', 'qc']
    inlines = [FileRecordInline]
    list_filter = [('created_by', UserRelatedDropdownFilter),
                   ('created_datetime', DateRangeFilter),
                   ('dataset_type', RelatedDropdownFilter),
                   ('tags', RelatedDropdownFilter),
                   ('qc', ChoiceDropdownFilter),
                   ('data_notices', RelatedDropdownFilter),
                   ]
    search_fields = ('session__id', 'name', 'collection', 'dataset_type__name',
                     'dataset_type__filename_pattern', 'version')
    ordering = ('-created_datetime',)

    def get_queryset(self, request):
        queryset = super(DatasetAdmin, self).get_queryset(request)
        queryset = queryset.select_related('session', 'session__subject', 'created_by')
        return queryset

    def dataset_type_(self, obj):
        return obj.dataset_type.name

    def name_(self, obj):
        return obj.name or '<unnamed>'

    def revision_(self, obj):
        return obj.revision.name

    def session_ro(self, obj):
        url = get_admin_url(obj.session)
        return format_html('<a href="{url}">{name}</a>', url=url, name=obj.session)
    session_ro.short_description = 'session'

    def subject(self, obj):
        return obj.session.subject.nickname

    def _online(self, obj):
        return obj.is_online
    _online.short_description = 'On server'
    _online.boolean = True

    def _protected(self, obj):
        return obj.is_protected
    _protected.short_description = 'Protected'
    _protected.boolean = True

    def _public(self, obj):
        return obj.is_public
    _public.short_description = 'Public'
    _public.boolean = True

    def delete_queryset(self, request, queryset):
        try:
            queryset.delete()
        except ProtectedError as e:
            err_msg = e.args[0] if e.args else 'One or more dataset(s) protected'
            self.message_user(request, err_msg, level=messages.ERROR)

    def delete_model(self, request, obj):
        try:
            obj.delete()
        except ProtectedError as e:
            # FIXME This still shows the successful message which is confusing for users
            err_msg = e.args[0] if e.args else f'Dataset {obj.name} is protected'
            self.message_user(request, err_msg, level=messages.ERROR)


class FileRecordAdmin(BaseAdmin):
    fields = ('relative_path', 'data_repository', 'dataset', 'exists')
    list_display = ('relative_path', 'repository', 'dataset_name',
                    'user', 'datetime', 'exists')
    readonly_fields = ('dataset', 'dataset_name', 'repository', 'user', 'datetime')
    list_filter = ('exists', 'data_repository__name')
    search_fields = ('dataset__created_by__username', 'dataset__name',
                     'relative_path', 'data_repository__name')
    ordering = ('-dataset__created_datetime',)

    def get_queryset(self, request):
        qs = super(FileRecordAdmin, self).get_queryset(request)
        qs = qs.select_related('data_repository', 'dataset', 'dataset__created_by')
        return qs

    def repository(self, obj):
        return getattr(obj.data_repository, 'name', None)

    def dataset_name(self, obj):
        return getattr(obj.dataset, 'name', None)

    def user(self, obj):
        return getattr(obj.dataset, 'created_by', None)

    def datetime(self, obj):
        return getattr(obj.dataset, 'created_datetime', None)


class DownloadAdmin(BaseAdmin):
    fields = ('user', 'dataset', 'first_download', 'last_download', 'count', 'projects')
    autocomplete_fields = ('dataset',)
    readonly_fields = ('first_download', 'last_download')
    list_display = ('dataset_type', 'dataset_name', 'subject', 'created_by',
                    'user', 'first_download', 'last_download', 'count')
    list_display_links = ('first_download',)
    search_filter = ('user__username', 'dataset__name')

    def dataset_name(self, obj):
        return obj.dataset.name

    def subject(self, obj):
        return obj.dataset.session.subject.nickname

    def dataset_type(self, obj):
        return obj.dataset.dataset_type.name

    def created_by(self, obj):
        return obj.dataset.created_by.username


class RevisionAdmin(BaseAdmin):
    fields = ['name', 'description', 'created_datetime']
    readonly_fields = ['created_datetime']
    list_display = ['name', 'description']
    search_fields = ('name',)
    ordering = ('-created_datetime',)


class TagAdmin(BaseAdmin):
    fields = ['name', 'description', 'protected', 'public', 'dataset_count', 'session_count']
    list_display = ['name', 'description', 'dataset_count', 'session_count', 'protected', 'public']
    readonly_fields = ['dataset_count', 'session_count']
    search_fields = ('name',)
    ordering = ('name',)

    def dataset_count(self, tag):
        return tag.dataset_count

    def session_count(self, tag):
        return tag.session_count

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(dataset_count=Count("datasets"))
        queryset = queryset.annotate(session_count=Count("datasets__session", distinct=True))
        return queryset


class DataNoticeAdmin(BaseAdmin):
    fields = (
        'name',
        'description',
        'importance',
        'version_affected',
        'affected_date_start',
        'affected_date_end',
        'datasets',
        'created_by',
        'created_datetime',
        'json',
    )
    readonly_fields = ('created_datetime',)
    # Maximum number of datasets rendered by the read-only `datasets_` field
    max_datasets_displayed = 100

    class DatasetTagListFilter(SimpleDropdownFilter):
        title = 'dataset tag'
        parameter_name = 'dataset_tag'

        def lookups(self, request, model_admin):
            return Tag.objects.order_by('name').values_list('id', 'name')

        def queryset(self, request, queryset):
            """Filter DataNotice queryset by dataset tag.

            This filter avoids joining the full Dataset table directly.
            """
            value = self.value()
            if not value:
                return queryset

            notice_dataset_through = DataNotice.datasets.through
            dataset_tag_through = Dataset.tags.through

            matching_datasets = dataset_tag_through.objects.filter(tag_id=value).values('dataset_id')
            matching_notice_datasets = notice_dataset_through.objects.filter(
                datanotice_id=OuterRef('pk'), dataset_id__in=matching_datasets)

            return queryset.annotate(_has_dataset_tag=Exists(matching_notice_datasets)).filter(
                _has_dataset_tag=True)

    class SessionProjectListFilter(SimpleDropdownFilter):
        title = 'project'
        parameter_name = 'project'

        def lookups(self, request, model_admin):
            notice_dataset_through = DataNotice.datasets.through
            session_project_through = Session.projects.through

            session_ids = Dataset.objects.filter(
                id__in=notice_dataset_through.objects.values('dataset_id'),
                session_id__isnull=False,
            ).values('session_id')
            project_ids = session_project_through.objects.filter(
                session_id__in=session_ids,
            ).values('project_id')

            return Project.objects.filter(id__in=project_ids).order_by('name').values_list('id', 'name')

        def queryset(self, request, queryset):
            value = self.value()
            if not value:
                return queryset

            notice_dataset_through = DataNotice.datasets.through
            session_project_through = Session.projects.through

            matching_sessions = session_project_through.objects.filter(project_id=value).values('session_id')
            matching_datasets = Dataset.objects.filter(session_id__in=matching_sessions).values('id')
            matching_notice_datasets = notice_dataset_through.objects.filter(
                datanotice_id=OuterRef('pk'), dataset_id__in=matching_datasets)

            return queryset.annotate(_has_project=Exists(matching_notice_datasets)).filter(
                _has_project=True)

    def has_change_permission(self, request, obj=None):
        # DataNotice has no subject/session ownership; any non-public authenticated user may edit.
        if request.user.is_public_user:
            return False
        return True

    def get_fields(self, request, obj=None):
        """Replace the datasets M2M with its read-only counterpart when changing a notice."""
        fields = super().get_fields(request, obj)
        if obj is None:  # datasets may still be picked when creating a notice
            return fields
        return tuple('datasets_' if field == 'datasets' else field for field in fields)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = tuple(super().get_readonly_fields(request, obj))
        if obj is None:
            return readonly_fields
        return readonly_fields + ('datasets_',)

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related('created_by')
        # Count the datasets with a correlated subquery on the through table: joining
        # the datasets table and grouping does not scale for notices with many datasets.
        dataset_counts = (DataNotice.datasets.through.objects
                          .filter(datanotice_id=OuterRef('pk'))
                          .order_by()
                          .values('datanotice_id')
                          .annotate(n=Count('dataset_id'))
                          .values('n'))
        return queryset.annotate(dataset_count=Coalesce(Subquery(dataset_counts), 0))

    @admin.display(description='datasets', ordering='dataset_count')
    def dataset_count(self, obj):
        return obj.dataset_count

    @staticmethod
    def _dataset_label(dataset):
        """Short human readable label for a dataset, cheap enough to call in a loop."""
        parts = []
        if dataset.session_id:
            session = dataset.session
            parts.append('%s/%s/%s' % (session.subject, str(session.start_time)[:10],
                                       str(session.number).zfill(3)))
        parts.append('/'.join(filter(None, (dataset.collection, dataset.name))))
        return ' '.join(filter(None, parts))

    @admin.display(description='datasets')
    def datasets_(self, obj):
        """Read-only, scrollable list of the datasets attached to this notice.

        The M2M widget is deliberately not rendered on the change form: for a notice
        with thousands of datasets every selected option has to be fetched and
        rendered, and posting them all back on save exceeds
        DATA_UPLOAD_MAX_NUMBER_FIELDS, which fails with a 400 status. Datasets are
        instead assigned when creating the notice, or through the REST API.
        """
        count = getattr(obj, 'dataset_count', None)
        if count is None:  # annotation missing, e.g. object fetched outside the admin
            count = obj.datasets.count()
        if not count:
            return 'No datasets'
        # NB: the base manager avoids the dataset type / data format select related
        datasets = (Dataset._base_manager.filter(data_notices=obj)
                    .select_related('session', 'session__subject')
                    .order_by('collection', 'name')[:self.max_datasets_displayed])
        items = format_html_join(
            '\n', '<li><a href="{}">{}</a></li>',
            ((get_admin_url(dataset), self._dataset_label(dataset)) for dataset in datasets))
        truncated = ('' if count <= self.max_datasets_displayed
                     else ' (showing the first %d)' % self.max_datasets_displayed)
        changelist_url = '%s?data_notices__id__exact=%s' % (
            reverse('admin:data_dataset_changelist'), obj.pk)
        return format_html(
            '<div style="max-height: 22em; max-width: 60em; overflow: auto; '
            'resize: vertical; border: 1px solid var(--hairline-color, #ccc); '
            'padding: 0.5em 0.5em 0.5em 0;">'
            '<ul style="margin: 0; padding-left: 2em;">{}</ul></div>'
            '<p class="help">{} dataset{} attached{}. '
            '<a href="{}">Show them in the dataset list</a>. '
            'The dataset list is read-only here; change it via the REST API.</p>',
            items, count, '' if count == 1 else 's', truncated, changelist_url)

    list_display = (
        'name',
        'dataset_count',
        'importance',
        'version_affected',
        'affected_date_start',
        'affected_date_end',
        'created_by',
        'created_datetime',
    )
    list_filter = (DatasetTagListFilter, SessionProjectListFilter)
    search_fields = ('name', 'description', 'version_affected', 'created_by__username')
    autocomplete_fields = ('datasets',)


admin.site.register(DataRepositoryType, DataRepositoryTypeAdmin)
admin.site.register(DataRepository, DataRepositoryAdmin)
admin.site.register(DataFormat, DataFormatAdmin)
admin.site.register(DatasetType, DatasetTypeAdmin)
admin.site.register(Dataset, DatasetAdmin)
admin.site.register(FileRecord, FileRecordAdmin)
admin.site.register(Download, DownloadAdmin)
admin.site.register(Revision, RevisionAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(DataNotice, DataNoticeAdmin)
