from django.contrib import admin
from django.urls import reverse
from django.utils.safestring import SafeString
from django.utils.html import format_html
from django.contrib.admin import TabularInline

from mptt.admin import MPTTModelAdmin

from experiments.models import (TrajectoryEstimate, ProbeInsertion, ProbeModel, CoordinateSystem,
                                BrainRegion, Channel, ChronicInsertion, FOV, FOVLocation)
from misc.admin import NoteInline
from alyx.base import BaseAdmin


class TrajectoryEstimateInline(TabularInline):
    show_change_link = True
    model = TrajectoryEstimate
    fields = ('x', 'y', 'z', 'depth', 'theta', 'phi', 'roll', 'provenance',)
    extra = 0


class ProbeInsertionInline(BaseAdmin):
    ordering = ('-session__start_time',)
    exclude = ['session', 'datasets']
    readonly_fields = ['id', '_session', 'auto_datetime', '_datasets']
    list_display = ['name', 'datetime', '_subject', '_session']
    list_display_links = ('name', '_subject', '_session',)
    search_fields = ('session__subject__nickname', 'session__pk', 'id')
    inlines = (TrajectoryEstimateInline, NoteInline)

    def _session(self, obj):
        # this is to provide a link back to the session page
        url = reverse('admin:%s_%s_change' % (obj.session._meta.app_label,
                                              obj.session._meta.model_name),
                      args=[obj.session.id])
        return format_html('<b><a href="{url}" ">{}</a></b>', obj.session, url=url)
    _session.short_description = 'ephys session'

    def _datasets(self, obj):
        # this is to provide a link back to the session page
        html = ""
        for dset in obj.datasets.all().order_by('collection', 'name'):
            url = reverse('admin:%s_%s_change'
                          % (dset._meta.app_label, dset._meta.model_name), args=[dset.id])
            html += format_html('<a href="{url}" ">./{}/{}</a><br></br>',
                                dset.collection, dset.name, url=url)
        return SafeString(html)
    _datasets.short_descritption = 'datasets'

    def _subject(self, obj):
        # this is to provide a link back to the _subject page
        url = reverse('admin:%s_%s_change' % (obj.session.subject._meta.app_label,
                                              obj.session.subject._meta.model_name),
                      args=[obj.session.subject.id])
        return format_html('<b><a href="{url}" ">{}</a></b>', obj.session.subject, url=url)
    _subject.short_descritption = 'subject'


class ChronicInsertionAdmin(BaseAdmin):
    exclude = ['end_time', 'json']
    readonly_fields = ['id', '_probes']
    search_fields = ('subject__nickname', 'probe_insertion__pk', 'id')
    inlines = (TrajectoryEstimateInline, NoteInline)

    def _probes(self, obj):
        # this is to provide a link back to the session page
        html = ""
        for pr in obj.probe_insertion.all().order_by('session__start_time'):
            url = reverse('admin:%s_%s_change' % (pr._meta.app_label,
                                                  pr._meta.model_name), args=[pr.id])
            html += format_html('<a href="{url}" ">{} {}</a><br></br>',
                                pr.name, pr.session, url=url)
        return SafeString(html)
    _probes.short_descritption = 'probes'


class ProbeModelAdmin(BaseAdmin):
    pass


class ChannelAdmin(BaseAdmin):
    list_display = ['trajectory_estimate', 'x', 'y', 'z', 'brain_region', 'axial', 'lateral']
    search_fields = ('trajectory_estimate__pk',)
    readonly_fields = ['trajectory_estimate', 'brain_region']


class TrajectoryEstimateAdmin(BaseAdmin):
    exclude = ['probe_insertion']
    readonly_fields = ['datetime', '_probe_insertion', '_chronic_insertion', 'session',
                       '_channel_count']
    list_display = ['datetime', 'subject', '_probe_insertion', '_chronic_insertion',
                    'provenance', '_channel_count',
                    'x', 'y', 'z', 'depth', 'theta', 'phi', 'session']
    list_editable = ['x', 'y', 'z', 'depth', 'theta', 'phi']
    list_display_links = ('datetime', 'subject', 'session',)
    ordering = ['-provenance', '-probe_insertion__session__start_time']
    search_fields = ('probe_insertion__session__subject__nickname',
                     'chronic_insertion__subject__nickname',)

    def _chronic_insertion(self, obj):
        if obj.chronic_insertion:
            # this is to provide a link back to the session page
            url = reverse('admin:%s_%s_change' % (obj.chronic_insertion._meta.app_label,
                                                  obj.chronic_insertion._meta.model_name),
                          args=[obj.chronic_insertion.id])
            return format_html('<b><a href="{url}" ">{}</a></b>',
                               obj.chronic_insertion.name, url=url)

    def _probe_insertion(self, obj):
        if obj.probe_insertion:
            # this is to provide a link back to the session page
            url = reverse('admin:%s_%s_change' % (obj.probe_insertion._meta.app_label,
                                                  obj.probe_insertion._meta.model_name),
                          args=[obj.probe_insertion.id])
            return format_html('<b><a href="{url}" ">{}</a></b>',
                               obj.probe_insertion.name, url=url)
    _probe_insertion.short_description = 'probe'

    def _channel_count(self, obj):
        count = obj.channels.all().count()
        if count:
            info = (Channel._meta.app_label, Channel._meta.model_name)
            url = reverse('admin:%s_%s_changelist' % info)
            return format_html('<b><a href="{url}?q={pk}" ">{}</a></b>', count,
                               pk=obj.id, url=url)
        else:
            return count
    _channel_count.short_description = 'channel count'


class BrainRegionsAdmin(MPTTModelAdmin):
    list_display = ['name', 'id', 'acronym', '_parent', 'level', 'description']
    list_display_links = ('id', 'name', '_parent')
    search_fields = ('name', 'acronym', 'parent__name', 'id', 'description')
    readonly_fields = ('id', 'name', 'acronym', '_parent', 'ontology', 'level',
                       '_related_descriptions')
    exclude = ('parent',)

    def _parent(self, obj):
        if obj.parent is None:
            return
        url = reverse('admin:%s_%s_change' % (obj._meta.app_label,
                                              obj._meta.model_name), args=[obj.parent.id])
        return format_html("<a href='{url}'>{} ({})</a>", str(obj.parent),
                           str(obj.parent.id if obj.parent else ''), url=url)

    def _related_descriptions(self, obj):
        descriptions = obj.related_descriptions
        return "\n\n".join(["{} (id: {}, level:{}): \n {}".format(
            d['name'], d['id'], d['level'], d['description']) for d in descriptions])


class FOVLocationInline(TabularInline):
    show_change_link = True
    model = FOVLocation
    exclude = ('name', 'json', 'x', 'y', 'z')
    readonly_fields = ('_x', '_y', '_z', 'n_xyz')
    list_display = ('_x', '_y', '_z')

    @staticmethod
    def _x(obj):
        return ', '.join(map('{:.1f}'.format, obj.x))

    @staticmethod
    def _y(obj):
        return ', '.join(map('{:.1f}'.format, obj.y))

    @staticmethod
    def _z(obj):
        return ', '.join(map('{:.1f}'.format, obj.z))


class FOVInline(BaseAdmin):
    ordering = ('-session__start_time',)
    exclude = ('session', 'datasets')
    readonly_fields = ('id', '_session', '_datasets')
    list_display = ('name', '_subject', '_session', 'imaging_type')
    list_display_links = ('name', '_subject', '_session',)
    search_fields = ('session__subject__nickname', 'session__pk', 'id', 'imaging_type__name')
    inlines = (FOVLocationInline, NoteInline)

    def _session(self, obj):
        # this is to provide a link back to the session page
        url = reverse('admin:%s_%s_change' % (obj.session._meta.app_label,
                                              obj.session._meta.model_name),
                      args=[obj.session.id])
        return format_html('<b><a href="{url}" ">{}</a></b>', obj.session, url=url)
    _session.short_description = 'imaging session'

    def _datasets(self, obj):
        # this is to provide a link back to the session page
        html = ""
        for dset in obj.datasets.all().order_by('collection', 'name'):
            url = reverse('admin:%s_%s_change'
                          % (dset._meta.app_label, dset._meta.model_name), args=[dset.id])
            html += format_html('<a href="{url}" ">./{}/{}</a><br></br>',
                                dset.collection, dset.name, url=url)
        return SafeString(html)
    _datasets.short_descritption = 'datasets'

    def _subject(self, obj):
        # this is to provide a link back to the _subject page
        url = reverse('admin:%s_%s_change' % (obj.session.subject._meta.app_label,
                                              obj.session.subject._meta.model_name),
                      args=[obj.session.subject.id])
        return format_html('<b><a href="{url}" ">{}</a></b>', obj.session.subject, url=url)
    _subject.short_descritption = 'subject'


admin.site.register(BrainRegion, BrainRegionsAdmin)
admin.site.register(TrajectoryEstimate, TrajectoryEstimateAdmin)
admin.site.register(ProbeInsertion, ProbeInsertionInline)
admin.site.register(ProbeModel, ProbeModelAdmin)
admin.site.register(ChronicInsertion, ChronicInsertionAdmin)
admin.site.register(CoordinateSystem, BaseAdmin)
admin.site.register(Channel, ChannelAdmin)
admin.site.register(FOV, FOVInline)
