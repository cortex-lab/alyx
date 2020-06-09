from django.contrib import admin
from django.utils.html import format_html
from django_admin_listfilter_dropdown.filters import RelatedDropdownFilter
from rangefilter.filter import DateRangeFilter

from .models import (DataRepositoryType, DataRepository, DataFormat, DatasetType,
                     Dataset, FileRecord, Download)
from alyx.base import BaseAdmin, BaseInlineAdmin, DefaultListFilter, get_admin_url


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
    list_filter = [('created_by', RelatedDropdownFilter)]

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
              'session_ro', 'collection']
    readonly_fields = ['name_', 'session_ro', '_online']
    list_display = ['name_', '_online', 'version', 'collection', 'dataset_type_', 'file_size',
                    'session_ro', 'created_by', 'created_datetime']
    inlines = [FileRecordInline]
    list_filter = [('created_by', RelatedDropdownFilter),
                   ('created_datetime', DateRangeFilter),
                   ('dataset_type', RelatedDropdownFilter),
                   ]
    search_fields = ('created_by__username', 'name', 'session__subject__nickname', 'collection',
                     'dataset_type__name', 'dataset_type__filename_pattern', 'version')
    ordering = ('-created_datetime',)

    def get_queryset(self, request):
        qs = super(DatasetAdmin, self).get_queryset(request)
        qs = qs.select_related('dataset_type', 'session', 'session__subject', 'created_by')
        return qs

    def dataset_type_(self, obj):
        return obj.dataset_type.name

    def name_(self, obj):
        return obj.name or '<unnamed>'

    def session_ro(self, obj):
        url = get_admin_url(obj.session)
        return format_html('<a href="{url}">{name}</a>', url=url, name=obj.session)
    session_ro.short_description = 'session'

    def subject(self, obj):
        return obj.session.subject.nickname

    def _online(self, obj):
        return obj.online
    _online.short_description = 'On server'
    _online.boolean = True


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


admin.site.register(DataRepositoryType, DataRepositoryTypeAdmin)
admin.site.register(DataRepository, DataRepositoryAdmin)
admin.site.register(DataFormat, DataFormatAdmin)
admin.site.register(DatasetType, DatasetTypeAdmin)
admin.site.register(Dataset, DatasetAdmin)
admin.site.register(FileRecord, FileRecordAdmin)
admin.site.register(Download, DownloadAdmin)
