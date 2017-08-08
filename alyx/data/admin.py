from django.contrib import admin
from .models import (DataRepository, DataRepositoryType, FileRecord, Dataset, DatasetType,
                     Timescale, TimeSeries)
from alyx.base import BaseAdmin


class DataRepositoryTypeAdmin(BaseAdmin):
    fields = ['name']


class DataRepositoryAdmin(BaseAdmin):
    fields = ['name', 'repository_type', 'path']


class FileRecordAdmin(BaseAdmin):
    fields = ['data_repository', 'relative_path', 'dataset']


class DatasetTypeAdmin(BaseAdmin):
    fields = ['name']


class BaseExperimentalDataAdmin(BaseAdmin):
    def __init__(self, *args, **kwargs):
        for field in ('session', 'created_by', 'created_datetime'):
            if self.fields and field not in self.fields:
                self.fields += (field,)
        super(BaseAdmin, self).__init__(*args, **kwargs)


class DatasetAdmin(BaseExperimentalDataAdmin):
    fields = ['name', 'dataset_type', 'md5']


class TimescaleAdmin(BaseAdmin):
    fields = ['name', 'nominal_start', 'nominal_time_unit', 'final']


class TimeSeriesAdmin(BaseExperimentalDataAdmin):
    fields = ['data', 'timestamps', 'timescale']


admin.site.register(DataRepositoryType, DataRepositoryTypeAdmin)
admin.site.register(DataRepository, DataRepositoryAdmin)
admin.site.register(FileRecord, FileRecordAdmin)
admin.site.register(DatasetType, DatasetTypeAdmin)
admin.site.register(Dataset, DatasetAdmin)
admin.site.register(Timescale, TimescaleAdmin)
admin.site.register(TimeSeries, TimeSeriesAdmin)
