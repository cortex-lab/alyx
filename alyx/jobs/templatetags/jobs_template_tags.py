from django import template
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
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


@register.filter
def get_icon(val):
    if val:
        return mark_safe('<img src="/static/admin/img/icon-yes.svg" alt="True">')
    else:
        return mark_safe('<img src="/static/admin/img/icon-no.svg" alt="False">')


@register.simple_tag()
def get_colour(val, n_dset, n_exp_dsets):
    if val:
        return mark_safe("color:Red")
    elif n_dset < n_exp_dsets:
        return mark_safe("color:Grey")
    else:
        return mark_safe("color:MediumSeaGreen")

@register.filter
def assign_none_to_val(val):
    if not val or val == 'NOT_SET':
        return mark_safe('-')
    else:
        return val


@register.filter
def get_session_path(obj):
    lab = obj.subject.lab.name
    path = obj.__str__()[37:]

    return mark_safe(f'{lab}/{path}')

@register.filter
def get_task_colour(status):
    if status == 20:
        return "color: #79aec8"
    elif status == 25:
        return "color:Purple"
    elif status == 30:
        return "color:Black"
    elif status == 40:
        return "color:Tomato"
    elif status == 45:
        return "color:Maroon"
    elif status == 50:
        return "color:Orange"
    elif status == 60:
        return "color:MediumSeaGreen"