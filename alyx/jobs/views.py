from rest_framework import generics, permissions

from django_filters.rest_framework import CharFilter
from django.views.generic.list import ListView

from alyx.base import BaseFilterSet

from jobs.models import Task
from jobs.serializers import TaskSerializer
from actions.models import Session


class TasksStatusView(ListView):
    template_name = 'tasks.html'

    def get_context_data(self, **kwargs):
        graph = self.kwargs.get('graph', None)
        context = super(TasksStatusView, self).get_context_data(**kwargs)
        context['graphs'] = list(Task.objects.all().values_list('graph', flat=True).distinct())
        if graph:
            context['task_names'] = list(Task.objects.filter(graph=graph).values_list(
                'name', flat=True).distinct())
            context['task_names'].sort()
        else:
            context['task_names'] = []
        context['title'] = 'Tasks Recap'
        context['site_header'] = 'Alyx'
        return context

    def get_queryset(self):
        graph = self.kwargs.get('graph', None)
        if graph:
            return Session.objects.filter(
                tasks__graph=self.kwargs['graph']).distinct().order_by("-start_time")


class TaskFilter(BaseFilterSet):
    lab = CharFilter('session__lab__name')
    status = CharFilter(method='status_filter')

    class Meta:
        model = Task
        exclude = ['json']

    def status_filter(self, queryset, name, value):
        choices = Task._meta.get_field('status').choices
        # create a dictionary string -> integer
        value_map = {v.lower(): k for k, v in choices}
        # get the integer value for the input string
        try:
            value = value_map[value.lower().strip()]
        except KeyError:
            raise ValueError("Invalid status, choices are: " +
                             ', '.join([ch[1] for ch in choices]))
        return queryset.filter(status=value)


class TaskList(generics.ListCreateAPIView):
    """
    get: **FILTERS**
    -   **task**: task name `/jobs?task=EphysSyncPulses`
    -   **session**: uuid `/jobs?session=aad23144-0e52-4eac-80c5-c4ee2decb198`
    -   **lab**: lab name from session table `/jobs?lab=churchlandlab`
    -   **pipeline**: pipeline field from task `/jobs?pipeline=ephys`
    """
    queryset = Task.objects.all().order_by('level', '-priority', '-session__start_time')
    serializer_class = TaskSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_class = TaskFilter


class TaskDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = (permissions.IsAuthenticated,)
