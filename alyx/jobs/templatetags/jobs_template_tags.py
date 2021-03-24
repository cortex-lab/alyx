from django import template
from django.urls import reverse
from django.utils.html import format_html
register = template.Library()


@register.filter
def index(indexable, i):
    return indexable[i]


@register.filter
def filter_tasks(tasks, task_list):
    """
    tabulate the tasks according to the task_list header
    """
    qs = [tasks.filter(name=n) for n in task_list]
    return list(map(lambda o: o[0] if o else None, qs))


@register.filter
def get_admin_url(obj):
    if not obj:
        return '#'
    info = (obj._meta.app_label, obj._meta.model_name)
    url = reverse('admin:%s_%s_change' % info, args=(obj.pk,))
    return url
