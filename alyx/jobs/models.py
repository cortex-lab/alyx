import uuid

from django.db import models

from data.models import DataRepository, Dataset
from actions.models import Session
from alyx.base import BaseModel


class Task(BaseModel):
    """
    Provides a model for a Job, with priorities and resources
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128)
    parent = models.ManyToManyField('self', on_delete=models.CASCADE, null=True, blank=True,
                                    related_name='children')
    priority = models.SmallIntegerField(blank=True, null=True)
    io_charge = models.SmallIntegerField(blank=True, null=True)
    gpu = models.SmallIntegerField(blank=True, null=True)
    cpu = models.SmallIntegerField(blank=True, null=True)
    pipeline = models.CharField(max_length=128, blank=True, null=True)

    def __str__(self):
        return self.name


class Job(BaseModel):
    """
    Describes a job, which is an instance of a Task
    """
    STATUS_DATA_SOURCES = [
        (10, 'Waiting',),
        (20, 'Ready',),
        (30, 'Running',),
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
    log = models.ForeignKey(Dataset, blank=True, null=True,
                            on_delete=models.SET_NULL,
                            related_name='job')
    timestamp = models.DateTimeField(null=True, blank=True, auto_now=True)

    task = models.ForeignKey(Task, null=True, blank=True,
                             on_delete=models.SET_NULL)

    version = models.CharField(blank=True, null=True, max_length=64,
                               help_text="version of the algorithm generating the file")

    def __str__(self):
        return self.name + '  ' + str(self.session)
