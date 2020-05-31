from django.contrib import admin

from jobs.models import Task
from alyx.base import BaseAdmin


class TaskAdmin(BaseAdmin):
    exclude = ['json']
    readonly_fields = ['session', 'log']
    list_display = ['status', 'session', 'version', 'level']


admin.site.register(Task, TaskAdmin)
