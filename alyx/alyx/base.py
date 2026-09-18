import ast
import json
import logging
import os
import os.path as op
from polymorphic.models import PolymorphicModel
import sys
import pytz
import uuid
import one.alf.spec
from datetime import datetime
import traceback

from django import forms
from django.db import models
from django.db import connection
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.core.management import call_command
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.utils import termcolors, timezone
from django.test import TestCase
from django_admin_listfilter_dropdown.filters import RelatedDropdownFilter
from django_filters import CharFilter
from django_filters import rest_framework as filters
from rest_framework.views import exception_handler
from rest_framework import serializers
from rest_framework import permissions
from rest_framework.pagination import LimitOffsetPagination
from dateutil.parser import parse
from reversion.admin import VersionAdmin
from alyx import __version__ as version

logger = logging.getLogger(__name__)

DATA_DIR = op.abspath(op.join(op.dirname(__file__), '../../data'))
DISABLE_MAIL = False  # used for testing
ALF_SPEC = dict(one.alf.spec._DEFAULT)  # Regex for ALF part validation


class CharNullField(models.CharField):
    """
    Subclass of the CharField that allows empty strings to be stored as NULL.

    This allows for unique assertions on non-empty string fields only.

    See this URL:
    https://stackoverflow.com/questions/454436/unique-fields-that-allow-nulls-in-django/1934764
    """

    description = "CharField that stores NULL but returns ''."

    def from_db_value(self, value, *_):
        """
        Gets value right out of the db and changes it if it's None.
        """
        return value or ''

    def to_python(self, value):
        """
        Gets value right out of the db or an instance, and changes it if it's `None`.
        """
        if isinstance(value, models.CharField):
            # If an instance, just return the instance.
            return value
        if value is None:
            # If db has NULL, convert it to ''.
            return ''

        # Otherwise, just return the value.
        return value

    def get_prep_value(self, value):
        """
        Catches value right before sending to db.
        """
        if value == '':
            # If Django tries to save an empty string, send the db None (NULL).
            return None
        else:
            # Otherwise, just pass the value.
            return value


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
    json = models.JSONField(null=True, blank=True,
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
    json = models.JSONField(null=True, blank=True,
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


class UserRelatedDropdownFilter(RelatedDropdownFilter):
    """A user dropdown filter that does not list read-only accounts.

    The default related filter populates its dropdown from the whole target table, so a plain
    RelatedDropdownFilter on a user field lists every LabMember - including, on a public
    database with self-registration, the account of every member of the public who has signed
    up. Public accounts never own data, so they are never a useful thing to filter by; dropping
    them keeps the filter useful without turning it into a directory of registered users.
    """

    def field_choices(self, field, request, model_admin):
        ordering = self.field_admin_ordering(field, request, model_admin)
        return field.get_choices(
            include_blank=False, limit_choices_to={'is_public_user': False}, ordering=ordering)


def alyx_mail(to, subject, text=''):
    if DISABLE_MAIL or os.getenv('DISABLE_MAIL', None):
        logger.warning("Mail is disabled by DISABLE_MAIL.")
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


ADMIN_PAGES = [
    ('Subject management', [
        'Subjects', 'Subject requests', 'Cull_subjects', 'Breeding pairs', 'Litters']),
    ('Experiments', [
        'Sessions', 'Weighings', 'Water restrictions', 'Water administrations', 'Water types',
        'Surgeries', 'Procedure types', 'Notes', 'Other actions', 'Projects']),
    ('Ephys experiments', [
        'Ephys sessions', 'Probe insertions', 'Chronic insertions', 'Probe models',
        'Trajectory estimates', 'Channels']),
    ('Imaging experiments', [
        'Imaging sessions', 'Fields of view']),  # May add 'Imaging type'
    ('Data files', [
        'Data repository types', 'Data repositories', 'Tasks', 'Data formats', 'Dataset types',
        'Datasets', 'File records', 'Tags', 'Revisions', 'Data notices', 'Downloads']),
    ('Subject genetics', [
        'Lines', 'Strains', 'Alleles', 'Sequences', 'Sources', 'Species',
        'Genotypes', 'Genotype tests', 'Zygosities', 'Zygosity tests']),
    ('Subject housing', ['Cage types', 'Housings', 'Foods', 'Enrichments']),
    ('Other', []),
    ('Lab admin', [
        'Groups', 'Lab members', 'Labs', 'Lab locations', 'Lab memberships']),
]


class Bunch(dict):
    def __init__(self, *args, **kwargs):
        super(Bunch, self).__init__(*args, **kwargs)
        self.__dict__ = self


def flatten(liste):
    return [item for sublist in liste for item in sublist]


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
    # Add custom URL query params to 'Adverse effects' link
    if 'Adverse effects' in models_dict:
        models_dict['Adverse effects']['admin_url'] += '?alive=all'  # filter by all subjects

    model_to_app = {str(model['name']): str(app['name'])
                    for app in app_list
                    for model in app['models']}
    category_list = [Bunch(name=name,
                           models=[models_dict[m] for m in model_names if m in models_dict],
                           collapsed='' if i < 4 else 'collapsed'  # Determine collapsed
                           )
                     for i, (name, model_names) in enumerate(order)]
    for model_name, app_name in model_to_app.items():
        if model_name in order_models:
            continue
        if model_name.startswith('Subject') or model_name in extra_in_common:
            category_list[0].models.append(models_dict[model_name])
        else:
            category_list[-2].models.append(models_dict[model_name])
    # Add link to training view in 'Common' panel.
    category_list[1].models.append({
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
    """The admin site Alyx serves.

    Installed as Django's default site by alyx.apps.AlyxAdminConfig, so that
    ``django.contrib.admin.site`` and the ``@admin.register`` decorator both refer to it.
    """

    site_header = 'Alyx'
    site_title = 'Alyx'
    site_url = None
    index_title = f'Welcome to Alyx {version}'
    enable_nav_sidebar = False

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
        models.JSONField: {'widget': JsonWidget},
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
        now = datetime.now(tz=server_tz)  # convert datetime from naive to server timezone
        now = now.astimezone(tz)  # convert to the lab timezone
        return {'start_time': now, 'created_at': now, 'date_time': now}

    def changelist_view(self, request, extra_context=None):
        category_list = _get_category_list(admin.site.get_app_list(request))
        extra_context = extra_context or {}
        extra_context['mininav'] = [('', '-- jump to --')]
        extra_context['mininav'] += [(model['admin_url'], model['name'])
                                     for model in category_list[0].models]
        return super(BaseAdmin, self).changelist_view(request, extra_context=extra_context)

    def has_add_permission(self, request, *args, **kwargs):
        if request.user.is_public_user:
            return False
        else:
            return super(BaseAdmin, self).has_add_permission(request, *args, **kwargs)

    def has_change_permission(self, request, obj=None):
        if request.user.is_public_user:
            return False
        if not obj:
            return True
        if request.user.is_superuser:
            return True

        # [CR 2024-03-12]
        # HACK: following a request by Charu R from cortexlab, we authorize all users in the
        # special Husbandry group to edit litters.
        # FIXME This should be moved to the individual model admin has_change_permission methods
        husbandry = 'husbandry' in ', '.join(_.name.lower() for _ in request.user.groups.all())
        if husbandry:
            if obj.__class__.__name__ in ('Litter', 'Subject', 'BreedingPair'):
                return True

        # Find subject associated to the object.
        if hasattr(obj, 'responsible_user'):
            subj = obj
        elif getattr(obj, 'session', None):
            subj = obj.session.subject
        elif getattr(obj, 'subject', None):
            subj = obj.subject
        else:
            return False
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
        models.JSONField: {'widget': forms.Textarea(
            attrs={'rows': 3,
                   'cols': 30})},
        models.CharField: {'widget': forms.TextInput(attrs={'size': 16})},
    }


class BaseQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if "auto_datetime" in kwargs:
            super(BaseQuerySet, self).update(**kwargs)
        else:
            super(BaseQuerySet, self).update(**kwargs, auto_datetime=timezone.now())


BaseManager = models.Manager.from_queryset(BaseQuerySet)


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
        pkeys = {'count', 'next', 'previous', 'results'}
        if isinstance(r.data, dict) and set(r.data.keys()) == pkeys:
            return r.data['results']
        else:
            return r.data

    def post(self, *args, **kwargs):
        return self.client.post(*args, **kwargs, content_type='application/json')

    def patch(self, *args, **kwargs):
        return self.client.patch(*args, **kwargs, content_type='application/json')


class BaseFilterSet(filters.FilterSet):
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

    @classmethod
    def filter_for_lookup(cls, f, lookup_type):
        # override date range lookups
        if isinstance(f, models.JSONField) and lookup_type == 'exact':
            return CharFilter, {}

        # use default behavior otherwise
        return super().filter_for_lookup(f, lookup_type)

    class Meta:
        abstract = True


def base_json_filter(fieldname, queryset, _, value):
    """
    function that filters the queryset from a custom REST query. To be used directly as
    a method for a FilterSet object. For example:
    # exact/equal lookup: "?extended_qc=qc_bool,True"
    # gte lookup: "?extended_qc=qc_pct__gte,0.5"
    # chained lookups: "?extended_qc=qc_pct__gte,0.5;qc_bool,True"
    """
    kwargs = _custom_filter_parser(value, arg_prefix=fieldname + '__')
    queryset = queryset.filter(**kwargs)
    return queryset


def split_comma_outside_brackets(value):
    """ For custom filters splits by comma if they are not within brackets. See
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
            # literal_eval, never eval: this value arrives verbatim in a REST query string.
            try:
                val = ast.literal_eval(val)
            except (ValueError, SyntaxError):
                raise ValueError(f'Not a list or tuple of literals: "{val}"')
        if arg_prefix + field in out_dict:
            raise ValueError('Duplicated fields in "' + str(value) + '"')
        out_dict[arg_prefix + field] = val
    return out_dict


class BaseSerializerContentTypeField(serializers.SlugRelatedField):
    """
    Field serializer for ContentType - the internal representation is an int
    The string representation is the concatenation of app + model, such as 'actions.session'
    """

    def to_representation(self, int_rep):
        return int_rep.app_label + '.' + int_rep.model

    def to_internal_value(self, str_rep):
        """
        If there is no dot, attempt a straight model lookup that may have conflicts
        Otherwise look for 'app.model' syntax as is returned in the representation
        A good practice is to constrain the queryset when initializing the serializer to given apps
        to avoid conflicts on the model name as much as possible
        """
        if '.' in str_rep:
            app, model = str_rep.split('.')
            obj = self.queryset.get(model=model, app_label=app)
        else:
            obj = self.queryset.get(model=str_rep)
        return obj


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


class LimitedLimitOffsetPagination(LimitOffsetPagination):
    """LimitOffsetPagination with a hard cap on the requested page size.

    Prevents a single request (e.g. `?limit=5000`) from materializing an
    unbounded number of rows and their prefetched relations in memory.

    The cap also reports itself. Capping alone only converts one huge query into many medium
    ones: a client asking for 10000 rows is handed 1000 with a `next` link and, seeing a large
    `count`, does the only thing it can and follows that link until the set is exhausted. That
    is as hard on the database as the original request and is the pattern that has taken it
    down. So a response that has been capped, or that begins a long run of pages, carries a
    line saying what happened and where the bulk route is - in the response body, which is the
    one channel every client reads whether or not it ever looks at the documentation.
    """
    max_limit = 1000
    #: Pages beyond this many records are better served by the cache tables than by paging.
    bulk_advice_threshold = 5000

    def get_limit(self, request):
        limit = super(LimitedLimitOffsetPagination, self).get_limit(request)
        requested = request.query_params.get(self.limit_query_param)
        self.limit_was_capped = False
        if requested:
            try:
                self.limit_was_capped = int(requested) > self.max_limit
            except (TypeError, ValueError):
                pass  # unparseable limits are already ignored by super()
        return limit

    def _advice(self):
        """Guidance to attach to this response, or '' if none is warranted.

        Deliberately quiet: only when a client asked for more than it can have, or when it has
        just started paging through a set large enough that paging is the wrong approach.
        Repeating it on every page of every response would train clients to ignore it.
        """
        capped = getattr(self, 'limit_was_capped', False)
        starting_a_long_run = self.offset == 0 and (self.count or 0) > self.bulk_advice_threshold
        if not (capped or starting_a_long_run):
            return ''
        advice = []
        if capped:
            advice.append(f'The requested page size was capped at {self.max_limit} records.')
        if (self.count or 0) > self.max_limit:
            advice.append(
                f'This query matches {self.count} records. Rather than paging through them, '
                f'use the ONE API, which queries downloaded cache tables locally instead of '
                f'the database: https://int-brain-lab.github.io/ONE/. Paging large result '
                f'sets places avoidable load on this database and is heavily rate limited.')
        return ' '.join(advice)

    def get_paginated_response(self, data):
        response = super(LimitedLimitOffsetPagination, self).get_paginated_response(data)
        advice = self._advice()
        if advice:
            response.data['detail'] = advice
        return response


def rest_filters_exception_handler(exc, context):
    """
    Custom exception handler that provides context (field names etc...) for poorly formed
    REST queries
    """
    response = exception_handler(exc, context)
    from rest_framework.response import Response
    from rest_framework.exceptions import Throttled
    # Now add the HTTP status code to the response.
    if response is not None:
        response.data['status_code'] = response.status_code
        if isinstance(exc, Throttled):
            # A client that has been throttled is, by definition, reading this response. DRF
            # already sets Retry-After; saying why and what to do instead turns a wall into an
            # instruction. Clients that hit the limit are usually paging a large result set,
            # which the cache tables serve without touching the database at all.
            response.data['detail'] = (
                f'{response.data.get("detail", "")} This database is rate limited. If you are '
                f'retrieving a large number of records, use the ONE API, which queries '
                f'downloaded cache tables locally rather than this database: '
                f'https://int-brain-lab.github.io/ONE/').strip()
    else:
        # we send back a long form error message in debug mode
        debug_text = traceback.format_exc() if settings.DEBUG else str(exc)
        data = {'status_code': 500, 'detail': debug_text}
        response = Response(data, status=500)

    return response


class BaseRestPublicPermission(permissions.BasePermission):
    """
    The purpose is to prevent public users from interfering in any way using writable methods
    """

    def has_permission(self, request, view):
        if request.method == 'GET':
            return True
        elif request.user.is_public_user:
            return False
        else:
            return True


def rest_permission_classes():
    permission_classes = (permissions.IsAuthenticated & BaseRestPublicPermission,)
    return permission_classes


def is_lab_member(user):
    """Whether this is a signed-in lab member rather than a public read-only account."""
    return bool(user.is_authenticated and user.is_staff and not user.is_public_user)


class LabMemberRestPermission(permissions.BasePermission):
    """For endpoints a public read-only account has no business calling at all."""

    def has_permission(self, request, view):
        return is_lab_member(request.user)


class LabMemberRequiredMixin:
    """Restricts a page to signed-in lab members: anyone else gets the login page or a 403.

    Deliberately not built on django.contrib.auth.mixins, which imports the auth forms and so
    the user model, and cannot be imported here without a circular import through misc.models.
    """

    login_url = reverse_lazy('admin:login')

    def dispatch(self, request, *args, **kwargs):
        if not is_lab_member(request.user):
            if request.user.is_authenticated:
                raise PermissionDenied
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path(), str(self.login_url))
        return super(LabMemberRequiredMixin, self).dispatch(request, *args, **kwargs)
