from django.db import models

from data.models import DataRepository, Dataset
from actions.models import Session
from alyx.base import BaseModel


class Task(BaseModel):
    name = models.CharField(max_length=128)
    depends_on = models.ManyToManyField('self', blank=True)
    priority = models.SmallIntegerField(blank=True, null=True)
    gpu = models.SmallIntegerField(blank=True, null=True)
    cpu = models.SmallIntegerField(blank=True, null=True)

    def __str__(self):
        return self.name


class Job(BaseModel):
    """
    Describes a job
    """
    STATUS_DATA_SOURCES = [
        (10, 'Pending',),
        (20, 'Running',),
        (30, 'Errored',),
        (40, 'Complete',),
    ]

    session = models.ForeignKey(Session, blank=True, null=True,
                                on_delete=models.CASCADE,
                                related_name='jobs')
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
