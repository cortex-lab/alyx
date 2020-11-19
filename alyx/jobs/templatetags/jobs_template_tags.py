from django import template
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
