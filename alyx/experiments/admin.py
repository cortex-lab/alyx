from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.contrib.admin import TabularInline
from reversion.admin import VersionAdmin

from mptt.admin import MPTTModelAdmin

from experiments.models import (TrajectoryEstimate, ProbeInsertion, ProbeModel, CoordinateSystem,
                                BrainRegion)
from alyx.base import BaseAdmin


class TrajectoryEstimateInline(TabularInline):
    show_change_link = True
    model = TrajectoryEstimate
    fields = ('x', 'y', 'z', 'depth', 'theta', 'phi', 'roll', 'provenance',)
    extra = 0


class ProbeInsertionInline(BaseAdmin):
    ordering = ('-session__start_time',)
    exclude = ['session']
    readonly_fields = ['_session']
    list_display = ['name', 'datetime', 'subject', 'session']
    list_display_links = ('name', 'subject', 'session',)
    search_fields = ('session__subject__nickname',)
    inlines = (TrajectoryEstimateInline,)

    def _session(self, obj):
        # this is to provide a link back to the session page
        url = reverse('admin:%s_%s_change' % (obj.session._meta.app_label,
                                              obj.session._meta.model_name),
                      args=[obj.session.id])
        return format_html('<b><a href="{url}" ">{}</a></b>', obj.session, url=url)
    _session.short_description = 'ephys session'


class ProbeModelAdmin(BaseAdmin):
    pass


class TrajectoryEstimateAdmin(VersionAdmin):
    exclude = ['probe_insertion']
    readonly_fields = ['_probe_insertion', 'session']
    list_display = ['datetime', 'subject', '_probe_insertion', 'x', 'y', 'z', 'depth', 'theta',
                    'phi', 'provenance', 'session']
    list_editable = ['x', 'y', 'z', 'depth', 'theta', 'phi']
    list_display_links = ('datetime', 'subject', 'session',)
    ordering = ['provenance', '-probe_insertion__session__start_time']
    search_fields = ('probe_insertion__session__subject__nickname',)

    def _probe_insertion(self, obj):
        # this is to provide a link back to the session page
        url = reverse('admin:%s_%s_change' % (obj.probe_insertion._meta.app_label,
                                              obj.probe_insertion._meta.model_name),
                      args=[obj.probe_insertion.id])
        return format_html('<b><a href="{url}" ">{}</a></b>', obj.probe_insertion.name, url=url)
    _probe_insertion.short_description = 'probe insertion'


class BrainRegionsAdmin(MPTTModelAdmin):
    list_display = ['name', 'id', 'acronym', 'parent', 'level']
    list_display_links = ('id', 'name', 'parent')
    search_fields = ('name', 'acronym', 'parent__name', 'id')


admin.site.register(BrainRegion, BrainRegionsAdmin)
admin.site.register(TrajectoryEstimate, TrajectoryEstimateAdmin)
admin.site.register(ProbeInsertion, ProbeInsertionInline)
admin.site.register(ProbeModel, ProbeModelAdmin)
admin.site.register(CoordinateSystem, BaseAdmin)
