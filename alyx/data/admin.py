from django.contrib import admin
from polymorphic.admin import PolymorphicParentModelAdmin, PolymorphicChildModelAdmin
from .models import *
from alyx.base import BaseAdmin


class DataRepositoryChildAdmin(PolymorphicChildModelAdmin):
    base_model = DataRepository


class LocalDataRepositoryAdmin(DataRepositoryChildAdmin):
    base_model = LocalDataRepository


class NetworkDataRepositoryAdmin(DataRepositoryChildAdmin):
    base_model = LocalDataRepository


class ArchiveDataRepositoryAdmin(DataRepositoryChildAdmin):
    base_model = LocalDataRepository


class DataRepositoryParentAdmin(PolymorphicParentModelAdmin):
    base_model = DataRepository
    child_models = (
        (LocalDataRepository, LocalDataRepositoryAdmin),
        (NetworkDataRepository, NetworkDataRepositoryAdmin),
        (ArchiveDataRepository, ArchiveDataRepositoryAdmin)
    )
    polymorphic_list = True
    list_display = ('name', 'polymorphic_ctype')
    pk_regex = '([\w-]+)'


class PhysicalArchiveAdmin(BaseAdmin):
    fields = ['location']


class FileRecordAdmin(BaseAdmin):
    fields = ['dataset', 'filename']


class DatasetAdmin(BaseAdmin):
    fields = ['name']


class TimestampAdmin(BaseAdmin):
    fields = ['name', 'timebase_name', 'regularly_sampled', 'sample_rate', 'first_sample_time']


class TimeSeriesAdmin(BaseAdmin):
    fields = ['file', 'column_names', 'description', 'timestamps', 'session']


admin.site.register(DataRepository, DataRepositoryParentAdmin)
admin.site.register(PhysicalArchive, PhysicalArchiveAdmin)
admin.site.register(FileRecord, FileRecordAdmin)
admin.site.register(Dataset, DatasetAdmin)
admin.site.register(Timestamp, TimestampAdmin)
admin.site.register(TimeSeries, TimeSeriesAdmin)
