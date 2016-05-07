from django.contrib import admin
from polymorphic.admin import PolymorphicParentModelAdmin, PolymorphicChildModelAdmin
from .models import *

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

admin.site.register(DataRepository, DataRepositoryParentAdmin)
admin.site.register(PhysicalArchive)
admin.site.register(FileRecord)
admin.site.register(LogicalFile)
admin.site.register(Fileset)