"""Write permissions, shared by the admin site and the REST API.

The admin and the REST API used to decide separately who may write a record, and the REST API
let any signed-in lab member change or delete anything (cortex-lab/alyx#882). Both now ask the
functions here: the ModelAdmin permission methods in alyx.base delegate to `can_add`,
`can_change` and `can_delete`, and `BaseRestPermission` applies the same functions to REST
writes. A rule specific to one model belongs in `CHANGE_RULES` or `DELETE_RULES`, not in its
ModelAdmin, or the REST API will not see it. docs/06_permissions.md describes the result.

These checks run on every write, so they are written to make few queries: Django's two queries
to load the user's permissions, which are then cached on the user for the rest of the request,
and usually one more to decide. Records are tested by the ids they hold rather than by loading
related objects, and each lab check is a single EXISTS query. Keep it that way: the query
counts are pinned by QueryCountTests in alyx/test_permissions.py.

The REST API checks are not enforced unless settings.ENFORCE_REST_PERMISSIONS is true. Until
then a REST write the admin would refuse is still made, and logged as a warning on this module's
logger, so a deployment can see what enforcing would break before turning it on. Changes to user
accounts are always enforced: no pipeline makes them, and changing another person's account
(adding yourself to their allowed users, say) is a way to gain their permissions.

DEFAULT_PERMISSION_CLASSES is resolved from inside rest_framework.views while that module is
still part way through importing, so anything named there must not reach back into it. Keep
this module free of Alyx imports at module level and of rest_framework.views (alyx.views pulls
it in through drf_spectacular, which is why this does not live there). Models are looked up
through the app registry when they are needed.
"""
from datetime import datetime
from functools import cache
import logging

from django.apps import apps
from django.conf import settings
from django.db.models import Q
from django.db.models.functions import Coalesce
from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)

# Permissions beyond Django's add, change, delete and view. No model declares them, so no
# migration creates them: set_user_permissions and set_pipeline_permissions do, through
# get_or_create_permission. Both belong to the Lab model, so their full names are
# 'misc.change_lab_colony' and 'misc.change_lab_records'.
LAB_COLONY_PERMISSION = ('change_lab_colony', 'Can change colony records of its labs')
LAB_RECORDS_PERMISSION = ('change_lab_records', 'Can change any record of its labs')
CUSTOM_PERMISSIONS = (LAB_COLONY_PERMISSION, LAB_RECORDS_PERMISSION)

# The records the colony permission covers.
COLONY_MODELS = frozenset({
    'subjects.subject', 'subjects.litter', 'subjects.breedingpair', 'subjects.line',
    'subjects.genotypetest', 'subjects.zygosity', 'actions.cull'})


def get_or_create_permission(permission):
    """Return one of CUSTOM_PERMISSIONS as a Permission, creating it if need be."""
    codename, name = permission
    lab_type = apps.get_model('contenttypes', 'ContentType').objects.get_for_model(
        apps.get_model('misc', 'Lab'))
    return apps.get_model('auth', 'Permission').objects.get_or_create(
        codename=codename, content_type=lab_type, defaults={'name': name})[0]


def _may_write(user):
    """Whether user is signed in and not a public, read-only account."""
    return bool(user and user.is_authenticated and not getattr(user, 'is_public_user', False))


def _has_model_permission(user, action, model):
    """Whether user holds Django's add, change or delete permission on model."""
    opts = model._meta
    return user.has_perm(f'{opts.app_label}.{action}_{opts.model_name}')


def _label(obj):
    return obj._meta.concrete_model._meta.label_lower


@cache
def _fields(model):
    """The names of the concrete fields and many-to-many fields of model."""
    opts = model._meta
    return ({f.name for f in opts.concrete_fields}, {f.name for f in opts.many_to_many})


def _is_property(model, name):
    return isinstance(getattr(model, name, None), property)


def _first(queryset):
    """The first value of a values_list queryset, or None, without the model's ordering."""
    return next(iter(queryset.order_by()[:1]), None)


# Ownership
# ------------------------------------------------------------------------------------------------

def _responsible_user_id(obj):
    """Find the subject obj is about and return (True, id of its responsible user).

    Returns (False, None) for a record with no subject. The subject is the record itself if it
    has a responsible user, else that of its session, else its own subject, in that order.
    """
    fields, _ = _fields(type(obj))
    if 'responsible_user' in fields:
        return True, obj.responsible_user_id
    if 'session' in fields:
        if obj.session_id:
            if type(obj)._meta.get_field('session').is_cached(obj):
                return True, obj.session.subject.responsible_user_id
            return True, _first(apps.get_model('actions', 'Session').objects.filter(
                pk=obj.session_id).values_list('subject__responsible_user', flat=True))
    elif _is_property(type(obj), 'session'):  # e.g. a trajectory, through its insertion
        # getattr with a default, as these properties raise AttributeError for a missing link
        session = getattr(obj, 'session', None)
        if session:
            return True, session.subject.responsible_user_id
    if 'subject' in fields:
        if not obj.subject_id:
            return False, None
        # Loaded through the record, which keeps it: the serializer or the admin form, which
        # show the subject, then use it rather than load it again.
        return True, obj.subject.responsible_user_id
    if _is_property(type(obj), 'subject'):
        subject = getattr(obj, 'subject', None)  # some return a nickname, not a subject
        if subject:
            return True, getattr(subject, 'responsible_user_id', None)
    return False, None


def _is_owner(user, obj):
    """Whether obj belongs to user.

    A record belongs to the responsible user of its subject, to the users that responsible user
    allows, and to the users the record names in a `user` or `users` field. A record with no
    subject belongs to no one. The cheapest tests come first.
    """
    found, responsible_id = _responsible_user_id(obj)
    if not found:
        return False
    if responsible_id == user.pk:
        return True
    fields, many_to_many = _fields(type(obj))
    if 'user' in fields and obj.user_id == user.pk:
        return True
    # Whether the record names them in its users, or its responsible user allows them: one
    # query between them, or none if the users are prefetched.
    LabMember = apps.get_model('misc', 'LabMember')
    named = Q()
    if 'users' in many_to_many:
        prefetched = getattr(obj, '_prefetched_objects_cache', {}).get('users')
        if prefetched is None:
            named = Q(pk__in=obj.users.values('pk'))
        elif any(u.pk == user.pk for u in prefetched):
            return True
    allowed = Q()
    if responsible_id is not None:
        # allowed_users is symmetrical: this row exists whichever of the two added the other.
        allowed = Q(pk__in=LabMember.allowed_users.through.objects.filter(
            from_labmember_id=responsible_id).values('to_labmember_id'))
    condition = named | allowed
    return bool(condition) and LabMember.objects.filter(condition, pk=user.pk).exists()


# Labs
# ------------------------------------------------------------------------------------------------
# A record's labs are given as a list of sources, each a list of lab ids or a values_list
# queryset of them, so that _in_labs can test membership in one query whatever the record.

def _session_labs(session_id):
    return apps.get_model('actions', 'Session').objects.filter(pk=session_id).values_list(
        Coalesce('lab', 'subject__lab'))


def _subject_labs(subject_id):
    return apps.get_model('subjects', 'Subject').objects.filter(pk=subject_id).values_list(
        'lab', flat=True)


def _repository_labs(repository_id):
    return apps.get_model('misc', 'Lab').repositories.through.objects.filter(
        datarepository_id=repository_id).values_list('lab_id', flat=True)


def _line_labs(obj):
    if not obj.line_id:
        return None
    return [apps.get_model('subjects', 'Line').objects.filter(pk=obj.line_id).values_list(
        'lab', flat=True)]


def _file_record_labs(obj):
    dataset_labs = apps.get_model('data', 'Dataset').objects.filter(
        pk=obj.dataset_id).values_list(Coalesce('session__lab', 'session__subject__lab'))
    return [dataset_labs, _repository_labs(obj.data_repository_id)]


def _task_labs(obj):
    if obj.session_id:
        return [_session_labs(obj.session_id)]
    if obj.data_repository_id:
        return [_repository_labs(obj.data_repository_id)]
    return None


def _trajectory_labs(obj):
    if obj.probe_insertion_id:
        return [apps.get_model('experiments', 'ProbeInsertion').objects.filter(
            pk=obj.probe_insertion_id).values_list(
            Coalesce('session__lab', 'session__subject__lab'))]
    if obj.chronic_insertion_id:
        return [apps.get_model('experiments', 'ChronicInsertion').objects.filter(
            pk=obj.chronic_insertion_id).values_list(Coalesce('lab', 'subject__lab'))]
    return None


def _channel_labs(obj):
    if not obj.trajectory_estimate_id:
        return None
    return [apps.get_model('experiments', 'TrajectoryEstimate').objects.filter(
        pk=obj.trajectory_estimate_id).values_list(Coalesce(
            'probe_insertion__session__lab', 'probe_insertion__session__subject__lab'))]


def _fov_location_labs(obj):
    return [apps.get_model('experiments', 'FOV').objects.filter(
        pk=obj.field_of_view_id).values_list(Coalesce('session__lab', 'session__subject__lab'))]


LAB_PATHS = {
    'data.datarepository': lambda obj: [_repository_labs(obj.pk)],
    'data.filerecord': _file_record_labs,
    'experiments.channel': _channel_labs,
    'experiments.fovlocation': _fov_location_labs,
    'experiments.trajectoryestimate': _trajectory_labs,
    'jobs.task': _task_labs,
    'subjects.breedingpair': _line_labs,
    'subjects.line': lambda obj: [[obj.lab_id]],
    'subjects.litter': _line_labs,
    'subjects.subject': lambda obj: [[obj.lab_id]],
}


def get_labs(obj):
    """Return where to find the labs obj belongs to, or None if it belongs to no lab.

    A record belongs to the lab of its session, or else of its subject; an action that names a
    lab of its own belongs to that one. Data repositories belong to the labs that use them,
    and a file record to its dataset's lab as well as to its repository's. Labs themselves,
    lab memberships, lab locations and accounts belong to no lab, so that the lab permissions
    can never be used to join a lab or change one.
    """
    path = LAB_PATHS.get(_label(obj))
    if path is not None:
        return path(obj)
    fields, _ = _fields(type(obj))
    if 'session' in fields and obj.session_id:
        return [_session_labs(obj.session_id)]
    if 'subject' in fields and obj.subject_id:
        if 'lab' in fields and obj.lab_id:
            return [[obj.lab_id]]
        return [_subject_labs(obj.subject_id)]
    return None


def _current_memberships(user):
    today = datetime.now().date()
    return apps.get_model('misc', 'LabMembership').objects.filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today), user_id=user.pk, start_date__lte=today)


def _in_labs(user, sources):
    """Whether user is currently a member of any of the labs, in one query."""
    if not sources:
        return False
    labs = Q()
    for source in sources:
        labs |= Q(lab_id__in=source)
    return _current_memberships(user).filter(labs).exists()


# Rules for single models
# ------------------------------------------------------------------------------------------------
# Each returns True or False to decide, or None to fall back on the lab permissions and
# ownership. They are only asked about users who hold the permission on the model and are not
# superusers.

def _task_rule(user, task):
    """The users of the task's session, and members of its lab or of its repository's lab."""
    if task.session_id:
        return apps.get_model('actions', 'Session').objects.filter(
            Q(users=user.pk) | Q(lab__in=_current_memberships(user).values('lab')),
            pk=task.session_id).exists()
    if task.data_repository_id:
        return _in_labs(user, [_repository_labs(task.data_repository_id)])
    return False


def _water_restriction_rule(user, obj):
    # A lab can let everyone edit water restrictions, in settings_lab.py.
    return True if getattr(settings, 'WATER_RESTRICTIONS_EDITABLE', False) else None


def _anyone_rule(user, obj):
    # Data notices are about datasets of many subjects, so they have no owner.
    return True


def _author_rule(user, note):
    # Notes are changed and deleted by their author only, pipelines included: a plotting task
    # replaces the note it made on its last run.
    return note.user_id == user.pk


def _own_account_rule(user, account):
    # Lab members may change their own account only, as LabMemberAdminForm also insists.
    return account.pk == user.pk


CHANGE_RULES = {
    'actions.waterrestriction': _water_restriction_rule,
    'data.datanotice': _anyone_rule,
    'jobs.task': _task_rule,
    'misc.labmember': _own_account_rule,
    'misc.note': _author_rule,
}

DELETE_RULES = {
    'misc.note': _author_rule,
}


# The checks
# ------------------------------------------------------------------------------------------------

def can_add(user, model):
    """Whether user may create records of model."""
    return _may_write(user) and _has_model_permission(user, 'add', model)


def can_change(user, obj=None, model=None):
    """Whether user may change obj, or, with no obj, records of model in general.

    Superusers may change anything. Otherwise the user needs the change permission on the
    model, and then, in this order: a rule in CHANGE_RULES decides; or the record is of one of
    the user's labs and the user holds the colony permission (colony records) or the lab
    records permission; or the record belongs to the user.
    """
    model = model or type(obj)
    if not (_may_write(user) and _has_model_permission(user, 'change', model)):
        return False
    if obj is None or user.is_superuser:
        return True
    label = _label(obj)
    rule = CHANGE_RULES.get(label)
    decision = rule(user, obj) if rule else None
    if decision is not None:
        return decision
    # The permissions are cached on the user by now, so asking costs no query.
    by_lab = (user.has_perm('misc.' + LAB_RECORDS_PERMISSION[0])
              or (label in COLONY_MODELS and user.has_perm('misc.' + LAB_COLONY_PERMISSION[0])))
    if by_lab and _in_labs(user, get_labs(obj)):
        return True
    return _is_owner(user, obj)


def can_delete(user, model, obj=None):
    """Whether user may delete obj, or, with no obj, records of model in general.

    As in Django's admin, this is the delete permission on the model, whoever the record
    belongs to, except for the models in DELETE_RULES.
    """
    if not (_may_write(user) and _has_model_permission(user, 'delete', model)):
        return False
    if obj is None or user.is_superuser:
        return True
    rule = DELETE_RULES.get(_label(obj))
    return rule(user, obj) if rule else True


# REST
# ------------------------------------------------------------------------------------------------

def _view_model(view):
    """The model a generic REST view creates, or None for a view not tied to one model."""
    queryset = getattr(view, 'queryset', None)
    if queryset is None and hasattr(view, 'get_queryset'):
        try:
            queryset = view.get_queryset()
        except AssertionError:  # a GenericAPIView with no queryset, e.g. /register-file
            return None
    return getattr(queryset, 'model', None)


class BaseRestPermission(BasePermission):
    """The admin's permissions, applied to the REST API.

    Every REST view uses this, through alyx.base.rest_permission_classes, and it is also the
    DEFAULT_PERMISSION_CLASSES, so a view that forgets to set permission_classes is not served
    to anonymous clients, which is what DRF's own AllowAny default would do.

    Anyone signed in may GET, and public users may do nothing else. A POST to a view of one
    model needs `can_add`, a PUT or PATCH needs `can_change` on the record and a DELETE needs
    `can_delete`. Views that are not about one model, like /register-file, only get the first
    two checks.
    """

    # Enforced whatever ENFORCE_REST_PERMISSIONS says.
    always_enforced = ('misc.labmember',)

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method == 'GET':
            return True
        if getattr(user, 'is_public_user', False):
            return False
        model = _view_model(view) if request.method == 'POST' else None
        if model is None:
            return True
        return self._decide(request, 'add', model, can_add(user, model))

    def has_object_permission(self, request, view, obj):
        if request.method == 'GET':
            return True
        model = type(obj)
        if request.method == 'DELETE':
            allowed = can_delete(request.user, model, obj)
            return self._decide(request, 'delete', model, allowed, obj)
        return self._decide(request, 'change', model, can_change(request.user, obj), obj)

    def _decide(self, request, action, model, allowed, obj=None):
        """Return whether to let the request through, logging the refusals not enforced."""
        if allowed:
            return True
        label = model._meta.label_lower
        # TODO Remove ENFORCE_REST_PERMISSIONS, and with it the logging-only path below, in a
        #  future version, once every deployment enforces these permissions: refusals should
        #  then always be enforced (cortex-lab/alyx#882).
        enforced = (getattr(settings, 'ENFORCE_REST_PERMISSIONS', False)
                    or label in self.always_enforced)
        self.message = f'You do not have permission to {action} this {model._meta.verbose_name}.'
        # The browsable API and OPTIONS check permissions under the method they would offer a
        # form for, while the request itself is a GET. Nothing is written, so nothing to log.
        if request.method == getattr(request, '_request', request).method:
            # A refusal is the client's to deal with; a write let through is the deployment's.
            logger.log(
                logging.INFO if enforced else logging.WARNING,
                'REST %s %s by %s %s: no %s permission on %s%s', request.method, request.path,
                request.user, 'refused' if enforced else
                'allowed, but would be refused with ENFORCE_REST_PERMISSIONS on', action, label,
                f' {obj.pk}' if obj is not None else '')
        return not enforced
