"""Tests for alyx.permissions, the write permissions that the admin and the REST API share."""
from datetime import date, datetime, timedelta
from io import StringIO
import logging
from unittest import mock

from django.contrib import admin
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import URLPattern, URLResolver, get_resolver, reverse
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from actions.models import Session, WaterRestriction, Weighing
from alyx.permissions import BaseRestPermission, can_add, can_change, can_delete, get_labs
from data.models import DataNotice, DataRepository, Dataset, FileRecord
from experiments.models import (
    FOV, FOVLocation, ImagingType, ProbeInsertion, TrajectoryEstimate)
from jobs.models import Task
from misc.models import Lab, LabMember, LabMembership, Note
from subjects.models import BreedingPair, Line, Litter, Project, Subject


def make_records(cls):
    """Create the users and records the tests share, as attributes of cls.

    The subject 'mouse' of lab_a has `owner` for responsible user, who allows `allowed`, and
    its session lists `experimenter` among its users. `server` is a member of lab_a with no
    other connection to the subject, like the account a lab server runs its pipelines with
    before it is made a pipeline user, and `pipeline` is that account made one. `husbandry` is
    a lab_a member in the Husbandry group and `outsider` a member of lab_b. All accounts but
    `pipeline` have staff status, and all but `no_group` and `public` are in the lab members
    group.
    """
    cls.lab = Lab.objects.create(name='lab_a')
    cls.other_lab = Lab.objects.create(name='lab_b')
    for name in ('owner', 'allowed', 'experimenter', 'server', 'pipeline', 'outsider',
                 'husbandry', 'no_group'):
        setattr(cls, name, LabMember.objects.create_user(
            username=name, password='pw', is_staff=name != 'pipeline'))
    cls.superuser = LabMember.objects.create_superuser('admin_user', 'admin@example.com', 'pw')
    cls.public = LabMember.objects.create_user(
        username='public', password='pw', is_public_user=True, is_staff=True)
    call_command('set_user_permissions', stdout=StringIO())
    call_command('set_pipeline_permissions', stdout=StringIO())
    cls.no_group.groups.clear()
    cls.pipeline.groups.add(Group.objects.get(name='Pipeline users'))
    cls.husbandry.groups.add(Group.objects.get(name='Husbandry'))
    cls.owner.allowed_users.add(cls.allowed)
    for user in (cls.server, cls.pipeline, cls.husbandry):
        LabMembership.objects.create(user=user, lab=cls.lab)
    LabMembership.objects.create(user=cls.outsider, lab=cls.other_lab)

    cls.subject = Subject.objects.create(nickname='mouse', lab=cls.lab,
                                         responsible_user=cls.owner)
    cls.other_subject = Subject.objects.create(nickname='other_mouse', lab=cls.other_lab,
                                               responsible_user=cls.outsider)
    cls.line = Line.objects.create(nickname='line', lab=cls.lab)
    cls.breeding_pair = BreedingPair.objects.create(name='pair', line=cls.line)
    cls.litter = Litter.objects.create(line=cls.line, breeding_pair=cls.breeding_pair)
    cls.session = Session.objects.create(subject=cls.subject, lab=cls.lab, number=1)
    cls.session.users.add(cls.experimenter)
    cls.other_session = Session.objects.create(subject=cls.other_subject, lab=cls.other_lab)
    cls.repository = DataRepository.objects.create(name='lab_a_server')
    cls.lab.repositories.add(cls.repository)
    cls.dataset = Dataset.objects.create(name='spikes.times.npy', session=cls.session)
    cls.file_record = FileRecord.objects.create(
        dataset=cls.dataset, data_repository=cls.repository,
        relative_path='mouse/2020-01-01/001/alf/spikes.times.npy')
    cls.insertion = ProbeInsertion.objects.create(session_id=cls.session.pk, name='probe00')
    cls.trajectory = TrajectoryEstimate.objects.create(probe_insertion=cls.insertion,
                                                       provenance=70)
    imaging_type = ImagingType.objects.create(name='mesoscope')
    cls.fov = FOV.objects.create(session_id=cls.session.pk, imaging_type=imaging_type,
                                 name='FOV_00')
    cls.fov_location = FOVLocation.objects.create(field_of_view=cls.fov, provenance='E',
                                                  n_xyz=(512, 512, 1))
    cls.task = Task.objects.create(name='Spikesorting', session=cls.session,
                                   data_repository=cls.repository)
    cls.note = Note.objects.create(  # as made by a plotting task
        user=cls.pipeline, text='QC', object_id=cls.session.pk,
        content_type=ContentType.objects.get_for_model(Session))


class QuietRefusals:
    """Keep the INFO messages logged for refused requests out of the test output."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        logger = logging.getLogger('alyx.permissions')
        cls.addClassCleanup(logger.setLevel, logger.level)
        logger.setLevel(logging.WARNING)


class PolicyTests(TestCase):
    """can_add, can_change and can_delete, which the admin and the REST API both ask."""

    @classmethod
    def setUpTestData(cls):
        make_records(cls)

    def test_change_by_ownership(self):
        for user in (self.owner, self.allowed, self.superuser):
            with self.subTest(user=user.username):
                self.assertTrue(can_change(user, self.session))
                self.assertTrue(can_change(user, self.insertion))
        for user in (self.server, self.outsider, self.public, self.no_group):
            with self.subTest(user=user.username):
                self.assertFalse(can_change(user, self.session))
                self.assertFalse(can_change(user, self.insertion))
        # The users of a session own it, but not the records that belong to it.
        self.assertTrue(can_change(self.experimenter, self.session))
        self.assertFalse(can_change(self.experimenter, self.insertion))
        # No subject, so no owner: only superusers, or by lab as tested below.
        self.assertFalse(can_change(self.owner, self.file_record))
        self.assertTrue(can_change(self.superuser, self.file_record))

    def test_change_without_object(self):
        """The admin asks this for change lists; it needs only the model permission."""
        self.assertTrue(can_change(self.server, model=Session))
        self.assertFalse(can_change(self.server, model=Project))  # not given to lab members
        self.assertFalse(can_change(self.no_group, model=Session))
        self.assertFalse(can_change(self.public, model=Session))

    def test_add_and_delete_follow_model_permissions(self):
        self.assertTrue(can_add(self.server, Session))
        self.assertFalse(can_add(self.server, Project))
        self.assertFalse(can_add(self.public, Session))
        self.assertFalse(can_add(self.no_group, Session))
        # Lab members may delete a few models only, whoever the record belongs to.
        self.assertTrue(can_delete(self.server, Weighing))
        self.assertFalse(can_delete(self.owner, Session))
        self.assertTrue(can_delete(self.superuser, Session))
        self.assertFalse(can_delete(self.public, Weighing))

    def test_task_rule(self):
        self.assertTrue(can_change(self.experimenter, self.task))  # a user of its session
        self.assertTrue(can_change(self.server, self.task))  # a member of its session's lab
        self.assertFalse(can_change(self.outsider, self.task))
        self.assertFalse(can_change(self.owner, self.task))  # ownership does not apply
        task = Task.objects.create(name='Repo task', data_repository=self.repository)
        self.assertTrue(can_change(self.server, task))  # a member of its repository's lab
        self.assertFalse(can_change(self.outsider, task))
        orphan = Task.objects.create(name='Orphan')
        self.assertFalse(can_change(self.server, orphan))

    def test_other_rules(self):
        notice = DataNotice.objects.create(name='notice')
        self.assertTrue(can_change(self.outsider, notice))
        self.assertFalse(can_change(self.public, notice))

        restriction = WaterRestriction.objects.create(subject=self.subject)
        self.assertFalse(can_change(self.outsider, restriction))
        with self.settings(WATER_RESTRICTIONS_EDITABLE=True):
            self.assertTrue(can_change(self.outsider, restriction))
            self.assertFalse(can_change(self.public, restriction))

        self.assertTrue(can_change(self.server, self.server))
        self.assertFalse(can_change(self.server, self.owner))
        self.assertTrue(can_change(self.superuser, self.owner))

    def test_notes(self):
        """Only its author may change or delete a note, as a plotting task does its own."""
        for user in (self.pipeline, self.superuser):
            with self.subTest(user=user.username):
                self.assertTrue(can_change(user, self.note))
                self.assertTrue(can_delete(user, Note, self.note))
        for user in (self.owner, self.server, self.outsider, self.public):
            with self.subTest(user=user.username):
                self.assertFalse(can_change(user, self.note))
                self.assertFalse(can_delete(user, Note, self.note))
        own = Note.objects.create(user=self.server, text='Mine', object_id=self.session.pk,
                                  content_type=self.note.content_type)
        self.assertTrue(can_delete(self.server, Note, own))  # any lab member, their own note

    def test_husbandry(self):
        """The colony records of their labs, whoever is responsible for them."""
        for obj in (self.subject, self.line, self.litter, self.breeding_pair):
            with self.subTest(record=type(obj).__name__):
                self.assertTrue(can_change(self.husbandry, obj))
                self.assertFalse(can_change(self.server, obj))
        self.assertFalse(can_change(self.husbandry, self.other_subject))  # another lab
        self.assertFalse(can_change(self.husbandry, self.session))  # not a colony record
        LabMembership.objects.filter(user=self.husbandry).update(
            end_date=date.today() - timedelta(days=1))
        self.assertFalse(can_change(self.husbandry, self.subject))  # no longer a member

    def test_pipeline(self):
        """Any record of its labs, whoever is responsible for it."""
        records = (self.subject, self.session, self.dataset, self.file_record, self.insertion,
                   self.trajectory, self.fov, self.fov_location, self.repository, self.line,
                   self.litter, self.breeding_pair)
        for obj in records:
            with self.subTest(record=type(obj).__name__):
                self.assertTrue(can_change(self.pipeline, obj))
                self.assertFalse(can_change(self.server, obj))
        # Tasks of the lab's sessions any member of the lab may change, by the task rule.
        self.assertTrue(can_change(self.pipeline, self.task))
        self.assertTrue(can_change(self.server, self.task))
        # A file record in the lab's repository, of a dataset with no session, and a task of
        # the lab's repository only.
        stray = FileRecord.objects.create(
            dataset=Dataset.objects.create(name='stray.npy'), data_repository=self.repository,
            relative_path='stray.npy')
        self.assertTrue(can_change(self.pipeline, stray))
        task = Task.objects.create(name='Repo task', data_repository=self.repository)
        self.assertTrue(can_change(self.pipeline, task))
        # Another lab's records, and records of no lab: never.
        for obj in (self.other_session, self.other_subject, self.lab, self.owner,
                    LabMembership.objects.get(user=self.pipeline),
                    Project.objects.create(name='project')):
            with self.subTest(record=type(obj).__name__):
                self.assertFalse(can_change(self.pipeline, obj))
        self.assertIsNone(get_labs(self.lab))
        # A member of both labs may change the records of both.
        LabMembership.objects.create(user=self.pipeline, lab=self.other_lab)
        self.assertTrue(can_change(self.pipeline, self.other_session))
        # Only current memberships count.
        LabMembership.objects.filter(user=self.pipeline).update(
            start_date=date.today() + timedelta(days=1))
        self.assertFalse(can_change(self.pipeline, self.session))

    def test_admin_asks_the_policy(self):
        request = RequestFactory().get('/')
        records = (self.subject, self.session, self.dataset, self.file_record, self.insertion,
                   self.trajectory, self.fov, self.fov_location, self.task, self.note,
                   self.owner, self.litter, self.line)
        for user in (self.owner, self.server, self.pipeline, self.husbandry, self.superuser,
                     self.public):
            request.user = user
            for obj in filter(lambda r: admin.site.is_registered(type(r)), records):
                model_admin = admin.site.get_model_admin(type(obj))
                with self.subTest(user=user.username, model=type(obj).__name__):
                    self.assertEqual(can_change(user, obj),
                                     model_admin.has_change_permission(request, obj))
                    self.assertEqual(can_delete(user, type(obj), obj),
                                     model_admin.has_delete_permission(request, obj))


class QueryCountTests(TestCase):
    """How many queries the checks make. They run on every write, so keep these numbers low.

    Django loads a user's permissions in two queries, once per request, then keeps them on the
    user: that is the 2 in each count. The rest is what deciding takes. Each check here starts
    as a request does, with a user loaded afresh and a record fetched without related objects.
    """

    @classmethod
    def setUpTestData(cls):
        make_records(cls)

    def assertQueries(self, n, check, user, obj):
        user = LabMember.objects.get(pk=user.pk)
        obj = type(obj).objects.get(pk=obj.pk)
        with self.subTest(user=user.username, record=type(obj).__name__):
            with self.assertNumQueries(n):
                check(user, obj)

    def test_change(self):
        for n, user, obj in (
                (0, self.superuser, self.session),
                (2, self.owner, self.subject),  # its responsible user, a field of the subject
                (3, self.owner, self.session),  # loads the subject, kept for the serializer
                (4, self.experimenter, self.session),  # named on it: one query more
                (4, self.allowed, self.session),  # allowed by its responsible user: the same
                (4, self.server, self.session),  # refused after those
                (3, self.pipeline, self.session),  # one query for its labs, whatever the record
                (3, self.pipeline, self.subject),
                (3, self.pipeline, self.file_record),
                (3, self.pipeline, self.repository),
                (3, self.pipeline, self.trajectory),
                (3, self.pipeline, self.fov_location),
                (3, self.husbandry, self.litter),
                (3, self.server, self.task),  # the task rule: one query
                (2, self.pipeline, self.note)):  # its author: nothing to look up
            self.assertQueries(n, can_change, user, obj)

    def test_delete_and_add(self):
        self.assertQueries(2, lambda user, obj: can_delete(user, Note, obj),
                           self.pipeline, self.note)
        self.assertQueries(2, lambda user, obj: can_delete(user, Session, obj),
                           self.owner, self.session)
        self.assertQueries(2, lambda user, obj: can_add(user, type(obj)),
                           self.pipeline, self.session)

    def test_permissions_loaded_once(self):
        """A second check by the same user, as in the same request, costs no permission query."""
        user = LabMember.objects.get(pk=self.pipeline.pk)
        can_change(user, self.session)
        with self.assertNumQueries(1):
            can_change(user, self.insertion)


class CommandTests(TestCase):
    """set_user_permissions and set_pipeline_permissions."""

    def codenames(self, group_name):
        return set(Group.objects.get(name=group_name).permissions.values_list(
            'codename', flat=True))

    def test_set_user_permissions(self):
        new = LabMember.objects.create_user('new', password='pw')
        gone = LabMember.objects.create_user('gone', password='pw', is_active=False)
        call_command('set_pipeline_permissions', stdout=StringIO())  # creates its permission
        for _ in range(2):  # it can be run again
            call_command('set_user_permissions', stdout=StringIO())
        new.refresh_from_db()
        gone.refresh_from_db()
        self.assertFalse(new.is_staff)  # staff and active status are left alone
        self.assertFalse(gone.is_active)
        self.assertTrue(new.groups.filter(name='Lab members').exists())
        lab_members = self.codenames('Lab members')
        self.assertIn('delete_note', lab_members)
        self.assertNotIn('delete_session', lab_members)
        self.assertFalse(lab_members & {'change_lab_colony', 'change_lab_records'})
        self.assertEqual({'change_lab_colony'}, self.codenames('Husbandry'))

        # Custom permissions given to lab members by hand are taken away again.
        Group.objects.get(name='Lab members').permissions.add(
            *Permission.objects.filter(codename='change_lab_records'))
        new.groups.add(Group.objects.get(name='Husbandry'))
        out = StringIO()
        call_command('set_user_permissions', stdout=out)
        self.assertNotIn('change_lab_records', self.codenames('Lab members'))
        self.assertIn("new is in group 'Husbandry' but not currently a member of any lab",
                      out.getvalue())

    def test_set_pipeline_permissions(self):
        account = LabMember.objects.create_user('server', password='pw', is_staff=True)
        for _ in range(2):  # it can be run again
            call_command('set_pipeline_permissions', stdout=StringIO())
        self.assertEqual({'change_lab_records'}, self.codenames('Pipeline users'))
        account.groups.add(Group.objects.get(name='Pipeline users'))
        out = StringIO()
        call_command('set_pipeline_permissions', stdout=out)
        for warning in ('server has staff status', "server is not in 'Lab members'",
                        'not currently a member of any lab'):
            self.assertIn(warning, out.getvalue())


class LabMembershipDateTests(TestCase):

    def test_today_is_when_asked(self):
        """lab_id used the date the server started, so new memberships waited for a restart."""
        user = LabMember.objects.create_user('member', password='pw')
        tomorrow = date.today() + timedelta(days=1)
        LabMembership.objects.create(user=user, lab=Lab.objects.create(name='lab'),
                                     start_date=tomorrow)
        self.assertFalse(user.lab_id().exists())
        with mock.patch('misc.models.datetime') as clock:
            clock.now.return_value = datetime.combine(tomorrow, datetime.min.time())
            self.assertTrue(user.lab_id().exists())
            self.assertEqual(['lab'], user.lab)


@override_settings(ENFORCE_REST_PERMISSIONS=True)
class RestPermissionTests(QuietRefusals, TestCase):
    """REST writes through the HTTP API."""

    @classmethod
    def setUpTestData(cls):
        make_records(cls)

    def patch(self, url, data):
        return self.client.patch(url, data=data, content_type='application/json')

    def test_change_needs_ownership(self):
        url = f'/sessions/{self.session.pk}'
        self.client.force_login(self.server)
        with self.assertLogs('alyx.permissions', 'INFO') as logs:
            response = self.patch(url, {'narrative': 'x'})
        self.assertEqual(403, response.status_code)
        self.assertIn(f'REST PATCH {url} by server refused', logs.output[0])
        self.assertIn('change this session', response.json()['detail'])
        self.client.force_login(self.owner)
        self.assertEqual(200, self.patch(url, {'narrative': 'x'}).status_code)

    def test_delete_needs_model_permission(self):
        url = f'/sessions/{self.session.pk}'
        self.client.force_login(self.owner)
        self.assertEqual(403, self.client.delete(url).status_code)
        self.client.force_login(self.superuser)
        self.assertEqual(204, self.client.delete(url).status_code)

    def test_create_needs_model_permission(self):
        self.client.force_login(self.server)
        self.assertEqual(403, self.client.post('/projects', {'name': 'p'}).status_code)
        self.client.force_login(self.superuser)
        self.assertEqual(201, self.client.post('/projects', {'name': 'p'}).status_code)

    def test_public_users_read_only(self):
        self.client.force_login(self.public)
        self.assertEqual(200, self.client.get(f'/sessions/{self.session.pk}').status_code)
        self.assertEqual(403, self.patch(f'/sessions/{self.session.pk}', {}).status_code)
        self.assertEqual(403, self.client.post('/register-file', {}).status_code)

    @override_settings(ENFORCE_REST_PERMISSIONS=False)
    def test_not_enforced_logs_instead(self):
        self.client.force_login(self.server)
        with self.assertLogs('alyx.permissions', 'WARNING') as logs:
            response = self.patch(f'/sessions/{self.session.pk}', {'narrative': 'x'})
        self.assertEqual(200, response.status_code)
        self.assertIn('would be refused', logs.output[0])
        self.assertIn('server', logs.output[0])
        self.assertIn('actions.session', logs.output[0])
        self.session.refresh_from_db()
        self.assertEqual('x', self.session.narrative)

    @override_settings(ENFORCE_REST_PERMISSIONS=False)
    def test_accounts_always_enforced(self):
        """Adding yourself to someone's allowed users would give you their subjects."""
        self.client.force_login(self.server)
        response = self.patch('/users/owner', {'allowed_users': ['server']})
        self.assertEqual(403, response.status_code)
        self.assertFalse(self.owner.allowed_users.filter(pk=self.server.pk).exists())
        self.assertEqual(403, self.client.delete('/users/owner').status_code)
        response = self.patch('/users/server', {'email': 'server@example.com'})
        self.assertEqual(200, response.status_code)

    @override_settings(ENFORCE_REST_PERMISSIONS=False)
    def test_browsable_api_does_not_log(self):
        """The browsable API checks permissions for its forms, which writes nothing."""
        self.client.force_login(self.server)
        with self.assertNoLogs('alyx.permissions', 'WARNING'):
            response = self.client.get(f'/sessions/{self.session.pk}', HTTP_ACCEPT='text/html')
        self.assertEqual(200, response.status_code)


def _rest_views(patterns=None, prefix=''):
    """Yield (route, view class, init kwargs) for each DRF view in the URL configuration."""
    for pattern in get_resolver().url_patterns if patterns is None else patterns:
        if isinstance(pattern, URLResolver):
            yield from _rest_views(pattern.url_patterns, prefix + str(pattern.pattern))
        elif isinstance(pattern, URLPattern):
            cls = getattr(pattern.callback, 'cls', None)
            if cls is not None and issubclass(cls, APIView):
                initkwargs = getattr(pattern.callback, 'initkwargs', {})
                yield prefix + str(pattern.pattern), cls, initkwargs


class RestViewsTests(QuietRefusals, TestCase):
    """Checks over every REST view, so that a new one cannot get round the permissions."""

    # Views open to anyone on purpose. None of them reads or writes a record.
    public_routes = (
        'api/',  # the API root: an index and a how-to
        'api/schema',  # the OpenAPI schema and its documentation page
        'docs/',
        'auth-token',  # signing in: it is how a client gets credentials in the first place
    )

    @classmethod
    def setUpTestData(cls):
        make_records(cls)

    def test_every_view_uses_the_shared_permissions(self):
        for route, cls, initkwargs in _rest_views():
            if route in self.public_routes:
                continue
            with self.subTest(route=route, view=cls.__name__):
                classes = cls(**initkwargs).permission_classes
                self.assertTrue(classes)
                self.assertTrue(all(isinstance(c, type) and issubclass(c, BaseRestPermission)
                                    for c in classes), classes)

    @override_settings(ENFORCE_REST_PERMISSIONS=True)
    def test_rest_agrees_with_the_admin(self):
        """For each REST view of a model in the admin, both answer alike for each user."""
        records = {type(obj): obj for obj in (
            self.subject, self.session, self.dataset, self.file_record, self.insertion,
            self.trajectory, self.fov, self.fov_location, self.task, self.note, self.owner,
            self.lab, self.repository)}
        users = (self.owner, self.server, self.pipeline, self.husbandry, self.outsider,
                 self.superuser, self.public)
        api, factory = APIRequestFactory(), RequestFactory()
        checked = set()
        for route, cls, initkwargs in _rest_views():
            model = getattr(getattr(cls, 'queryset', None), 'model', None)
            if model is None or not admin.site.is_registered(model):
                continue
            model_admin = admin.site.get_model_admin(model)
            view = cls(**initkwargs)
            methods = set(view.allowed_methods)
            for user in users:
                admin_request = factory.get('/')
                admin_request.user = user
                for method in methods & {'POST', 'PATCH', 'DELETE'}:
                    request = Request(getattr(api, method.lower())('/'))
                    request.user = user
                    view.request, view.kwargs, view.format_kwarg = request, {}, None
                    permission = view.get_permissions()[0]
                    rest = permission.has_permission(request, view)
                    if method == 'POST':
                        expected = model_admin.has_add_permission(admin_request)
                    elif model not in records:
                        continue
                    else:
                        obj = records[model]
                        rest = rest and permission.has_object_permission(request, view, obj)
                        expected = (model_admin.has_delete_permission(admin_request, obj)
                                    if method == 'DELETE' else
                                    model_admin.has_change_permission(admin_request, obj))
                    with self.subTest(route=route, method=method, user=user.username):
                        self.assertEqual(expected, rest)
                    checked.add(model)
        registered = set(filter(admin.site.is_registered, records))
        self.assertTrue(registered <= checked, registered - checked)


# The REST writes that ibllib, mpci and ONE make, and whether, with ENFORCE_REST_PERMISSIONS
# on, each account may make them: `server`, a lab member such as a lab server's account before
# it is made a pipeline user; `pipeline`, that account made one; and `owner`, the subject's
# responsible user. Superusers may make all of them. Each is
# (where it is made, method, path, data, server allowed, pipeline allowed, owner allowed).
PIPELINE_WRITES = (
    ('ONE RegistrationClient.register_session', 'POST', '/sessions', {}, True, True, True),
    ('ONE/ibllib register_session, json_field_update', 'PATCH', '/sessions/{session}',
     {'json': {'IS_MOCK': False}}, False, True, True),
    ('ibllib QC extended_qc', 'PATCH', '/sessions/{session}',
     {'extended_qc': {'behavior': 1}}, False, True, True),
    ('ibllib training status', 'PATCH', '/subjects/mouse', {'json': {'trained': 1}},
     False, True, True),
    ('ONE register_water_administration', 'POST', '/water-administrations', {},
     True, True, True),
    ('ONE register_weight', 'POST', '/weighings', {}, True, True, True),
    ('ONE register_files', 'POST', '/register-file', {}, True, True, True),
    ('ibllib tasks create', 'POST', '/tasks', {}, True, True, True),
    ('ibllib tasks status', 'PATCH', '/tasks/{task}', {'status': 'Started'}, True, True, False),
    ('ibllib file records exists flag', 'PATCH', '/files/{file_record}', {'exists': True},
     False, True, False),
    ('ibllib Patcher', 'DELETE', '/files/{file_record}', None, False, False, False),
    ('ibllib Patcher', 'DELETE', '/datasets/{dataset}', None, False, False, False),
    ('ibllib probe insertions', 'POST', '/insertions', {}, True, True, True),
    ('ibllib probe insertion QC', 'PATCH', '/insertions/{insertion}', {'json': {'qc': 1}},
     False, True, True),
    ('ibllib histology', 'POST', '/trajectories', {}, True, True, True),
    ('ibllib alignment QC', 'PATCH', '/trajectories/{trajectory}', {'json': {}},
     False, True, True),
    ('ibllib histology', 'POST', '/channels', {}, True, True, True),
    ('ibllib histology', 'DELETE', '/trajectories/{trajectory}', None, False, False, False),
    ('ibllib notes, mpci roicat', 'POST', '/notes', {}, True, True, True),
    ("ibllib snapshot, the note's author", 'PATCH', '/notes/{note}', {'text': 'x'},
     False, True, False),
    ("ibllib snapshot, the note's author", 'DELETE', '/notes/{note}', None, False, True, False),
    ('ibllib local server health', 'PATCH', '/data-repository/lab_a_server',
     {'json': {}}, False, True, False),
    ('mpci imaging stack', 'POST', '/imaging-stack', {}, True, True, True),
    ('mpci fields of view', 'POST', '/fields-of-view', {}, True, True, True),
    ('mpci FOV QC, integrity', 'PATCH', '/fields-of-view/{fov}', {'json': {}},
     False, True, True),
    ('mpci FOV location', 'POST', '/fov-location', {}, True, True, True),
    ('mpci FOV location', 'PATCH', '/fov-location/{fov_location}', {'n_xyz': [1, 1, 1]},
     False, True, False),
)


@override_settings(ENFORCE_REST_PERMISSIONS=True)
class PipelineWritesTests(QuietRefusals, TestCase):
    """What enforcing the REST permissions does to the writes the pipelines make.

    Only whether the permission check passes is tested: a request that passes may still be
    refused for its (here empty) data with a 400.
    """

    @classmethod
    def setUpTestData(cls):
        make_records(cls)

    def request(self, method, path, data):
        path = path.format(**{name: getattr(self, name).pk for name in (
            'session', 'task', 'file_record', 'dataset', 'insertion', 'trajectory', 'note',
            'fov', 'fov_location')})
        if method == 'POST':
            return self.client.post(path, data)
        if method == 'DELETE':
            return self.client.delete(path)
        return self.client.patch(path, data=data, content_type='application/json')

    def check(self, user, column):
        for source, method, path, data, *allowed in PIPELINE_WRITES:
            with self.subTest(source=source, method=method, path=path):
                self.client.force_login(user)
                status = self.request(method, path, data).status_code
                if allowed[column]:
                    self.assertNotIn(status, (401, 403))
                else:
                    self.assertEqual(403, status)

    def test_server_account(self):
        self.check(self.server, 0)

    def test_pipeline_user(self):
        self.check(self.pipeline, 1)

    def test_responsible_user(self):
        self.check(self.owner, 2)

    def test_superuser(self):
        self.client.force_login(self.superuser)
        for source, method, path, data, *_ in PIPELINE_WRITES:
            with self.subTest(source=source, method=method, path=path):
                self.assertNotIn(self.request(method, path, data).status_code, (401, 403))

    @override_settings(ENFORCE_REST_PERMISSIONS=False)
    def test_not_enforced(self):
        """With enforcement off, as by default, every write still goes through."""
        self.client.force_login(self.server)
        with self.assertLogs('alyx.permissions', 'WARNING') as logs:
            for source, method, path, data, *_ in PIPELINE_WRITES:
                with self.subTest(source=source, method=method, path=path):
                    status = self.request(method, path, data).status_code
                    self.assertNotIn(status, (401, 403))
        refused = sum(not server for *_, server, _, _ in PIPELINE_WRITES)
        self.assertEqual(refused, len(logs.output))


class AccountChangelistTests(TestCase):
    """The admin's list of users, whose permission flags can be edited in place."""

    @classmethod
    def setUpTestData(cls):
        make_records(cls)

    def post_flags(self, account):
        """Tick is_stock_manager on account from the change list, as the logged-in user."""
        return self.client.post(reverse('admin:misc_labmember_changelist'), {
            'form-TOTAL_FORMS': 1, 'form-INITIAL_FORMS': 1, 'form-0-id': account.pk,
            'form-0-is_stock_manager': 'on', '_save': 'Save'})

    def test_other_accounts_refused(self):
        self.client.force_login(self.server)
        response = self.post_flags(self.owner)
        self.assertContains(response, "You can&#x27;t change other users.")
        self.owner.refresh_from_db()
        self.assertFalse(self.owner.is_stock_manager)

    def test_superuser_allowed(self):
        self.client.force_login(self.superuser)
        self.assertEqual(302, self.post_flags(self.owner).status_code)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_stock_manager)


class RemovalReminderTests(SimpleTestCase):

    def test_remove_enforce_rest_permissions(self):
        """Fails on purpose from 1 March 2027. Move the date if deployments need longer."""
        self.assertLess(date.today(), date(2027, 3, 1), (
            'Time to remove ENFORCE_REST_PERMISSIONS (cortex-lab/alyx#882), so that REST '
            'permissions are always enforced: the setting in deploy/app/docker/'
            'settings-deploy.py; the logging-only path in BaseRestPermission._decide and its '
            'always_enforced in alyx/permissions.py, and the module docstring there; its '
            'mentions in docs/06_permissions.md and in the REST write permissions section of '
            'docs/03_deployment.md; the tests here that switch it off; and this test.'))
