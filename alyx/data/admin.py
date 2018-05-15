from django.contrib import admin
from django.utils.html import format_html
from django_admin_listfilter_dropdown.filters import RelatedDropdownFilter
from rangefilter.filter import DateRangeFilter

from .models import (DataRepositoryType, DataRepository, DataFormat, DatasetType,
                     Dataset, FileRecord, Timescale)
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
    fields = ('name', 'repository_type', 'timezone', 'dns', 'data_url', 'globus_path',
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
    list_display = fields
    ordering = ('name',)
    search_fields = ('name', 'description', 'filename_pattern', 'created_by__username')
    list_filter = [('created_by', RelatedDropdownFilter)]

    def save_model(self, request, obj, form, change):
        if not obj.created_by and 'created_by' not in form.changed_data:
            obj.created_by = request.user
        super(DatasetTypeAdmin, self).save_model(request, obj, form, change)


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
    fields = ['name', 'dataset_type', 'md5', 'session_ro']
    readonly_fields = ['name_', 'session_ro']
    list_display = ['name_', 'dataset_type', 'session',
                    'created_by', 'created_datetime']
    list_select_related = ('dataset_type', 'session', 'session__subject', 'created_by')
    inlines = [FileRecordInline]
    list_filter = [('created_by', RelatedDropdownFilter),
                   ('created_datetime', DateRangeFilter),
                   ('dataset_type', RelatedDropdownFilter),
                   ]
    search_fields = ('created_by__username', 'name', 'session__subject__nickname',
                     'dataset_type__name', 'dataset_type__filename_pattern')
    ordering = ('-created_datetime',)

    def name_(self, obj):
        return obj.name or '<unnamed>'

    def session_ro(self, obj):
        url = get_admin_url(obj.session)
        return format_html('<a href="{url}">{name}</a>', url=url, name=obj.session)
    session_ro.short_description = 'session'


class FileRecordAdmin(BaseAdmin):
    fields = ('relative_path', 'data_repository', 'dataset', 'exists')
    list_display = ('relative_path', 'repository', 'dataset_name',
                    'user', 'datetime', 'exists')
    list_select_related = ('data_repository', 'dataset', 'dataset__created_by')
    readonly_fields = ('dataset', 'dataset_name', 'repository', 'user', 'datetime')
    list_filter = ('exists', 'data_repository__name')
    search_fields = ('dataset__created_by__username', 'dataset__name',
                     'relative_path', 'data_repository__name')
    ordering = ('-dataset__created_datetime',)

    def repository(self, obj):
        return getattr(obj.data_repository, 'name', None)

    def dataset_name(self, obj):
        return getattr(obj.dataset, 'name', None)

    def user(self, obj):
        return getattr(obj.dataset, 'created_by', None)

    def datetime(self, obj):
        return getattr(obj.dataset, 'created_datetime', None)


class TimescaleAdmin(BaseAdmin):
    fields = ('name', 'nominal_start', 'nominal_time_unit', 'final')
    list_display = fields


admin.site.register(DataRepositoryType, DataRepositoryTypeAdmin)
admin.site.register(DataRepository, DataRepositoryAdmin)
admin.site.register(DataFormat, DataFormatAdmin)
admin.site.register(DatasetType, DatasetTypeAdmin)
admin.site.register(Dataset, DatasetAdmin)
admin.site.register(FileRecord, FileRecordAdmin)
admin.site.register(Timescale, TimescaleAdmin)
