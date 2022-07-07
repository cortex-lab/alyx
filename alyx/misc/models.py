from datetime import datetime
from io import BytesIO
import os.path as op
import uuid
import sys
import pytz

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
    allowed_users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True)
    is_public_user = models.BooleanField(default=False)

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
    repositories = models.ManyToManyField(
        'data.DataRepository', blank=True,
        help_text="Related DataRepository instances. Any file which is registered to Alyx is "
        "automatically copied to all repositories assigned to its project.")

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
    text = models.TextField(blank=True,
                            help_text="String, content of the note or description of the image.")
    image = models.ImageField(upload_to=get_image_path, blank=True, null=True)

    # Generic foreign key to arbitrary model instances.
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField(help_text="UUID, an object of content_type with this "
                                           "ID must already exist to attach a note.")
    content_object = GenericForeignKey()

    def save(self, image_width=None, **kwargs):
        if self.image and not self._state.adding and image_width != 'orig':
            # Resize image - saving
            with Image.open(self.image) as im:
                with BytesIO() as output:
                    # Compute new size by keeping the aspect ratio.
                    width = int(image_width or UPLOADED_IMAGE_WIDTH)
                    wpercent = width / float(im.size[0])
                    height = int((float(im.size[1]) * float(wpercent)))
                    im.thumbnail((width, height))
                    im.save(output, format=im.format, quality=70)
                    output.seek(0)
                    self.image = InMemoryUploadedFile(
                        output, 'ImageField', self.image.name,
                        im.format, sys.getsizeof(output), None)
                    super(Note, self).save(**kwargs)
        else:
            super(Note, self).save(**kwargs)


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
    """
    Table containing housing conditions. Subjects are linked through the HousingSubject table
    that contains the date_in / date_out for each Housing.
    NB: housing is not a physical cage, although it refers to it by cage_name.
    For history recording purposes, if an enrichment/food in a physical cage changes, then:
    1) creates a new Housing instance
    2) closes (set end_datetime) for current mice in junction table
    3) creates HousingSubject records for the current mice and new Housing
    """
    subjects = models.ManyToManyField('subjects.Subject', through='HousingSubject',
                                      related_name='housings')
    cage_name = models.CharField(max_length=64)
    cage_type = models.ForeignKey('CageType', on_delete=models.SET_NULL, null=True, blank=True)
    enrichment = models.ForeignKey('Enrichment', on_delete=models.SET_NULL, null=True, blank=True)
    food = models.ForeignKey('Food', on_delete=models.SET_NULL, null=True, blank=True)
    cage_cleaning_frequency_days = models.IntegerField(null=True, blank=True)
    light_cycle = models.IntegerField(choices=((0, 'Normal'),
                                               (1, 'Inverted'),),
                                      null=True, blank=True)

    def __str__(self):
        return self.cage_name + ' (housing: ' + str(self.pk)[:8] + ')'

    def save(self, **kwargs):
        # if this is a forced update/insert, save and continue to avoid recursion
        if kwargs.get('force_update', False) or kwargs.get('force_insert', False):
            super(Housing, self).save(**kwargs)
            return
        # first check if it's an update to an existing value, if not, just create
        housings = Housing.objects.filter(pk=self.pk)
        if not housings:
            super(Housing, self).save(**kwargs)
            return
        # so if it's an update check for field changes excluding end date which is an update
        old = Housing.objects.get(pk=self.pk)
        excludes = ['json', 'name']  # do not track changes to those fields
        isequal = True
        for f in self._meta.fields:
            if f.name in excludes:
                continue
            isequal &= getattr(old, f.name) == getattr(self, f.name)
        # in this case the housing may just have had comments or json changed
        if isequal:
            super(Housing, self).save(**kwargs)
            return
        # update fields triggers 1) the update of the current rec, 2) the creation of a new rec
        self.close_and_create()

    def close_and_create(self):
        # get the old/current object
        old = Housing.objects.get(pk=self.pk)
        subs = old.subjects.all()
        if not subs:
            return
        self.pk = None
        self.save(force_insert=True)
        subs = old.subjects_current()
        if not subs:
            return
        # 1) update of the old model(s), setting the end time
        now = datetime.now(tz=timezone.get_current_timezone())
        if subs.first().lab:
            now = now.astimezone(pytz.timezone(subs.first().lab.timezone))
        old.housing_subjects.all().update(end_datetime=now)
        # 2) update of the current model and create start time
        for sub in subs:
            HousingSubject.objects.create(subject=sub, housing=self, start_datetime=now)

    def subjects_current(self, datetime=None):
        from subjects.models import Subject
        if datetime:
            hs = self.housing_subjects.filter(end_datetime__gte=datetime)
            hs = hs.filter(start_datetime__lte=datetime)
            pass
        else:
            hs = self.housing_subjects.filter(end_datetime__isnull=True)
        return Subject.objects.filter(pk__in=hs.values_list('subject', flat=True))

    @property
    def subject_count(self):
        return self.subjects.objects.all().count()

    @property
    def lab(self):
        sub = self.subjects.first()
        if sub:
            return sub.lab.name


class HousingSubject(BaseModel):
    """
    Through model for Housing and Subjects m2m
    """
    subject = models.ForeignKey('subjects.Subject',
                                related_name='housing_subjects',
                                on_delete=models.SET_NULL,
                                null=True)
    housing = models.ForeignKey('Housing',
                                related_name='housing_subjects',
                                on_delete=models.SET_NULL,
                                null=True,
                                blank=True)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField(null=True, blank=True)

    def save(self, **kwargs):
        # if this is a forced update, save and continue to avoid recursion
        if kwargs.get('force_update', False):
            super(HousingSubject, self).save(**kwargs)
            return
        old = HousingSubject.objects.filter(pk=self.pk)
        # if the subject is in another housing, close the other
        if not self.end_datetime:
            hs = HousingSubject.objects.filter(subject=self.subject, end_datetime__isnull=True
                                               ).exclude(pk__in=old.values_list('pk', flat=True))
            hs.update(end_datetime=self.start_datetime)
        # if this is a modification of an existing object, force update the old and force insert
        if old:
            old[0].end_datetime = self.start_datetime
            super(HousingSubject, self).save(force_update=True)  # self.save(force_insert=True)
            return
        super(HousingSubject, self).save(**kwargs)
