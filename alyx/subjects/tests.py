from datetime import datetime, date
import logging
from operator import attrgetter
import os.path as op
import sys
from uuid import UUID
import warnings

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.signals import pre_delete
from django.test import TestCase
from django.test.client import RequestFactory
from django.utils.connection import ConnectionDoesNotExist

from .admin import mysite
from subjects.models import BreedingPair, Line, Litter, Subject
from actions.models import Cull, CullMethod, Session, WaterRestriction, Surgery
from misc.models import Lab

logger = logging.getLogger(__file__)
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


DATA_DIR = op.abspath(op.join(op.dirname(__file__), '../../data'))


class MyTestsMeta(type):
    """Metaclass to generate one test per model dynamically."""
    def __new__(cls, name, bases, attrs):
        classes = sorted(mysite._registry, key=attrgetter('__name__'))
        for my_class in classes:
            name = my_class.__name__
            attrs['test_%s' % name] = cls.gen(my_class)
        return super(MyTestsMeta, cls).__new__(cls, name, bases, attrs)

    @classmethod
    def gen(cls, my_class):
        # Return a testcase that tests ``x``.
        def fn(self):
            self._test_class(my_class)
        return fn


class ModelAdminTests(TestCase, metaclass=MyTestsMeta):
    def setUp(self):
        # Fail on warning.
        # warnings.simplefilter("error")

        from misc.models import Lab
        self.site = mysite
        self.factory = RequestFactory()
        request = self.factory.get('/')
        request.csrf_processing_done = True
        self.request = request
        self.users = [user for user in get_user_model().objects.filter(is_superuser=True)]
        self.lab = Lab.objects.first()
        assert self.lab is not None

    def tearDown(self):
        warnings.simplefilter('default')

    @classmethod
    def setUpTestData(cls):
        call_command('loaddata', op.join(DATA_DIR, 'all_dumped_anon.json.gz'), verbosity=1)

    def ar(self, r):
        r.render()
        self.assertEqual(r.status_code, 200)

    def _test_list_change(self, ma):
        # List of subjects.
        r = ma.changelist_view(self.request)
        logger.debug("User %s, testing list %s.",
                     self.request.user.username, ma.model.__name__)
        self.ar(r)

        # Test the add page.
        if ma.has_add_permission(self.request):
            r = ma.add_view(self.request)
            logger.debug("User %s, testing add %s.",
                         self.request.user.username, ma.model.__name__)
            self.ar(r)

        # Get the first subject.
        qs = ma.get_queryset(self.request)
        if not len(qs):
            return
        subj = qs[0]

        # Test the change page.
        identifier = subj.id.hex if isinstance(subj.id, UUID) else str(subj.id)
        r = ma.change_view(self.request, identifier)
        logger.debug("User %s, testing change %s %s.",
                     self.request.user.username, ma.model.__name__, identifier)
        self.ar(r)

        # TODO: test saving

    def _test_class(self, cls):
        for user in self.users:  # test with different users
            self.request.user = user
            self._test_list_change(self.site._registry[cls])

    def test_validation(self):
        # Expect raises when using special characters
        self.assertRaises(ValidationError, Subject.objects.create, nickname='~mango.*')

    def test_history(self):
        from subjects.models import _has_field_changed

        s = Subject.objects.first()

        # Change the nickname.
        old_nickname = s.nickname
        s.nickname = 'new_nickname'
        s.save()

        self.assertEqual(s.json['history']['nickname'][-1]['value'], old_nickname)

        self.assertTrue(_has_field_changed(s, 'nickname'))
        self.assertFalse(_has_field_changed(s, 'death_date'))

        self.assertTrue(s.responsible_user is not None)
        self.assertFalse(_has_field_changed(s, 'responsible_user'))
        s.responsible_user = get_user_model().objects.last()
        self.assertTrue(_has_field_changed(s, 'responsible_user'))

    def test_zygosities_1(self):
        from subjects import models as m
        sequence = m.Sequence.objects.create(name='sequence')
        allele = m.Allele.objects.create(nickname='allele')
        line = m.Line.objects.create(nickname='line', lab=self.lab)
        line.alleles.add(allele)
        subject = m.Subject.objects.create(nickname='subject', line=line, lab=self.lab)
        assert len(subject.genotype.all()) == 0

        # Create a rule and a genotype test ; the subject should be automatically genotyped.
        rule = m.ZygosityRule.objects.create(
            line=line, allele=allele, sequence0=sequence, sequence0_result=1, zygosity=2)
        m.GenotypeTest.objects.create(
            subject=subject, sequence=sequence, test_result=1)

        a = m.Zygosity.objects.filter(subject=subject).first()
        assert len(subject.genotype.all()) == 1
        assert a.allele == allele
        assert a.subject == subject
        assert a.zygosity == 2

        # Change the rule
        rule.zygosity = 3
        rule.save()
        a = m.Zygosity.objects.filter(subject=subject).first()
        assert a.zygosity == 3

    def test_zygosities_2(self):
        from subjects import models as m
        sequence = m.Sequence.objects.create(name='sequence')
        allele = m.Allele.objects.create(nickname='allele')
        line = m.Line.objects.create(nickname='line', lab=self.lab)
        line.alleles.add(allele)

        # Create the parents.
        father = m.Subject.objects.create(
            nickname='father', sex='M', line=line, lab=self.lab)
        mother = m.Subject.objects.create(
            nickname='mother', sex='F', line=line, lab=self.lab)

        # Create the parents genotypes.
        m.Zygosity.objects.create(subject=father, allele=allele, zygosity=2)
        m.Zygosity.objects.create(subject=mother, allele=allele, zygosity=2)

        # Create the breeding pair and litter.
        bp = m.BreedingPair.objects.create(line=line, father=father, mother1=mother)
        litter = m.Litter.objects.create(line=line, breeding_pair=bp)

        # Create the subject.
        subject = m.Subject.objects.create(
            nickname='subject', line=line, litter=litter, lab=self.lab)
        z = m.Zygosity.objects.filter(subject=subject).first()
        assert z is None  # no zygosity should be assigned from parents

        # Create a rule and a genotype test ; the subject should be automatically genotyped.
        zr = m.ZygosityRule.objects.create(
            line=line, allele=allele, sequence0=sequence, sequence0_result=1, zygosity=0)
        m.GenotypeTest.objects.create(
            subject=subject, sequence=sequence, test_result=1)

        a = m.Zygosity.objects.filter(subject=subject).first()
        assert len(subject.genotype.all()) == 1
        assert a.allele == allele
        assert a.subject == subject
        assert a.zygosity == 0

        # Delete the rule.
        zr.delete()
        a = m.Zygosity.objects.filter(subject=subject).first()
        assert len(subject.genotype.all()) == 1
        assert a.allele == allele
        assert a.subject == subject
        assert a.zygosity == 2

    def test_zygosities_3(self):
        from subjects import models as m
        sequence = m.Sequence.objects.create(name='sequence')
        allele = m.Allele.objects.create(nickname='allele')
        allele_bis = m.Allele.objects.create(nickname='allele_bis')
        line = m.Line.objects.create(nickname='line', lab=self.lab)
        line.alleles.add(allele)

        # Create the parents.
        father = m.Subject.objects.create(
            nickname='father', sex='M', line=line, lab=self.lab)
        mother = m.Subject.objects.create(
            nickname='mother', sex='F', line=line, lab=self.lab)

        # Create the parents genotypes.
        m.Zygosity.objects.create(subject=father, allele=allele_bis, zygosity=2)
        m.Zygosity.objects.create(subject=mother, allele=allele, zygosity=1)

        # Create the breeding pair and litter.
        bp = m.BreedingPair.objects.create(line=line, father=father, mother1=mother)
        litter = m.Litter.objects.create(line=line, breeding_pair=bp)

        # Create the subject.
        subject = m.Subject.objects.create(
            nickname='subject', line=line, litter=litter, lab=self.lab)
        z = m.Zygosity.objects.filter(subject=subject)  # noqa
        return
        # TODO
        # ? assert z.zygosity == 2  # from parents
        # Create a rule and a genotype test ; the subject should be automatically genotyped.
        zr = m.ZygosityRule.objects.create(
            line=line, allele=allele, sequence0=sequence, sequence0_result=1, zygosity=0)
        m.GenotypeTest.objects.create(
            subject=subject, sequence=sequence, test_result=1)

        a = m.Zygosity.objects.filter(subject=subject).first()
        assert len(subject.genotype.all()) == 1
        assert a.allele == allele
        assert a.subject == subject
        assert a.zygosity == 0

        # Delete the rule.
        zr.delete()
        a = m.Zygosity.objects.filter(subject=subject).first()
        assert len(subject.genotype.all()) == 1
        assert a.allele == allele
        assert a.subject == subject
        assert a.zygosity == 2


class SubjectSurgery(TestCase):
    """Test subject surgery interactions.

    When a surgery is saved, the subject should be modified in a few ways.
    """
    def setUp(self):
        self.lab = Lab.objects.create(name='awesomelab')
        self.sub = Subject.objects.create(
            nickname='lawes', lab=self.lab, birth_date=date(2019, 1, 1))

    def test_protocol_number(self):
        """Test that the protocol number is incremented when a surgery is created."""
        assert self.sub.protocol_number == '1'
        # after a surgery protocol number goes to 2
        self.surgery = Surgery.objects.create(
            subject=self.sub, start_time=datetime(2019, 1, 1, 12, 0, 0), implant_weight=0.)
        assert self.sub.protocol_number == '2'
        # after water restriction number goes to 3
        self.wr = WaterRestriction.objects.create(
            subject=self.sub, start_time=datetime(2019, 1, 1, 12, 0, 0))
        assert self.sub.protocol_number == '3'
        self.wr.end_time = datetime(2019, 1, 2, 12, 0, 0)
        self.wr.save()
        assert self.sub.protocol_number == '2'
        self.surgery.delete()
        assert self.sub.protocol_number == '1'

    def test_actual_severity(self):
        """Test that the actual severity is increased when a surgery is created."""
        self.sub.actual_severity = 1
        self.sub.save()

        # Severity should not be increased unless it was mild (2)
        surgery = Surgery.objects.create(
            subject=self.sub, start_time=datetime(2019, 1, 1, 12, 0, 0), implant_weight=0.)
        self.assertEqual(1, self.sub.actual_severity)
        surgery.delete()

        # Severity should be increased if it was mild (2)
        self.sub.actual_severity = 2
        self.sub.save()
        surgery = Surgery.objects.create(
            subject=self.sub, start_time=datetime(2019, 1, 1, 12, 0, 0), implant_weight=0.)
        self.assertEqual(3, self.sub.actual_severity)

    def test_acute_non_recovery(self):
        """Test that the subject is culled after non-recovery surgeries."""
        # When a recovery surgery is created, the subject should not be culled.
        kwargs = {
            'subject': self.sub, 'implant_weight': 0.,
            'start_time': datetime(2019, 1, 1, 12, 0, 0),
        }
        surgery = Surgery.objects.create(
            outcome_type='r', end_time=datetime(2019, 1, 1, 13, 0, 0), **kwargs)
        self.assertFalse(hasattr(self.sub, 'cull'))
        surgery.delete()

        # When a non-recovery surgery is created with an end time,
        # the subject should be culled with the surgery end time.
        for outcome in ('n', 'a'):
            with self.subTest(outcome_type=outcome):
                surgery = Surgery.objects.create(outcome_type=outcome, **kwargs)
                surgery.end_time = datetime(2019, 1, 1, 13, 0, 0)
                surgery.save()
                self.assertFalse(hasattr(self.sub, 'cull'))  # no longer expected to create a cull
                self.assertEqual(self.sub.death_date, surgery.end_time.date())
                surgery.delete()


class SubjectCullTests(TestCase):

    def setUp(self):
        self.lab = Lab.objects.create(name='awesomelab')
        self.sub1 = Subject.objects.create(nickname='basil', lab=self.lab, birth_date='2019-01-01')
        self.sub2 = Subject.objects.create(nickname='loretta', lab=self.lab,
                                           birth_date='2019-01-01')
        self.CO2 = CullMethod.objects.create(name='CO2')
        self.decapitation = CullMethod.objects.create(name='decapitation')
        self.wr = WaterRestriction.objects.create(
            subject=self.sub1, start_time=datetime(2019, 1, 1, 12, 0, 0))

    def test_update_cull_object(self):
        self.assertFalse(hasattr(self.sub1, 'cull'))
        # self.assertIsNone(self.wr.end_time)
        # makes sure than when creating the cull
        # if there is an integrity error here, it means the save functions are saving the cull
        # several time and the water restriction/ cull / subjects save are interdependent
        cull = Cull.objects.create(subject=self.sub1, date='2019-07-15', cull_method=self.CO2)
        self.assertEqual(self.sub1.death_date, cull.date)
        # change cull properties and make sure the corresponding subject properties changed too
        cull.cull_method = self.decapitation
        cull.date = '2019-07-16'
        cull.save()
        self.assertEqual(self.sub1.death_date, cull.date)
        # [CR] WARNING: the water restriction is closed at the first save (Cull creation), but NOT
        # at the second save, when the cull date has been changed. I don't think the closed
        # water restriction's end time should be silently updated to reflect this.
        # This is why we have a NotEqual.
        self.assertNotEqual(
            WaterRestriction.objects.get(subject=self.sub1).end_time.strftime('%Y-%m-%d'),
            cull.date)
        # make sure that when a subject with a cull has its death date changed, the cull object
        # is updated too
        self.sub1.death_date = date(2019, 7, 17)
        self.sub1.save()
        self.assertEqual(cull.date, self.sub1.death_date)
        # now make sure that when the Cull object is deleted, the corresponding subject has his
        # death_date set to None
        cull.delete()
        self.assertIsNone(self.sub1.death_date)
        self.assertTrue(self.sub1.alive())

    def test_cull_ends_water_restriction(self):
        """Test open water restrictions are ended when the death date is already set."""
        self.sub2.death_date = date(2019, 7, 15)
        self.sub2.save()
        # Water restriction added after the death date was set
        wr = WaterRestriction.objects.create(
            subject=self.sub2, start_time=datetime(2019, 7, 15, 12, 0, 0))
        wr.refresh_from_db()
        self.assertFalse(wr.is_active())
        # End time should not precede the start time
        self.assertEqual(wr.end_time, wr.start_time)
        # Re-open and add a cull with the same date as the death date
        WaterRestriction.objects.filter(pk=wr.pk).update(end_time=None)
        Cull.objects.create(subject=self.sub2, date=date(2019, 7, 15), cull_method=self.CO2)
        wr.refresh_from_db()
        self.assertFalse(wr.is_active())
        self.sub2.refresh_from_db()
        self.assertEqual(self.sub2.protocol_number, '1')


class LineAutonameTests(TestCase):
    """Deleting the newest breeding pairs, litters or subjects of a line frees their names."""

    def setUp(self):
        self.lab = Lab.objects.create(name='awesomelab')
        self.line = Line.objects.create(name='line', nickname='LN', lab=self.lab)
        self.bp = BreedingPair.objects.create(line=self.line)
        # LN_L_001 with pups LN_0001 and LN_0002, then LN_L_002 with LN_0003 and LN_0004
        self.litters = [Litter.objects.create(line=self.line, breeding_pair=self.bp)
                        for _ in range(2)]
        self.pups = [Subject.objects.create(line=self.line, litter=litter, lab=self.lab)
                     for litter in self.litters for _ in range(2)]

    def assertIndexes(self, litter, subject):
        self.line.refresh_from_db()
        self.assertEqual(self.line.litter_autoname_index, litter)
        self.assertEqual(self.line.subject_autoname_index, subject)

    def delete(self, *objs):
        """Delete the objects, or querysets, one after the other in one transaction."""
        with self.captureOnCommitCallbacks(execute=True):
            for obj in objs:
                obj.delete()

    def test_litter_created_by_mistake(self):
        self.assertEqual([lt.name for lt in self.litters], ['LN_L_001', 'LN_L_002'])
        self.assertEqual([p.nickname for p in self.pups],
                         ['LN_0001', 'LN_0002', 'LN_0003', 'LN_0004'])
        # Oldest first, as from the pups inline of the litter admin
        self.delete(self.pups[2], self.pups[3])
        self.assertIndexes(2, 2)
        self.delete(self.litters[1])
        self.assertIndexes(1, 2)
        litter = Litter.objects.create(line=self.line)
        pup = Subject.objects.create(line=self.line, litter=litter, lab=self.lab)
        self.assertEqual((litter.name, pup.nickname), ('LN_L_002', 'LN_0003'))

    def test_separate_deletes(self):
        """Across transactions only the newest steps back, so the newest must go first."""
        self.delete(self.pups[3])
        self.delete(self.pups[2])
        self.assertIndexes(2, 2)
        self.delete(self.pups[0])
        self.delete(self.pups[1])
        self.assertIndexes(2, 1)  # LN_0001 stays unused

    def test_bulk_delete(self):
        # The litter first leaves its pups without a litter
        self.delete(Litter.objects.filter(pk=self.litters[1].pk))
        self.assertIndexes(1, 4)
        self.delete(Subject.objects.filter(pk__in=[p.pk for p in self.pups[2:]]))
        self.assertIndexes(1, 2)

    def test_proxy_delete(self):
        """Deleting from the cull subject admin, which uses a proxy model, frees the name."""
        self.delete(apps.get_model('subjects', 'CullSubject').objects.get(pk=self.pups[3].pk))
        self.assertIndexes(2, 3)

    def test_renamed(self):
        """The counter never goes back over a number it didn't just see deleted."""
        self.pups[3].nickname = 'KM_077'  # e.g. renamed to an experiment name
        self.pups[3].save()
        mistake = Subject.objects.create(line=self.line, lab=self.lab)
        self.assertEqual(mistake.nickname, 'LN_0005')
        self.delete(mistake, self.pups[2])
        self.assertIndexes(2, 4)
        manual = Subject.objects.create(nickname='LN_0010', line=self.line, lab=self.lab)
        self.delete(self.pups[3], manual)  # not an autoname, and above the counter
        self.assertIndexes(2, 4)

    def test_subject_with_sessions(self):
        """A subject with sessions keeps its name, which its data folders on disk have too."""
        Session.objects.create(subject=self.pups[3])
        self.delete(self.pups[2], self.pups[3])
        self.assertIndexes(2, 4)

    def test_rollback(self):
        """Deletions rolled back are forgotten, and don't count towards the next transaction."""
        with self.assertRaises(ZeroDivisionError), transaction.atomic():
            Subject.objects.get(pk=self.pups[3].pk).delete()
            1 / 0
        self.assertIndexes(2, 4)
        self.delete(Subject.objects.filter(pk=self.pups[3].pk))
        self.assertIndexes(2, 3)

    def test_database_alias(self):
        """Deleting from another database, e.g. a copy being pruned, only uses that database."""
        # The alias is not configured, so only using the default database would succeed
        with self.assertRaises(ConnectionDoesNotExist):
            pre_delete.send(sender=Subject, instance=self.pups[3], using='pruned_copy')
        line = Line.objects.get(pk=self.line.pk)
        line._state.db = 'pruned_copy'
        with self.assertRaises(ConnectionDoesNotExist):
            line.release_autonames(Subject, {4})
        self.assertIndexes(2, 4)

    def test_breeding_pair(self):
        self.delete(self.bp)
        self.line.refresh_from_db()
        self.assertEqual(self.line.breeding_pair_autoname_index, 0)
        self.assertEqual(BreedingPair.objects.create(line=self.line).name, 'LN_BP_001')

    def test_autoname_number(self):
        self.assertEqual(self.line.autoname_number(Litter, 'LN_L_001'), 1)
        self.assertEqual(self.line.autoname_number(Litter, 'LN_L_1000'), 1000)
        for name in ('LN_L_0001', 'LN_L_00\u00b2', 'LN_L_', 'LN_0001', 'LNX_L_001', 'Bob'):
            self.assertIsNone(self.line.autoname_number(Litter, name), name)
