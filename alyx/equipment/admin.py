from django.contrib import admin
from polymorphic.admin import PolymorphicParentModelAdmin, PolymorphicChildModelAdmin
from .models import (Appliance, WeighingScale, Amplifier, PipettePuller, DAQ, ExtracellularProbe,
                     VirusBatch, LabLocation, EquipmentManufacturer, EquipmentModel
                     )
from alyx.base import BaseAdmin


class ApplianceChildAdmin(PolymorphicChildModelAdmin):
    base_model = Appliance


class WeighingScaleAdmin(ApplianceChildAdmin):
    base_model = WeighingScale


class AmplifierAdmin(ApplianceChildAdmin):
    base_model = Amplifier


class PipettePullerAdmin(ApplianceChildAdmin):
    base_model = PipettePuller


class DAQAdmin(ApplianceChildAdmin):
    base_model = DAQ


class ExtracellularProbeAdmin(ApplianceChildAdmin):
    base_model = ExtracellularProbe


class ApplianceParentAdmin(PolymorphicParentModelAdmin):
    base_model = Appliance
    child_models = (
        (WeighingScale, WeighingScaleAdmin),
        (Amplifier, AmplifierAdmin),
        (ExtracellularProbe, ExtracellularProbeAdmin),
        (PipettePuller, PipettePullerAdmin),
        (DAQ, DAQAdmin)
    )
    polymorphic_list = True
    list_display = ('descriptive_name', 'polymorphic_ctype',
                    'location', 'equipment_model')
    pk_regex = '([\w-]+)'


class LabLocationAdmin(BaseAdmin):
    fields = ['name']


class EquipmentManufacturerAdmin(BaseAdmin):
    fields = ['name', 'notes']


class EquipmentModelAdmin(BaseAdmin):
    fields = ['model_name', 'manufacturer', 'description']


class VirusBatchAdmin(BaseAdmin):
    fields = ['virus_type', 'virus_source', 'date_time_made', 'nominal_titer', 'description']


admin.site.register(Appliance, ApplianceParentAdmin)

admin.site.register(LabLocation, LabLocationAdmin)
admin.site.register(EquipmentManufacturer, EquipmentManufacturerAdmin)
admin.site.register(EquipmentModel, EquipmentModelAdmin)
admin.site.register(VirusBatch, VirusBatchAdmin)
