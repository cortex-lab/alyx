import logging
import os.path as op
from polymorphic.models import PolymorphicModel
import uuid
import sys

from django import forms
from django.db import models
from django.db import connection
from django.conf import settings
from django.contrib import admin
from django.contrib.postgres.fields import JSONField
from django.core.mail import send_mail
from django.core.management import call_command
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import termcolors

from dateutil.parser import parse
from reversion.admin import VersionAdmin
from rest_framework.test import APITestCase


logger = logging.getLogger(__name__)

DATA_DIR = op.abspath(op.join(op.dirname(__file__), '../../data'))


class QueryPrintingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        if settings.DEBUG:
            self.start = 0

    def __call__(self, request):

        response = self.get_response(request)

        if settings.DEBUG and 'runserver' in sys.argv and self.start is not None:
            red = termcolors.make_style(opts=('bold',), fg='red')
            yellow = termcolors.make_style(opts=('bold',), fg='yellow')

            count = len(connection.queries) - self.start
            output = '# queries: %s' % count
            output = output.ljust(18)

            # add some colour
            if count > 100:
                output = red(output)
            elif count > 10:
                output = yellow(output)

            # runserver just prints its output to sys.stderr, so follow suite
            sys.stderr.write(output)

        return response


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, blank=True, help_text="Long name")
    json = JSONField(null=True, blank=True,
                     help_text="Structured data, formatted in a user-defined way")

    class Meta:
        abstract = True


def modify_fields(**kwargs):
    def wrap(cls):
        for field, prop_dict in kwargs.items():
            for prop, val in prop_dict.items():
                setattr(cls._meta.get_field(field), prop, val)
        return cls
    return wrap


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
               ('Data files',
                ['Data repository types',
                 'Data repositories',
                 'Data formats',
                 'Dataset types',
                 'Datasets',
                 'File records',
                 'Data collections',
                 'Time series',
                 'Event series',
                 'Interval series',
                 ]),
               ('Data that changes rarely',
                ['Lines',
                 'Strains',
                 'Alleles',
                 'Sequences',
                 'Sources',
                 'Species',
                 'Other actions',
                 'Procedure types',
                 ]),
               ('Other', ['Sessions',
                          'Genotype tests',
                          'Zygosities',
                          ]),
               ('IT admin', ['Tokens',
                             'Groups',
                             'Lab members',
                             'Labs',
                             'Lab locations',
                             'Lab memberships',
                             ]),
               ]


class Bunch(dict):
    def __init__(self, *args, **kwargs):
        super(Bunch, self).__init__(*args, **kwargs)
        self.__dict__ = self


def flatten(l):
    return [item for sublist in l for item in sublist]


def _show_change(date_time, old, new):
    date_time = parse(date_time)
    return '%s: %s ⇨ %s' % (
        date_time.strftime("%d/%m/%Y at %H:%M"), str(old), str(new))


def _iter_history_changes(obj, field):
    changes = obj.json.get('history', {}).get(field, [])
    for d1, d2 in zip(changes, changes[1:]):
        yield _show_change(d1['date_time'], d1['value'], d2['value'])
    # Last change to current value.
    if changes:
        d = changes[-1]
        current = getattr(obj, field, None)
        yield _show_change(d['date_time'], d['value'], current)


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
                           models=[models_dict[m] for m in model_names if m in models_dict],
                           collapsed='' if name == 'Common' else 'collapsed'
                           )
                     for name, model_names in order]
    for model_name, app_name in model_to_app.items():
        if model_name in order_models:
            continue
        if model_name.startswith('Subject') or model_name in extra_in_common:
            category_list[0].models.append(models_dict[model_name])
        else:
            category_list[3].models.append(models_dict[model_name])
    return category_list


def get_admin_url(obj):
    if not obj:
        return '#'
    info = (obj._meta.app_label, obj._meta.model_name)
    return reverse('admin:%s_%s_change' % info, args=(obj.pk,))


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


class BaseAdmin(VersionAdmin):
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(
                           attrs={'rows': 8,
                                  'cols': 60})},
        JSONField: {'widget': forms.Textarea(
                    attrs={'rows': 5,
                           'cols': 50})},
        models.UUIDField: {'widget': forms.TextInput(attrs={'size': 32})},
    }
    list_per_page = 50
    save_on_top = True
    show_full_result_count = False

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
    show_change_link = True
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(
                           attrs={'rows': 3,
                                  'cols': 30})},
        JSONField: {'widget': forms.Textarea(
                    attrs={'rows': 3,
                           'cols': 30})},
        models.CharField: {'widget': forms.TextInput(attrs={'size': 16})},
    }


class BaseTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('loaddata', op.join(DATA_DIR, 'all_dumped_anon.json.gz'), verbosity=1)

    def ar(self, r, code=200):
        self.assertTrue(r.status_code == code, r.data)


mysite = MyAdminSite()
mysite.site_header = 'Alyx'
mysite.site_title = 'Alyx'
mysite.site_url = None
mysite.index_title = 'Welcome to Alyx'

admin.site = mysite
