from django.contrib import admin

from jobs.models import Task
from alyx.base import BaseAdmin


class TaskAdmin(BaseAdmin):
    exclude = ['json']
    readonly_fields = ['session', 'log', 'parents']
    list_display = ['name', 'status', 'session', 'version', 'level']

    # this is a ready-only interface
    def has_change_permission(self, request, obj=None):
        return False


admin.site.register(Task, TaskAdmin)
