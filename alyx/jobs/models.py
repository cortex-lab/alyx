import uuid

from django.db import models

from data.models import DataRepository
from actions.models import Session
from alyx.base import BaseModel


class Task(BaseModel):
    """
    Provides a model for a Job, with priorities and resources
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128, unique=True)
    parents = models.ManyToManyField('self', blank=True, related_name='children',
                                     symmetrical=False)
    priority = models.SmallIntegerField(blank=True, null=True)
    io_charge = models.SmallIntegerField(blank=True, null=True)
    level = models.SmallIntegerField(blank=True, null=True)
    gpu = models.SmallIntegerField(blank=True, null=True)
    cpu = models.SmallIntegerField(blank=True, null=True)
    ram = models.SmallIntegerField(blank=True, null=True)
    pipeline = models.CharField(max_length=128, blank=True, null=True,
                                help_text="This is usually the Python module name on the workers")

    def __str__(self):
        return self.name


class Job(BaseModel):
    """
    Describes a job, which is an instance of a Task
    """
    STATUS_DATA_SOURCES = [
        (10, 'Waiting',),
        (20, 'Ready',),
        (30, 'Started',),
        (40, 'Errored',),
        (50, 'Complete',),
    ]
    session = models.ForeignKey(Session, blank=True, null=True,
                                on_delete=models.CASCADE,
                                related_name='jobs')
    # data repository will serve as a filter for local servers to get awaiting jobs
    data_repository = models.ForeignKey(DataRepository, blank=True, null=True,
                                        on_delete=models.CASCADE,
                                        related_name='jobs')
    status = models.IntegerField(default=10, choices=STATUS_DATA_SOURCES)
    log = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(null=True, blank=True, auto_now=True)

    task = models.ForeignKey(Task, null=True, blank=True,
                             on_delete=models.CASCADE)

    version = models.CharField(blank=True, null=True, max_length=64,
                               help_text="version of the algorithm generating the file")

    def __str__(self):
        return self.name + '  ' + str(self.session)

    @property
    def parents(self):
        jobs = Job.objects.filter(task__in=self.task.parent.all(), session=self.session)
        return jobs.values_list('pk', flat=True)

    @property
    def level(self):
        return self.task.level

    @property
    def pipeline(self):
        return self.task.pipeline

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['task', 'session'],
                                    name='unique_job_task_per_session')
        ]
