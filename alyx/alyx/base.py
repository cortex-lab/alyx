import uuid
from polymorphic.models import PolymorphicModel
from django.db import models
from django.contrib import admin
from django.contrib.postgres.fields import JSONField
from django import forms


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    json = JSONField(null=True, blank=True,
                     help_text="Structured data, formatted in a user-defined way")

    class Meta:
        abstract = True


class BasePolymorphicModel(PolymorphicModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    json = JSONField(null=True, blank=True,
                     help_text="Structured data, formatted in a user-defined way")

    class Meta:
        abstract = True


class BaseAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(
                           attrs={'rows': 8,
                                  'cols': 60})},
        JSONField: {'widget': forms.Textarea(
                    attrs={'rows': 5,
                           'cols': 50})},
    }

    def __init__(self, *args, **kwargs):
        if self.fields:
            self.fields += ('json',)
        super(BaseAdmin, self).__init__(*args, **kwargs)


class BaseInlineAdmin(admin.TabularInline):
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(
                           attrs={'rows': 3,
                                  'cols': 30})},
        JSONField: {'widget': forms.Textarea(
                    attrs={'rows': 3,
                           'cols': 30})},
        models.CharField: {'widget': forms.TextInput(attrs={'size': 16})},
    }
