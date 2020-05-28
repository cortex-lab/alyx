from rest_framework import generics, permissions

from jobs.models import Job, Task
from jobs.serializers import JobSerializer, TaskSerializer
from django_filters.rest_framework import CharFilter

from alyx.base import BaseFilterSet


class JobFilter(BaseFilterSet):
    data_repository = CharFilter('data_repository__name')
    lab = CharFilter('session__lab__name')
    task = CharFilter('task__name')
    pipeline = CharFilter(field_name='task__pipeline', lookup_expr='iexact')
    status = CharFilter(method='status_filter')

    class Meta:
        model = Job
        exclude = ['json']

    def status_filter(self, queryset, name, value):
        choices = Job._meta.get_field('status').choices
        # create a dictionary string -> integer
        value_map = {v.lower(): k for k, v in choices}
        # get the integer value for the input string
        try:
            value = value_map[value.lower().strip()]
        except KeyError:
            raise ValueError("Invalid status, choices are: " +
                             ', '.join([ch[1] for ch in choices]))
        return queryset.filter(status=value)


class JobList(generics.ListCreateAPIView):
    """
    get: **FILTERS**
    -   **task**: task name `/jobs?task=EphysSyncPulses`
    -   **data_repository**: data_repository name `/jobs?data_repository=my_repo`
    -   **session**: uuid `/jobs?session=aad23144-0e52-4eac-80c5-c4ee2decb198`
    -   **lab**: lab name from session table `/jobs?lab=churchlandlab`
    -   **pipeline**: pipeline field from task `/jobs?pipeline=ephys`
    """
    queryset = Job.objects.all().order_by('task__priority', 'task__level')
    serializer_class = JobSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_class = JobFilter


class JobDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    permission_classes = (permissions.IsAuthenticated,)


class TaskList(generics.ListCreateAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filter_fields = ('name', 'pipeline')


class TaskDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'name'
