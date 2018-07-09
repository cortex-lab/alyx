import uuid

from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone

from alyx.base import BaseModel
from alyx.settings import TIME_ZONE


class LabMember(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    is_stock_manager = models.BooleanField(default=False)

    class Meta:
        ordering = ['username']


class Lab(BaseModel):
    name = models.CharField(max_length=255, unique=True)
    institution = models.CharField(max_length=255, blank=True)
    address = models.CharField(max_length=255, blank=True)
    timezone = models.CharField(
        max_length=64, blank=True, default=TIME_ZONE,
        help_text="Timezone of the server "
        "(see https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)")

    def __str__(self):
        return self.name


class LabMembership(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)
    role = models.CharField(max_length=255, blank=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return "%s %s in %s" % (self.user, self.role, self.lab)


class Note(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date_time = models.DateTimeField(default=timezone.now)
    text = models.TextField(blank=True)

    # Generic foreign key to arbitrary model instances.
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey()


class BrainLocation(BaseModel):
    """Gives a brain location in stereotaxic coordinates, plus other information about location."""
    name = models.CharField(max_length=255)
    # [Anterior, Right, Down], relative to bregma in µm
    stereotaxic_coordinates = ArrayField(models.FloatField(blank=True, null=True), size=3)
    # e.g. area, layer, comments on how estimated
    description = models.TextField()
    # using their vocabulary
    allen_location_ontology = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name


class CoordinateTransformation(BaseModel):
    """
    This defines how to convert from a local coordinate system (e.g. of a silicon probe) to
    stereotaxic coordinates.
    It is an affine transformation:
    stereotaxic_coordinates = origin + transformation_matrix*local_coordinates.
    The decription and allen_location_ontology apply to the coordinate origin
    (e.g. electrode tip).
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    allen_location_ontology = models.CharField(max_length=1000)

    origin = ArrayField(models.FloatField(blank=True, null=True), size=3)
    transformation_matrix = ArrayField(ArrayField(models.FloatField(blank=True, null=True),
                                                  size=3), size=3)

    def __str__(self):
        return self.name
