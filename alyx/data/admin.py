from django.contrib import admin
from .models import DataRepository, FileRecord, Dataset, TimeSeries
from alyx.base import BaseAdmin


class DataRepositoryAdmin(BaseAdmin):
    fields = ['name', 'repository_type']


class FileRecordAdmin(BaseAdmin):
    fields = ['dataset', 'filename']


class DatasetAdmin(BaseAdmin):
    fields = ['name']


class TimeSeriesAdmin(BaseAdmin):
    fields = ['file', 'column_names', 'description', 'timestamps', 'session']


admin.site.register(DataRepository, DataRepositoryAdmin)
admin.site.register(FileRecord, FileRecordAdmin)
admin.site.register(Dataset, DatasetAdmin)
admin.site.register(TimeSeries, TimeSeriesAdmin)
