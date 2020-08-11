from django.contrib import admin
from django.utils.html import format_html

from jobs.models import Task
from alyx.base import BaseAdmin, get_admin_url


class TaskAdmin(BaseAdmin):
    exclude = ['json']
    readonly_fields = ['session', 'log', 'parents']
    list_display = ['name', 'graph', 'status_str', 'datetime', 'session_str', 'version', 'level']
    search_fields = ('graph', 'session__lab__name', 'session__subject__nickname')
    ordering = ('-session__start_time',)

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj:
            return obj.session.lab.name in request.user.lab

    def session_str(self, obj):
        url = get_admin_url(obj.session)
        return format_html('<a href="{url}">{session}</a>', session=obj.session or '-', url=url)
    session_str.short_description = 'session'

    def status_str(self, obj):
        black, green, orange, red = ('000000', '008000', 'FF7F50', 'FF0000')
        if obj.status == 40:  # error
            col = red
        elif obj.status == 50:  # empty
            col = orange
        elif obj.status == 60:  # complete
            col = green
        else:
            col = black
        return format_html(
            '<b><a style="color: #{};">{}</a></b>', col, '{}'.format(obj.get_status_display()))
    status_str.short_description = 'status'


admin.site.register(Task, TaskAdmin)
