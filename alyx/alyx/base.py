import logging
import uuid
from polymorphic.models import PolymorphicModel

from django import forms
from django.db import models
from django.conf import settings
from django.conf.locale.en import formats as en_formats
from django.contrib import admin
from django.contrib.postgres.fields import JSONField
from django.core.mail import send_mail
from django.template.response import TemplateResponse

logger = logging.getLogger(__name__)
en_formats.DATETIME_FORMAT = "d/m/Y H:i"


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


class DefaultListFilter(admin.SimpleListFilter):
    # Default filter value.
    # http://stackoverflow.com/a/16556771/1595060
    def choices(self, cl):
        for lookup, title in self.lookup_choices:
            yield {
                'selected': self.value() == lookup,
                'query_string': cl.get_query_string({
                    self.parameter_name: lookup,
                }, []),
                'display': title,
            }


def alyx_mail(to, subject, text=''):
    if not to:
        return
    if not isinstance(to, (list, tuple)):
        to = [to]
    text += '\n\n--\nMessage sent automatically - please do not reply.'
    try:
        send_mail('[alyx] ' + subject, text,
                  settings.SUBJECT_REQUEST_EMAIL_FROM,
                  to,
                  fail_silently=True,
                  )
        logger.debug("Mail sent to %s.", ', '.join(to))
    except Exception as e:
        logger.warn("Mail failed: %s", e)


ADMIN_PAGES = [('Common', ['Subjects',
                           'Surgeries',
                           'Breeding pairs',
                           'Litters',
                           'Water administrations',
                           'Water restrictions',
                           'Weighings',
                           'Subject requests',
                           ]),
               ('Data that changes rarely',
                ['Lines',
                 'Strains',
                 'Alleles',
                 'Sequences',
                 'Sources',
                 'Species',
                 'Virus injections',
                 'Other actions',
                 'Procedure types',
                 ]),
               ('Other', ['Sessions',
                          'Genotype tests',
                          'Zygosities',
                          ]),
               ('IT admin', ['Tokens',
                             'Groups',
                             'Users',
                             'Stock managers',
                             ]),
               ]


class Bunch(dict):
    def __init__(self, *args, **kwargs):
        super(Bunch, self).__init__(*args, **kwargs)
        self.__dict__ = self


def flatten(l):
    return [item for sublist in l for item in sublist]


def _get_category_list(app_list):
    order = ADMIN_PAGES
    extra_in_common = ['Adverse effects', 'Cull subjects']
    order_models = flatten([models for app, models in order])
    models_dict = {str(model['name']): model
                   for app in app_list
                   for model in app['models']}
    model_to_app = {str(model['name']): str(app['name'])
                    for app in app_list
                    for model in app['models']}
    category_list = [Bunch(name=name,
                           models=[models_dict[m] for m in model_names],
                           collapsed='' if name == 'Common' else 'collapsed'
                           )
                     for name, model_names in order]
    for model_name, app_name in model_to_app.items():
        if model_name in order_models:
            continue
        if model_name.startswith('Subject') or model_name in extra_in_common:
            category_list[0].models.append(models_dict[model_name])
        elif app_name == 'Equipment':
            category_list[1].models.append(models_dict[model_name])
        else:
            category_list[2].models.append(models_dict[model_name])
    return category_list


class MyAdminSite(admin.AdminSite):
    def index(self, request, extra_context=None):
        category_list = _get_category_list(self.get_app_list(request))
        context = dict(
            self.each_context(request),
            title=self.index_title,
            app_list=category_list,
        )
        context.update(extra_context or {})
        request.current_app = self.name

        return TemplateResponse(request, self.index_template or 'admin/index.html', context)


class BaseAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(
                           attrs={'rows': 8,
                                  'cols': 60})},
        JSONField: {'widget': forms.Textarea(
                    attrs={'rows': 5,
                           'cols': 50})},
    }
    list_per_page = 50

    def __init__(self, *args, **kwargs):
        if self.fields and 'json' not in self.fields:
            self.fields += ('json',)
        super(BaseAdmin, self).__init__(*args, **kwargs)

    def changelist_view(self, request, extra_context=None):
        category_list = _get_category_list(admin.site.get_app_list(request))
        extra_context = extra_context or {}
        extra_context['mininav'] = [('', '-- jump to --')]
        extra_context['mininav'] += [(model['admin_url'], model['name'])
                                     for model in category_list[0].models]
        return super(BaseAdmin, self).changelist_view(request, extra_context=extra_context)


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
