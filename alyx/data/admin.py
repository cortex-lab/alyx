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


class DataRepositoryAdmin(BaseAdmin):
    fields = ('name', 'repository_type', 'globus_endpoint_id', 'path')
    list_display = fields


class DataFormatAdmin(BaseAdmin):
    fields = ['name', 'description', 'alf_filename',
              'matlab_loader_function', 'python_loader_function']
    list_display = fields[:-1]


class DatasetTypeAdmin(BaseAdmin):
    fields = ('name', 'description', 'alf_filename')
    list_display = fields


class BaseExperimentalDataAdmin(BaseAdmin):
    def __init__(self, *args, **kwargs):
        for field in ('created_by', 'created_datetime'):
            if self.fields and field not in self.fields:
                self.fields += (field,)
        super(BaseAdmin, self).__init__(*args, **kwargs)


class FileRecordInline(BaseInlineAdmin):
    model = FileRecord
    extra = 1
    fields = ('data_repository', 'relative_path', 'exists', 'json')


class DatasetAdmin(BaseExperimentalDataAdmin):
    fields = ['name', 'dataset_type', 'md5', 'session_ro']
    readonly_fields = ['session_ro']
    list_display = ['name', 'dataset_type', 'session', 'created_by', 'created_datetime']
    inlines = [FileRecordInline]
    list_filter = [('created_by', RelatedDropdownFilter),
                   ('created_datetime', DateRangeFilter),
                   ]
    search_fields = ('created_by__username', 'name', 'session__subject__nickname')
    ordering = ('-created_datetime',)

    def session_ro(self, obj):
        url = get_admin_url(obj.session)
        return format_html('<a href="{url}">{name}</a>', url=url, name=obj.session)
    session_ro.short_description = 'session'


class FileRecordAdmin(BaseAdmin):
    fields = ('data_repository', 'relative_path', 'dataset')
    list_display = fields


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
