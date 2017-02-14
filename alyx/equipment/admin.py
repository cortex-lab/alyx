from django.contrib import admin
from polymorphic.admin import PolymorphicParentModelAdmin, PolymorphicChildModelAdmin
from .models import *


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

admin.site.register(Appliance, ApplianceParentAdmin)

admin.site.register(LabLocation)
admin.site.register(EquipmentManufacturer)
admin.site.register(EquipmentModel)
admin.site.register(VirusBatch)
