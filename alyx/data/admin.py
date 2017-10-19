from django.contrib import admin
from .models import (DataRepositoryType, DataRepository, DataFormat, DatasetType,
                     Dataset, FileRecord, Timescale)
from alyx.base import BaseAdmin


class DataRepositoryTypeAdmin(BaseAdmin):
    fields = ['name']


class DataRepositoryAdmin(BaseAdmin):
    fields = ['name', 'repository_type', 'path']


class DataFormatAdmin(BaseAdmin):
    fields = ['name', 'description', 'alf_filename',
              'matlab_loader_function', 'python_loader_function']


class DatasetTypeAdmin(BaseAdmin):
    fields = ['name', 'description', 'alf_filename']


class BaseExperimentalDataAdmin(BaseAdmin):
    def __init__(self, *args, **kwargs):
        for field in ('session', 'created_by', 'created_datetime'):
            if self.fields and field not in self.fields:
                self.fields += (field,)
        super(BaseAdmin, self).__init__(*args, **kwargs)


class DatasetAdmin(BaseExperimentalDataAdmin):
    fields = ['name', 'dataset_type', 'md5']


class FileRecordAdmin(BaseAdmin):
    fields = ['data_repository', 'relative_path', 'dataset']


class TimescaleAdmin(BaseAdmin):
    fields = ['name', 'nominal_start', 'nominal_time_unit', 'final']


admin.site.register(DataRepositoryType, DataRepositoryTypeAdmin)
admin.site.register(DataRepository, DataRepositoryAdmin)
admin.site.register(DataFormat, DataFormatAdmin)
admin.site.register(DatasetType, DatasetTypeAdmin)
admin.site.register(Dataset, DatasetAdmin)
admin.site.register(FileRecord, FileRecordAdmin)
admin.site.register(Timescale, TimescaleAdmin)
