import logging
import uuid

from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator, ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from mptt.models import MPTTModel, TreeForeignKey

from alyx.base import BaseModel, BaseManager
from actions.models import ChronicRecording

logger = logging.getLogger(__name__)

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


class ChronicInsertion(ChronicRecording):
    """
    Chronic insertions
    """
    serial = models.CharField(max_length=255, blank=True, help_text="Probe serial number")
    model = models.ForeignKey(ProbeModel, blank=True, null=True, on_delete=models.SET_NULL,
                              related_name='chronic_insertion')

    def __str__(self):
        return "%s %s %s" % (self.name, self.subject.nickname, self.serial)


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
    chronic_insertion = models.ForeignKey(ChronicInsertion, blank=True, on_delete=models.SET_NULL,
                                          null=True, related_name='probe_insertion')

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
    chronic_insertion = models.ForeignKey(ChronicInsertion, blank=True, null=True,
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
            models.UniqueConstraint(fields=['provenance', 'chronic_insertion'],
                                    condition=models.Q(probe_insertion__isnull=True),
                                    name='unique_trajectory_per_chronic_provenance'),
            models.UniqueConstraint(fields=['provenance', 'probe_insertion'],
                                    condition=models.Q(probe_insertion__isnull=False),
                                    name='unique_trajectory_per_provenance'),
        ]

    def __str__(self):
        if self.probe_insertion:
            return "%s  %s/%s" % \
                   (self.get_provenance_display(), str(self.session), self.probe_insertion.name)
        elif self.chronic_insertion:
            return "%s  %s/%s" % \
                   (self.get_provenance_display(), self.chronic_insertion.subject.nickname,
                    self.chronic_insertion.name)
        else:
            return super().__str__()

    @property
    def probe_name(self):
        if self.probe_insertion:
            return self.probe_insertion.name
        elif self.chronic_insertion:
            return self.chronic_insertion.name

    @property
    def session(self):
        if self.probe_insertion:
            return self.probe_insertion.session

    @property
    def subject(self):
        if self.probe_insertion:
            return self.probe_insertion.session.subject.nickname
        elif self.chronic_insertion:
            return self.chronic_insertion.subject.nickname


class FiberModel(BaseModel):  # maybe this shouldn't be based on a ProbeModel but rather have
    """
    A model for an optical fiber cannula, implanted in a brain
    as used by fiber photometry or optogenetics experiments
    """

    fiber_manufacturer = models.CharField(
        max_length=255,
        null=True,
        help_text="manufacturer's name, e.g. Doric",
    )
    fiber_model = models.CharField(
        max_length=255,
        null=True,
        help_text="manufacturer's part number e.g. MFC__mm_ZF1.25_FLT",
    )
    na = models.FloatField(null=False, help_text="numerical aperture of the fiber, e.g. .54")
    diameter = models.FloatField(null=False, help_text="fiber diameter in um, e.g. 200")
    length = models.FloatField(null=False, help_text="fiber length in mm, e.g. 6")
    tip_type = models.CharField(default="flat", null=False, help_text="fiber tip type, e.g. flat, tapered etc.")
    tip_parameter = models.FloatField(null=True, help_text="fiber shape parameter, e.g. tip angle, taper length")
    description = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="any additional description",
    )

    def __str__(self):
        # TODO here: depending on tip shape, maybe we want to include more information here
        # those two are the most important though
        return f"NA:{self.na}, diameter:{self.diameter}"


class ChronicFiberInsertion(ChronicRecording):
    """
    note: ChronicRecording is empy, this is a BaseAction
    could also just directly inherit from that, but maybe it's
    set up like this for future extensability
    TODO DOCME
    """

    model = models.ForeignKey(
        FiberModel,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="chronic_fiber_insertion",
    )

    def __str__(self):
        return "%s %s %s" % (self.name, self.subject.nickname, self.serial)


class FiberInsertion(BaseModel):
    """
    Describe an optical fiber insertion used for fiber photometry 
    recordings or optogenetics
    """

    objects = BaseManager()

    session = models.ForeignKey(
        "actions.PhotometrySession",
        blank=True,
        null=True, # these insertions have meaning on session level only, so I think it should be True
        on_delete=models.CASCADE,
        related_name="fiber_insertion",
    )

    fiber_model = models.ForeignKey(
        FiberModel,
        blank=True,
        null=False, # TODO should this be True
        on_delete=models.SET_NULL, # doesn't this clash with nullable?
        related_name="fiber_insertion", 
    )

    datasets = models.ManyToManyField(
        "data.Dataset",
        blank=True,
        related_name="fiber_insertion",
    )

    chronic_insertion = models.ForeignKey(
        ChronicFiberInsertion,
        blank=True,
        on_delete=models.SET_NULL,
        null=False,
        related_name="fiber_insertion",
    )

    auto_datetime = models.DateTimeField(
        auto_now=True,
        blank=True,
        null=True,
        verbose_name="last updated",
    )

    def __str__(self):
        return "%s %s" % (self.name, str(self.session))

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "session"],
                name="unique_fiber_insertion_name_per_session",
            )
        ]

    @property
    def subject(self):
        return self.session.subject.nickname

    @property
    def datetime(self):
        return self.session.start_time


class FiberTrajectoryEstimate(models.Model):
    """
    Describes a probe insertion trajectory - always a straight line
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    INSERTION_DATA_SOURCES = [
        # (70, 'Ephys aligned histology track',), # doesn't exist for fiber
        (50, 'Histology track',),
        # (30, 'Micro-manipulator',), # doesn't exist for fiber
        (10, 'Planned',),
    ]

    fiber_insertion = models.ForeignKey(FiberInsertion, blank=True, null=False,
                                        on_delete=models.CASCADE,
                                        related_name='fiber_trajectory_estimate')
    chronic_fiber_insertion = models.ForeignKey(ChronicFiberInsertion, blank=True, null=False,
                                          on_delete=models.CASCADE,
                                          related_name='fiber_trajectory_estimate')
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
            models.UniqueConstraint(fields=['provenance', 'chronic_fiber_insertion'],
                                    condition=models.Q(fiber_insertion__isnull=True),
                                    name='unique_fiber_trajectory_per_chronic_provenance'),
            models.UniqueConstraint(fields=['provenance', 'fiber_insertion'],
                                    condition=models.Q(fiber_insertion__isnull=False),
                                    name='unique_fiber_trajectory_per_provenance'),
        ]

    def __str__(self):
        if self.fiber_insertion:
            return f"{self.get_provenance_display()}  {self.session}/{self.fiber_insertion.name}"
        elif self.chronic_fiber_insertion:
            return f"{self.get_provenance_display()}  {self.chronic_fiber_insertion.subject.nickname}/{self.chronic_fiber_insertion.name}"
        else:
            return super().__str__()

    @property
    def probe_name(self):
        if self.fiber_insertion:
            return self.fiber_insertion.name
        elif self.chronic_fiber_insertion:
            return self.chronic_fiber_insertion.name

    @property
    def session(self):
        if self.fiber_insertion:
            return self.fiber_insertion.session

    @property
    def subject(self):
        if self.fiber_insertion:
            return self.fiber_insertion.session.subject.nickname
        elif self.chronic_fiber_insertion:
            return self.chronic_fiber_insertion.subject.nickname


class FiberTipLocation(BaseModel):
    # modelled after a "channel" in ephys
    x = models.FloatField(blank=True, null=True, help_text=X_HELP_TEXT, verbose_name='x-ml (um)')
    y = models.FloatField(blank=True, null=True, help_text=Y_HELP_TEXT, verbose_name='y-ap (um)')
    z = models.FloatField(blank=True, null=True, help_text=Z_HELP_TEXT, verbose_name='z-dv (um)')
    brain_region = models.ForeignKey(BrainRegion, default=0, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='fiber_tip_location')
    fiber_trajectory_estimate = models.ForeignKey(FiberTrajectoryEstimate, null=True, blank=True,
                                            on_delete=models.CASCADE, related_name='fiber_tip_location')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['fiber_trajectory_estimate'],
                                               name='unique_fiber_trajectory_estimate')]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.fiber_trajectory_estimate.save()  # this will bump the datetime auto-update of trajectory


class Channel(BaseModel):
    axial = models.FloatField(blank=True, null=True,
                              help_text=("Distance in micrometers along the probe from the tip."
                                         " 0 means the tip."))
    lateral = models.FloatField(blank=True, null=True, help_text=("Distance in micrometers"
                                                                  " across the probe"))
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


class ImagingType(BaseModel):
    """Imaging field of view model"""
    name = models.CharField(
        max_length=255, blank=False, null=False, unique=True, help_text='Long name')
    objects = BaseManager()

    def __str__(self):
        return self.name


class ImagingStack(BaseModel):
    """Imaging stack model

    This model has a one-to-many relationship with the FOV model. Each FOV constitutes a slice
    within the stack, its order determined by the first z coordinate (or by convention, the FOV
    name).  This allows us to associate fields of view that lie along the same z axis.  Note that
    slices are not necessarily contiguous in the raw data (e.g. a stack may comprise FOV_03,
    FOV_06, and FOV_09).
    """
    objects = BaseManager()


class FOV(BaseModel):
    """Imaging field of view model"""
    objects = BaseManager()
    session = models.ForeignKey('actions.ImagingSession', blank=True, null=False,
                                on_delete=models.CASCADE, related_name='field_of_view')
    imaging_type = models.ForeignKey(ImagingType, blank=True, null=False, on_delete=models.CASCADE,
                                     related_name='field_of_view')
    datasets = models.ManyToManyField('data.Dataset', blank=True, related_name='field_of_view')
    stack = models.ForeignKey(ImagingStack, blank=True, null=True, on_delete=models.CASCADE,
                              related_name='slices')

    @property
    def subject(self):
        return self.session.subject.nickname

    @property
    def datetime(self):
        return self.session.start_time

    class Meta:
        verbose_name = 'field of view'
        verbose_name_plural = 'fields of view'
        unique_together = ('session', 'name')
        ordering = ('session', 'name')

    def save(self, *args, **kwargs):
        """Ensure FOVs belonging to stack share the same session"""
        if self.stack and self.stack.slices.count() > 0:
            if self.session.id != FOV.objects.filter(stack=self.stack).first().session.id:
                raise ValidationError('Stack fields of view must belong to the same session')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.pk} {self.imaging_type} {self.name}'


@receiver(post_save, sender=FOV)
def update_fov_m2m_relationships_on_save(sender, instance, **kwargs):
    from data.models import Dataset
    try:
        dsets = Dataset.objects.filter(session=instance.session,
                                       collection__icontains=instance.name)
        instance.datasets.set(dsets, clear=True)
    except Exception:
        logger.warning("Skip update m2m relationship on saving FOV")


class FOVLocation(BaseModel):
    """Imaging field of view location model

    The location has a many-to-one relationship with the FOV model, and defines the brain
    coordinates and brain region(s) covered by a field of view, analogous to the ProbeInsertion
    and TragectoryEstimate relationship.  Typically a field of view has an estimated location and a
    final location determined by histology (referred to as its provenance).  For a given field of
    view there should be at most one locations where default_provenance is True. This location is
    the one used when querying brain region.

    The x, y, z coordinates comprise the coordinates of each corner pixel.  Most fields of view are
    considered to be a plane (n_xyz = [X, Y, 1]), hence there should be 4 coordinates per axis. If
    there are more than 1 pixels along the z axis, the coordinates should be considered the
    top/most shallow aspect of the volume and a further 4 coordinates can be provided for the
    bottom extent.
    """

    class Provenance(models.TextChoices):
        """How the location and brain regions were determined"""
        ESTIMATE = 'E', _('Estimate')  # e.g. centre of craniotomy measured during surgery
        FUNCTIONAL = 'F', _('Functional')  # e.g. retinotopy
        LANDMARK = 'L', _('Landmark')  # e.g. vasculature
        HISTOLOGY = 'H', _('Histology')

    objects = BaseManager()
    field_of_view = models.ForeignKey(
        FOV, null=False, on_delete=models.CASCADE, related_name='location')
    _phelp = ' / '.join([f'{s[0]}: {s[1]}' for s in Provenance.choices])
    provenance = models.CharField(
        max_length=1,
        choices=Provenance.choices,
        default=Provenance.LANDMARK,
        help_text=_phelp
    )
    default_provenance = models.BooleanField(default=False)
    coordinate_system = models.ForeignKey(CoordinateSystem, null=True, blank=True,
                                          on_delete=models.SET_NULL,
                                          help_text='3D coordinate system used.')
    auto_datetime = models.DateTimeField(auto_now=True, verbose_name='last update')

    _HELP_TEXT = ('The location in um of the top left, top right, bottom left and '
                  'bottom right pixels respectively, along the %s axis (typically the '
                  '%s extent) at the most superficial depth.  For volumetric imaging '
                  'provide four more coordinates for the deepest extent.')

    x = ArrayField(models.FloatField(blank=True, null=True), size=8, default=list,
                   help_text=_HELP_TEXT % ('x', 'medio-lateral'))
    y = ArrayField(models.FloatField(blank=True, null=True), size=8, default=list,
                   help_text=_HELP_TEXT % ('y', 'antereo-posterior'))
    z = ArrayField(models.FloatField(blank=True, null=True), size=8, default=list,
                   help_text=_HELP_TEXT % ('z', 'dorsal-ventral'))

    n_xyz = ArrayField(models.IntegerField(blank=True, null=True), size=3, default=list,
                       help_text='Number of pixels along each axis')

    brain_region = models.ManyToManyField(BrainRegion, related_name='brain_region')

    class Meta:
        verbose_name = 'field of view location'
        verbose_name_plural = 'fields of view location'
        constraints = [
            models.UniqueConstraint(fields=['provenance', 'field_of_view'],
                                    name='unique_provenance_per_field_of_view')
        ]
        ordering = ('-default_provenance',)

    def save(self, *args, **kwargs):
        """Ensure only one provenance can be set as default"""
        locations = FOVLocation.objects.filter(
            field_of_view=self.field_of_view, default_provenance=True).exclude(id=self.id)
        if self.default_provenance and locations.count() > 0:
            locations.update(default_provenance=False)
        super().save(*args, **kwargs)
