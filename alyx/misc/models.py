from datetime import datetime
from io import BytesIO
import os.path as op
import uuid
import sys

from PIL import Image

from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils import timezone

from alyx.base import BaseModel, modify_fields
from alyx.settings import TIME_ZONE, UPLOADED_IMAGE_WIDTH


class LabMember(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    is_stock_manager = models.BooleanField(default=False)

    class Meta:
        ordering = ['username']

    @property
    def lab(self, date=datetime.now().date()):
        lms = LabMembership.objects.filter(user=self.pk, start_date__lte=date)
        lms = lms.exclude(end_date__lt=date)
        return [str(ln[0]) for ln in lms.values_list('lab__name').distinct()]


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
    lab = models.ForeignKey(Lab, null=True, blank=True, on_delete=models.SET_NULL)

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
