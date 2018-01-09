from django.contrib import admin
from .models import (DataRepositoryType, DataRepository, DataFormat, DatasetType,
                     Dataset, FileRecord, Timescale)
from alyx.base import BaseAdmin, BaseInlineAdmin, DefaultListFilter


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
    fields = ['name']
    list_display = fields[:-1]


class DataRepositoryAdmin(BaseAdmin):
    fields = ['name', 'repository_type', 'globus_endpoint_id', 'path']
    list_display = fields[:-1]


class DataFormatAdmin(BaseAdmin):
    fields = ['name', 'description', 'alf_filename',
              'matlab_loader_function', 'python_loader_function']
    list_display = fields[:-1]


class DatasetTypeAdmin(BaseAdmin):
    fields = ['name', 'description', 'alf_filename']
    list_display = fields[:-1]


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
    fields = ['name', 'dataset_type', 'md5']
    list_display = ['name', 'dataset_type', 'session', 'created_by', 'created_datetime']
    inlines = [FileRecordInline]
    list_filter = [CreatedByListFilter,
                   ]
    search_fields = ('created_by__username', 'name')


class FileRecordAdmin(BaseAdmin):
    fields = ['data_repository', 'relative_path', 'dataset']
    list_display = fields[:-1]


class TimescaleAdmin(BaseAdmin):
    fields = ['name', 'nominal_start', 'nominal_time_unit', 'final']
    list_display = fields[:-1]


admin.site.register(DataRepositoryType, DataRepositoryTypeAdmin)
admin.site.register(DataRepository, DataRepositoryAdmin)
admin.site.register(DataFormat, DataFormatAdmin)
admin.site.register(DatasetType, DatasetTypeAdmin)
admin.site.register(Dataset, DatasetAdmin)
admin.site.register(FileRecord, FileRecordAdmin)
admin.site.register(Timescale, TimescaleAdmin)
