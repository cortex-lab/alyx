import uuid
from django.db import models
from django.contrib.postgres.fields import JSONField, ArrayField

class BrainLocation(models.Model):
    """Gives a brain location in stereotaxic coordinates, plus other information about location."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    stereotaxic_coordinates = ArrayField(models.FloatField(blank=True, null=True), size=3) # [Anterior, Right, Down], relative to bregma in µm
    description = models.TextField() # e.g. area, layer, comments on how estimated
    allen_location_ontology = models.CharField(max_length=255, null=True, blank=True) # using their vocabulary

    def __str__(self):
        return self.name

class CoordinateTransformation(models.Model):
    """
    This defines how to convert from a local coordinate system (e.g. of a silicon probe) to stereotaxic coordinates.
    It is an affine transformation:
    stereotaxic_coordinates = origin + transformation_matrix*local_coordinates.
    The decription and allen_location_ontology apply to the coordinate origin (e.g. electrode tip).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    allen_location_ontology = models.CharField(max_length=1000)

    origin = ArrayField(models.FloatField(blank=True, null=True), size=3)
    transformation_matrix = ArrayField(ArrayField(models.FloatField(blank=True, null=True), size=3), size=3)

    def __str__(self):
        return self.name