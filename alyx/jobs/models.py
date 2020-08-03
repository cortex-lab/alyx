import uuid

from django.db import models

from actions.models import Session


class Task(models.Model):
    """
    Provides a model for a Task, with priorities and resources
    """
    STATUS_DATA_SOURCES = [
        (20, 'Waiting',),
        (25, 'Held',),
        (30, 'Started',),
        (40, 'Errored',),
        (45, 'Abandoned',),
        (50, 'Empty'),
        (60, 'Complete',),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # some information for parallel runs
    name = models.CharField(max_length=64, blank=True, null=True)
    priority = models.SmallIntegerField(blank=True, null=True)
    io_charge = models.SmallIntegerField(blank=True, null=True)
    level = models.SmallIntegerField(blank=True, null=True)
    gpu = models.SmallIntegerField(blank=True, null=True)
    cpu = models.SmallIntegerField(blank=True, null=True)
    ram = models.SmallIntegerField(blank=True, null=True)
    time_out_secs = models.SmallIntegerField(blank=True, null=True)
    time_elapsed_secs = models.FloatField(blank=True, null=True)
    executable = models.CharField(max_length=128, blank=True, null=True,
                                  help_text="Usually the Python class name on the workers")
    graph = models.CharField(
        max_length=64, blank=True, null=True,
        help_text="The name of the graph containing a set of related and possibly dependent tasks")
    status = models.IntegerField(default=10, choices=STATUS_DATA_SOURCES)
    log = models.TextField(blank=True, null=True)
    session = models.ForeignKey(Session, blank=True, null=True,
                                on_delete=models.CASCADE,
                                related_name='tasks')
    version = models.CharField(blank=True, null=True, max_length=64,
                               help_text="version of the algorithm generating the file")
    # dependency pattern for the task graph
    parents = models.ManyToManyField('self', blank=True, related_name='children',
                                     symmetrical=False)
    datetime = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name + '  ' + str(self.session) + '  ' + self.get_status_display()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['name', 'session'],
                                    name='unique_task_name_per_session')
        ]
