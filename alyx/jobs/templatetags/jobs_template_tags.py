from django import template
from django.urls import reverse
from django.utils.safestring import mark_safe
register = template.Library()


@register.filter
def index(indexable, i):
    return indexable[i]


@register.filter(name='zip')
def zip_lists(a, b):
    return zip(a, b)


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
def get_session_path_with_eid(obj):
    lab = obj.subject.lab.name
    path = obj.__str__()[37:]
    eid = obj.id

    return mark_safe(f'{eid} {lab}/{path}')


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


@register.simple_tag(takes_context=True)
def param_replace(context, **kwargs):
    """
    Return encoded URL parameters that are the same as the current
    request's parameters, only with the specified GET parameters added or changed.
    It also removes any empty parameters to keep things neat,
    so you can remove a parm by setting it to ``""``.
    For example, if you're on the page ``/things/?with_frosting=true&page=5``,
    then
    <a href="/things/?{% param_replace page=3 %}">Page 3</a>
    would expand to
    <a href="/things/?with_frosting=true&page=3">Page 3</a>
    Based on
    https://stackoverflow.com/questions/22734695/next-and-before-links-for-a-django-paginated-query/22735278#22735278
    """
    d = context['request'].GET.copy()
    for k, v in kwargs.items():
        d[k] = v
    for k in [k for k, v in d.items() if not v]:
        del d[k]
    return d.urlencode()
