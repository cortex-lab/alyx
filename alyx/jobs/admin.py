from django.contrib import admin

from jobs.models import Job, Task
from alyx.base import BaseAdmin


class JobAdmin(BaseAdmin):
    readonly_fields = ['session', 'log']


class TaskAdmin(BaseAdmin):
    exclude = ['json']
    list_display = ['name', 'gpu', 'cpu']


admin.site.register(Job, JobAdmin)
admin.site.register(Task, TaskAdmin)
