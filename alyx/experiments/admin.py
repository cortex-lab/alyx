from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.contrib.admin import TabularInline

from experiments.models import TrajectoryEstimate, ProbeInsertion, ProbeModel
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


admin.site.register(ProbeInsertion, ProbeInsertionInline)
admin.site.register(ProbeModel, ProbeModelAdmin)
