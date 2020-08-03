from django.db.models import Q, Count, Max
from rest_framework import generics, permissions
from django_filters.rest_framework import CharFilter
from django.views.generic.list import ListView

from alyx.base import BaseFilterSet

from misc.models import Lab
from jobs.models import Task
from jobs.serializers import TaskSerializer
from actions.models import Session


class TasksStatusView(ListView):
    template_name = 'tasks.html'
    paginate_by = 50

    def get_context_data(self, **kwargs):
        graph = self.kwargs.get('graph', None)
        context = super(TasksStatusView, self).get_context_data(**kwargs)
        context['graphs'] = list(Task.objects.all().values_list('graph', flat=True).distinct())
        # annotate the labs for template display
        cw = Count('session__tasks', filter=Q(session__tasks__status=20))
        ls = Max('session__start_time', filter=Q(session__tasks__isnull=False))
        lj = Max('session__tasks__datetime')
        context['labs'] = Lab.objects.annotate(
            count_waiting=cw, last_session=ls, last_job=lj).order_by('name')

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
        lab = self.kwargs.get('lab', None)
        qs = Session.objects.all()
        if lab:
            qs = qs.filter(lab__name=lab)
        if graph:
            qs = qs.filter(tasks__graph=self.kwargs['graph'])
        return qs.distinct().order_by("-start_time")


class TaskFilter(BaseFilterSet):
    lab = CharFilter('session__lab__name')
    status = CharFilter(method='enum_field_filter')

    class Meta:
        model = Task
        exclude = ['json']


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
