import structlog
import uuid

from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver

from mptt.models import MPTTModel, TreeForeignKey

from alyx.base import BaseModel, BaseManager

logger = structlog.get_logger(__name__)

X_HELP_TEXT = ("brain surface medio-lateral coordinate (um) of"
               "the insertion, right +, relative to Bregma")
Y_HELP_TEXT = ("brain surface antero-posterior coordinate (um) of the "
               "insertion, front +, relative to Bregma")
Z_HELP_TEXT = ("brain surface dorso-ventral coordinate (um) of the insertion"
               ", up +, relative to Bregma")


class BrainRegion(MPTTModel):
    acronym = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255, unique=True)
    id = models.IntegerField(primary_key=True)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                            related_name='children')
    ontology = models.CharField(max_length=64, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name

    @property
    def related_descriptions(self):
        """ returns a string containing all descriptions from parents and childs"""
        descriptions = []
        try:
            for anc in self.get_ancestors():
                if anc.description is not None:
                    descriptions.append({'id': anc.id, 'name': str(anc),
                                         'description': anc.description, 'level': anc.level})
            for anc in self.get_descendants():
                if anc.description is not None:
                    descriptions.append({'id': anc.id, 'name': str(anc),
                                         'description': anc.description, 'level': anc.level})
        except ValueError:
            print("ERROR  " + str(self.id) + "  " + str(self.name))
        return descriptions


class CoordinateSystem(BaseModel):
    """
    Used to describe a 3D coordinate system.
    The description is expected to provide:
    -   3D origin
    -   directions of axes
    -   unit of axes
    """
    description = models.TextField(blank=True, max_length=4096, unique=True)

    def __str__(self):
        return self.name


class ProbeModel(BaseModel):
    """
    Metadata describing each probe model
    """
    probe_manufacturer = models.CharField(max_length=255)
    probe_model = models.CharField(unique=True, max_length=255,
                                   help_text="manufacturer's part number e.g. A4x8-5mm-100-20")
    description = models.CharField(max_length=255, null=True, blank=True,
                                   help_text="optional informal description e.g. "
                                   "'Michigan 4x4 tetrode'; 'Neuropixels phase 2 option 1'")

    def __str__(self):
        return self.probe_model


class ProbeInsertion(BaseModel):
    """
    Describe an electrophysiology probe insertion used for recording
    """

    objects = BaseManager()
    session = models.ForeignKey('actions.EphysSession', blank=True, null=True,
                                on_delete=models.CASCADE, related_name='probe_insertion')
    model = models.ForeignKey(ProbeModel, blank=True, null=True, on_delete=models.SET_NULL,
                              related_name='probe_insertion')
    serial = models.CharField(max_length=255, blank=True, help_text="Probe serial number")
    auto_datetime = models.DateTimeField(auto_now=True, blank=True, null=True,
                                         verbose_name='last updated')
    datasets = models.ManyToManyField('data.Dataset', blank=True, related_name='probe_insertion')
    chronic_recording = models.ForeignKey('actions.ChronicRecording', blank=True, null=True,
                                          on_delete=models.CASCADE, related_name='probe_insertion')

    def __str__(self):
        return "%s %s" % (self.name, str(self.session))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['name', 'session'],
                                    name='unique_probe_insertion_name_per_session')
        ]

    @property
    def subject(self):
        return self.session.subject.nickname

    @property
    def datetime(self):
        return self.session.start_time


@receiver(post_save, sender=ProbeInsertion)
def update_m2m_relationships_on_save(sender, instance, **kwargs):
    from data.models import Dataset
    try:
        dsets = Dataset.objects.filter(session=instance.session,
                                       collection__icontains=instance.name)
        instance.datasets.set(dsets, clear=True)
    except Exception:
        logger.warning("Skip update m2m relationship on saving ProbeInsertion")


class TrajectoryEstimate(models.Model):
    """
    Describes a probe insertion trajectory - always a straight line
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    INSERTION_DATA_SOURCES = [
        (70, 'Ephys aligned histology track',),
        (50, 'Histology track',),
        (30, 'Micro-manipulator',),
        (10, 'Planned',),
    ]

    probe_insertion = models.ForeignKey(ProbeInsertion, blank=True, null=True,
                                        on_delete=models.CASCADE,
                                        related_name='trajectory_estimate')
    x = models.FloatField(null=True, help_text=X_HELP_TEXT, verbose_name='x-ml (um)')
    y = models.FloatField(null=True, help_text=Y_HELP_TEXT, verbose_name='y-ap (um)')
    z = models.FloatField(null=True, help_text=Z_HELP_TEXT, verbose_name='z-dv (um)')
    depth = models.FloatField(null=True, help_text="probe insertion depth (um)")
    theta = models.FloatField(null=True,
                              help_text="Polar angle ie. from vertical, (degrees) [0-180]",
                              validators=[MinValueValidator(0), MaxValueValidator(180)])
    phi = models.FloatField(null=True,
                            help_text="Azimuth from right (degrees), anti-clockwise, [0-360]",
                            validators=[MinValueValidator(-180), MaxValueValidator(360)])
    roll = models.FloatField(null=True,
                             validators=[MinValueValidator(0), MaxValueValidator(360)])
    _phelp = ' / '.join([str(s[0]) + ': ' + s[1] for s in INSERTION_DATA_SOURCES])
    provenance = models.IntegerField(default=10, choices=INSERTION_DATA_SOURCES, help_text=_phelp)
    coordinate_system = models.ForeignKey(CoordinateSystem, null=True, blank=True,
                                          on_delete=models.SET_NULL,
                                          help_text='3D coordinate system used.')
    datetime = models.DateTimeField(auto_now=True, verbose_name='last update')
    json = models.JSONField(null=True, blank=True,
                            help_text="Structured data, formatted in a user-defined way")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['provenance', 'probe_insertion'],
                                    name='unique_trajectory_per_provenance')
        ]

    def __str__(self):
        return "%s  %s/%s" % \
               (self.get_provenance_display(), str(self.session), self.probe_insertion.name)

    @property
    def probe_name(self):
        return self.probe_insertion.name

    @property
    def session(self):
        return self.probe_insertion.session

    @property
    def subject(self):
        return self.probe_insertion.session.subject.nickname


class Channel(BaseModel):
    axial = models.FloatField(blank=True, null=True,
                              help_text=("Distance in micrometers along the probe from the tip."
                                         " 0 means the tip."))
    lateral = models.FloatField(blank=True, null=True, help_text=("Distance in micrometers"
                                                                  " accross the probe"))
    x = models.FloatField(blank=True, null=True, help_text=X_HELP_TEXT, verbose_name='x-ml (um)')
    y = models.FloatField(blank=True, null=True, help_text=Y_HELP_TEXT, verbose_name='y-ap (um)')
    z = models.FloatField(blank=True, null=True, help_text=Z_HELP_TEXT, verbose_name='z-dv (um)')
    brain_region = models.ForeignKey(BrainRegion, default=0, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='channels')
    trajectory_estimate = models.ForeignKey(TrajectoryEstimate, null=True, blank=True,
                                            on_delete=models.CASCADE, related_name='channels')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['axial', 'lateral', 'trajectory_estimate'],
                                               name='unique_axial_lateral_trajectory_estimate')]

    def save(self, *args, **kwargs):
        super(Channel, self).save(*args, **kwargs)
        self.trajectory_estimate.save()  # this will bump the datetime auto-update of trajectory
