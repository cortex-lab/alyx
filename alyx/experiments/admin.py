from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from experiments.models import ProbeInsertion
from alyx.base import BaseAdmin


class InsertionAdmin(BaseAdmin):
    ordering = ('session__start_time',)
    exclude = ['session']
    readonly_fields = ['_session']

    def _session(self, obj):

        url = reverse('admin:%s_%s_change' % (obj.session._meta.app_label,
                                              obj.session._meta.model_name),
                      args=[obj.ephys_session.id])
        return format_html('<b><a href="{url}" ">{}</a></b>', obj.session, url=url)
    _session.short_description = 'ephys session'


admin.site.register(ProbeInsertion, InsertionAdmin)
