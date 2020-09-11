import json
import logging
import os
import os.path as op
from polymorphic.models import PolymorphicModel
import sys
import pytz
import uuid
from collections import OrderedDict
from rest_framework import serializers

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
from django.utils import termcolors, timezone
from django.test import TestCase
from django_filters import CharFilter
from django_filters.rest_framework import FilterSet
from rest_framework.views import exception_handler

from dateutil.parser import parse
from reversion.admin import VersionAdmin


logger = logging.getLogger(__name__)

DATA_DIR = op.abspath(op.join(op.dirname(__file__), '../../data'))
DISABLE_MAIL = False  # used for testing


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

            # for q in connection.queries:
            #     print(q['sql'])

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
    if DISABLE_MAIL or os.getenv('DISABLE_MAIL', None):
        logger.warning("Mails are disabled by DISABLE_MAIL.")
        return
    if not to:
        return
    if to and not isinstance(to, (list, tuple)):
        to = [to]
    to = [_ for _ in to if _]
    if not to:
        return
    text += '\n\n--\nMessage sent automatically - please do not reply.'
    try:
        send_mail('[alyx] ' + subject, text,
                  settings.SUBJECT_REQUEST_EMAIL_FROM,
                  to,
                  fail_silently=True,
                  )
        logger.info("Mail sent to %s.", ', '.join(to))
        return True
    except Exception as e:
        logger.warning("Mail failed: %s", e)
        return False


ADMIN_PAGES = [('Common', ['Subjects',
                           'Cull_subjects',
                           'Sessions',
                           'Ephys sessions',
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
                 'Downloads',
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
                 'Water types',
                 'Probe models',
                 ]),
               ('Other', ['Genotype tests',
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
    # Add link to training view in 'Common' panel.
    category_list[0].models.append({
        'admin_url': reverse('training'),
        'name': 'Training view',
        'perms': {},
    })
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


class JsonWidget(forms.Textarea):
    def __init__(self, *args, **kwargs):
        kwargs['attrs'] = {'rows': 20, 'cols': 60, 'style': 'font-family: monospace;'}
        super(JsonWidget, self).__init__(*args, **kwargs)

    def format_value(self, value):
        out = super(JsonWidget, self).format_value(value)
        out = json.loads(out)
        if out and not isinstance(out, dict):
            out = json.loads(out)
        out = json.dumps(out, indent=1)
        return out


class BaseAdmin(VersionAdmin):
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(
                           attrs={'rows': 8,
                                  'cols': 60})},
        JSONField: {'widget': JsonWidget},
        models.UUIDField: {'widget': forms.TextInput(attrs={'size': 32})},
    }
    list_per_page = 50
    save_on_top = True
    show_full_result_count = False

    def __init__(self, *args, **kwargs):
        if self.fields and 'json' not in self.fields:
            self.fields += ('json',)
        super(BaseAdmin, self).__init__(*args, **kwargs)

    def get_changeform_initial_data(self, request):
        # The default start time, in the admin interface, should be in the timezone of the user.
        if not request.user.lab:
            return {}
        from misc.models import Lab
        tz = pytz.timezone(Lab.objects.get(name=request.user.lab[0]).timezone)
        assert settings.USE_TZ is False  # timezone.now() is expected to be a naive datetime
        server_tz = pytz.timezone(settings.TIME_ZONE)  # server timezone
        now = server_tz.localize(timezone.now())  # convert datetime from naive to server timezone
        now = now.astimezone(tz)  # convert to the lab timezone
        return {'start_time': now, 'created_at': now, 'date_time': now}

    def changelist_view(self, request, extra_context=None):
        category_list = _get_category_list(admin.site.get_app_list(request))
        extra_context = extra_context or {}
        extra_context['mininav'] = [('', '-- jump to --')]
        extra_context['mininav'] += [(model['admin_url'], model['name'])
                                     for model in category_list[0].models]
        return super(BaseAdmin, self).changelist_view(request, extra_context=extra_context)

    def has_change_permission(self, request, obj=None):
        if not obj:
            return True
        if request.user.is_superuser:
            return True
        # Subject associated to the object.
        subj = obj if hasattr(obj, 'responsible_user') else getattr(obj, 'subject', None)
        resp_user = getattr(subj, 'responsible_user', None)
        # List of allowed users for the subject.
        allowed = getattr(resp_user, 'allowed_users', None)
        allowed = set(allowed.all() if allowed else [])
        if resp_user:
            allowed.add(resp_user)
        # Add the responsible user or user(s) to the list of allowed users.
        if hasattr(obj, 'responsible_user'):
            allowed.add(obj.responsible_user)
        if hasattr(obj, 'user'):
            allowed.add(obj.user)
        if hasattr(obj, 'users'):
            for user in obj.users.all():
                allowed.add(user)
        return request.user in allowed


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


class BaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        globals()['DISABLE_MAIL'] = True
        call_command('loaddata', op.join(DATA_DIR, 'all_dumped_anon.json.gz'), verbosity=1)

    def ar(self, r, code=200):
        """
        Asserts that HTTP status code matches expected value and parse data with or without
         pagination
        :param r: response object
        :param code: expected HTTP response code (default 200)
        :return: data: the data structure without pagination info if paginate activated
        """
        self.assertTrue(r.status_code == code, r.data)
        pkeys = set(['count', 'next', 'previous', 'results'])
        if isinstance(r.data, OrderedDict) and set(r.data.keys()) == pkeys:
            return r.data['results']
        else:
            return r.data

    def post(self, *args, **kwargs):
        return self.client.post(*args, **kwargs, content_type='application/json')

    def patch(self, *args, **kwargs):
        return self.client.patch(*args, **kwargs, content_type='application/json')


class BaseFilterSet(FilterSet):
    """
    Base class for Alyx filters. Adds a custom django filter for extensible queries using
    Django syntax. For example this is a query on a start_time field of a REST accessible model:
    sessions?django=start_time__date__lt,2017-06-05'
    if a ~ is prepended to the field name, performs an exclude instead of a filter
    sessions?django=~start_time__date__lt,2017-06-05'
    """
    django = CharFilter(field_name='', method=('django_filter'))

    def django_filter(self, queryset, _, value):
        kwargs = _custom_filter_parser(value)
        for k in kwargs:
            if k.startswith('~'):
                queryset = queryset.exclude(**{k[1:]: kwargs[k]}).distinct()
            else:
                queryset = queryset.filter(**{k: kwargs[k]}).distinct()
        return queryset

    def enum_field_filter(self, queryset, name, value):
        """
        Method to be used in the filterset class for enum fields
        """
        choices = queryset.model._meta.get_field(name).choices
        # create a dictionary string -> integer
        value_map = {v.lower(): k for k, v in choices}
        # get the integer value for the input string
        try:
            value = value_map[value.lower().strip()]
        except KeyError:
            raise ValueError("Invalid" + name + ", choices are: " +
                             ', '.join([ch[1] for ch in choices]))
        return queryset.filter(**{name: value})

    class Meta:
        abstract = True


def base_json_filter(fieldname, queryset, _, value):
    """
    function that filters the queryset from a cutom REST query. To be used directly as
    a method for a FilterSet object. For example:
    # exact/equal lookup: "?extended_qc=qc_bool,True"
    # gte lookup: "?extended_qc=qc_pct__gte,0.5"
    # chained lookups: "?extended_qc=qc_pct__gte,0.5;qc_bool,True"
    """
    kwargs = _custom_filter_parser(value, arg_prefix=fieldname + '__')
    queryset = queryset.filter(**kwargs)
    return queryset


def split_comma_outside_brackets(value):
    """ For custom filters splits by comma if they are not whithin brackets. See
    test_base.py for examples"""
    fv = []
    word = ''
    close_char = ''
    for c in value:
        if c == ',' and close_char == '':
            fv.append(word)
            word = ''
            continue
        elif c == '[':
            close_char = ']'
        elif c == '(':
            close_char = ')'
        elif c == close_char:
            close_char = ''
        word += c
    fv.append(word)
    return fv


def _custom_filter_parser(value, arg_prefix=''):
    """
    # parses the value string provided to custom filters json and Django via REST api
    :param value: string returned by the rest request: examples:
        "qc_pct__gte,0.5,qc_bool,True"
         "myfield,[4, 9]]"
    :param arg_prefix:
    :return: dictionary that can be fed directly to a Django filter() query
    """
    # split by commas only if they are outside list brackets (I know... we all love regex)
    fv = split_comma_outside_brackets(value)
    i = 0
    out_dict = {}
    while i < len(fv):
        field, val = fv[i], fv[i + 1]
        i += 2
        if val == 'None':
            val = None
        elif val.lower() == 'true':
            val = True
        elif val.lower() == 'false':
            val = False
        elif val.replace('.', '', 1).isdigit():
            val = float(val)
        elif val.startswith(('(', '[')) and val.endswith((')', ']')):
            val = eval(val)
        out_dict[arg_prefix + field] = val
    return out_dict


class BaseSerializerEnumField(serializers.Field):
    """
    Field serializer for an int model field with enumerated choices.
    This provides the string representation of the model for the rest requests and filters
    """

    @property
    def choices(self):
        model = self.parent.Meta.model
        return model._meta.get_field(self.field_name).choices

    def to_representation(self, int_rep):
        status = [ch for ch in self.choices if ch[0] == int_rep]
        return status[0][1]

    def to_internal_value(self, str_rep):
        status = [ch for ch in self.choices if ch[1] == str_rep]
        if len(status) == 0:
            raise serializers.ValidationError("Invalid " + self.field_name + ", choices are: " +
                                              ', '.join([ch[1] for ch in self.choices]))
        return status[0][0]


def rest_filters_exception_handler(exc, context):
    """
    Custom exception handler that provides context (field names etc...) for poorly formed
    REST queries
    """
    response = exception_handler(exc, context)

    from rest_framework.response import Response
    # Now add the HTTP status code to the response.
    if response is not None:
        response.data['status_code'] = response.status_code
    else:
        data = {'status_code': 500, 'detail': str(exc)}
        response = Response(data, status=500)

    return response


mysite = MyAdminSite()
mysite.site_header = 'Alyx'
mysite.site_title = 'Alyx'
mysite.site_url = None
mysite.index_title = 'Welcome to Alyx'

admin.site = mysite
