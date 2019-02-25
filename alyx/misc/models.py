from datetime import datetime
from io import BytesIO
import os.path as op
import uuid
import sys
import pytz
from collections.abc import Iterable

from PIL import Image

from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils import timezone

from alyx.base import BaseModel, modify_fields
from alyx.settings import TIME_ZONE, UPLOADED_IMAGE_WIDTH, DEFAULT_LAB_PK


def default_lab():
    return DEFAULT_LAB_PK


class LabMember(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    is_stock_manager = models.BooleanField(default=False)

    class Meta:
        ordering = ['username']

    def lab_id(self, date=datetime.now().date()):
        lms = LabMembership.objects.filter(user=self.pk, start_date__lte=date)
        lms = lms.exclude(end_date__lt=date)
        return Lab.objects.filter(id__in=lms.values_list('lab', flat=True))

    @property
    def lab(self, date=datetime.now().date()):
        labs = self.lab_id(date=date)
        return [str(ln[0]) for ln in labs.values_list('name').distinct()]

    @property
    def tz(self):
        labs = self.lab_id()
        if not labs:
            return settings.TIME_ZONE
        else:
            return labs[0].timezone


class Lab(BaseModel):
    name = models.CharField(max_length=255, unique=True)
    institution = models.CharField(max_length=255, blank=True)
    address = models.CharField(max_length=255, blank=True)
    timezone = models.CharField(
        max_length=64, blank=True, default=TIME_ZONE,
        help_text="Timezone of the server "
        "(see https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)")

    reference_weight_pct = models.FloatField(
        default=0.,
        help_text="The minimum mouse weight is a linear combination of "
        "the reference weight and the zscore weight.")

    zscore_weight_pct = models.FloatField(
        default=0.,
        help_text="The minimum mouse weight is a linear combination of "
        "the reference weight and the zscore weight.")
    # those are all the default fields for populating Housing tables
    cage_type = models.ForeignKey('CageType', on_delete=models.SET_NULL, null=True, blank=True)
    enrichment = models.ForeignKey('Enrichment', on_delete=models.SET_NULL, null=True, blank=True)
    food = models.ForeignKey('Food', on_delete=models.SET_NULL, null=True, blank=True)
    cage_cleaning_frequency_days = models.IntegerField(null=True, blank=True)
    light_cycle = models.IntegerField(choices=((0, 'Normal'),
                                               (1, 'Inverted'),), null=True, blank=True)

    def __str__(self):
        return self.name


class LabMembership(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)
    role = models.CharField(max_length=255, blank=True)
    start_date = models.DateField(blank=True, null=True, default=timezone.now)
    end_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return "%s %s in %s" % (self.user, self.role, self.lab)


@modify_fields(name={
    'blank': False,
})
class LabLocation(BaseModel):
    """
    The physical location at which an session is performed or appliances are located.
    This could be a room, a bench, a rig, etc.
    """
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, default=default_lab)

    def __str__(self):
        return self.name


def get_image_path(instance, filename):
    date = datetime.now().strftime('%Y/%m/%d')
    pk = instance.object_id
    base, ext = op.splitext(filename)
    return '%s/%s.%s%s' % (date, base, pk, ext)


class Note(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date_time = models.DateTimeField(default=timezone.now)
    text = models.TextField(blank=True)
    image = models.ImageField(upload_to=get_image_path, blank=True, null=True)

    # Generic foreign key to arbitrary model instances.
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey()

    def save(self):
        if self.image:
            # Resize image
            with Image.open(self.image) as im:
                with BytesIO() as output:
                    # Compute new size by keeping the aspect ratio.
                    width = UPLOADED_IMAGE_WIDTH
                    wpercent = width / float(im.size[0])
                    height = int((float(im.size[1]) * float(wpercent)))
                    im.thumbnail((width, height))
                    im.save(output, format=im.format, quality=70)
                    output.seek(0)
                    self.image = InMemoryUploadedFile(
                        output, 'ImageField', self.image.name,
                        im.format, sys.getsizeof(output), None)
                    super(Note, self).save()
        else:
            super(Note, self).save()


class CageType(BaseModel):
    description = models.CharField(
        max_length=1023, blank=True, help_text="Extended description of the cage product/brand")

    def __str__(self):
        return self.name


class Enrichment(BaseModel):
    name = models.CharField(max_length=255, unique=True,
                            help_text="Training wheel, treadmill etc..")
    description = models.CharField(
        max_length=1023, blank=True, help_text="Extended description of the enrichment, link ...")

    def __str__(self):
        return self.name


class Food(BaseModel):
    name = models.CharField(max_length=255, unique=True,
                            help_text="Food brand and content")
    description = models.CharField(
        max_length=1023, blank=True, help_text="Extended description of the food, link ...")

    def __str__(self):
        return self.name


class Housing(BaseModel):
    subjects = models.ManyToManyField('subjects.Subject')
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField(null=True, blank=True)
    cage_name = models.CharField(max_length=64, null=True, blank=True)
    cage_type = models.ForeignKey('CageType', on_delete=models.SET_NULL, null=True, blank=True)
    enrichment = models.ForeignKey('Enrichment', on_delete=models.SET_NULL, null=True, blank=True)
    food = models.ForeignKey('Food', on_delete=models.SET_NULL, null=True, blank=True)
    cage_cleaning_frequency_days = models.IntegerField(null=True, blank=True)
    light_cycle = models.IntegerField(choices=((0, 'Normal'),
                                               (1, 'Inverted'),),
                                      null=True, blank=True)

    def save(self, **kwargs):
        # if this is a forced update/insert, save and continue
        if kwargs.get('force_update', False) or kwargs.get('force_insert', False):
            super(Housing, self).save(**kwargs)
            return

        # first check if it's an update to an existing value, if not, just save
        housings = Housing.objects.filter(pk=self.pk)
        if not housings:
            super(Housing, self).save(**kwargs)
            return

        # so if it's an update check for field changes excluding end date which is an update
        old = Housing.objects.get(pk=self.pk)
        excludes = ['start_datetime', 'end_datetime']
        isequal = True
        for f in self._meta.fields:
            if f.name in excludes:
                continue
            isequal &= getattr(old, f.name) == getattr(self, f.name)
        # in this case the housing may just have had its dates changed
        if isequal:
            super(Housing, self).save(**kwargs)
            return
        # update fields triggers 1) the update of the current rec, 2) the creation of a new rec
        self.update_and_create(old)

    def update_and_create(self, old_housings, moved_subjects_pk=None):
        if not old_housings:
            return
        # 1) update of the old model(s), setting the end time
        now = datetime.now().astimezone(timezone.get_current_timezone())
        sub = self.subjects.first()
        if sub and sub.lab:
            now.astimezone(pytz.timezone(sub.lab.timezone))
        # this needs to work for querysets and for misc.Housing objects
        if not isinstance(old_housings, Iterable):
            old_housings = [old_housings]
        for old in old_housings:
            old.end_datetime = timezone.make_naive(now)
            old.save(force_update=True)
        # 2) update of the current model
        self.pk = None
        self.start_datetime = old.end_datetime
        self.save(force_insert=True)
        # if this is an automatic subject removal, make sure the subjects are updated
        if moved_subjects_pk:
            subs = set(old.subjects.all().values_list('pk', flat=True))
            subs = subs.difference(moved_subjects_pk)
            self.subjects.set(subs)

    @property
    def mice_per_cage(self):
        return self.subjects.objects.all().count()

    @property
    def lab(self):
        sub = self.subjects.first()
        if sub:
            return sub.lab.name
