from rest_framework import generics, permissions

from jobs.models import Task
from jobs.serializers import TaskSerializer
from django_filters.rest_framework import CharFilter

from alyx.base import BaseFilterSet


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
    queryset = Task.objects.all().order_by('priority', 'level')
    serializer_class = TaskSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_class = TaskFilter


class TaskDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = (permissions.IsAuthenticated,)
