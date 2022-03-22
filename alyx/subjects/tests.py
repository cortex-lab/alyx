from datetime import datetime
import logging
from operator import attrgetter
import os.path as op
import sys
from uuid import UUID
import warnings

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.test.client import RequestFactory

from .admin import mysite
from subjects.models import Subject
from actions.models import Cull, CullMethod, WaterRestriction
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

    def test_history(self):
        from subjects.models import Subject, _has_field_changed

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


class SubjectProtocolNumber(TestCase):

    def setUp(self):
        self.lab = Lab.objects.create(name='awesomelab')
        self.sub = Subject.objects.create(nickname='lawes', lab=self.lab, birth_date='2019-01-01')

    def test_protocol_number(self):
        from actions.models import Surgery
        assert self.sub.protocol_number == '1'
        # after a surgery protocol number goes to 2
        self.surgery = Surgery.objects.create(
            subject=self.sub, start_time=datetime(2019, 1, 1, 12, 0, 0))
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
        self.assertEqual(self.sub1.cull_method, str(cull.cull_method))
        self.assertEqual(self.sub1.death_date, cull.date)
        # [CR] WARNING: the water restriction is closed at the first save (Cull creation), but NOT
        # at the second save, when the cull date has been changed. I don't think the closed
        # water restriction's end time should be silently updated to reflect this.
        # This is why we have a NotEqual.
        self.assertNotEqual(
            WaterRestriction.objects.get(subject=self.sub1).end_time.strftime('%Y-%m-%d'),
            cull.date)
        # now make sure that when the Cull object is deleted, the corresponding subject has his
        # death_date set to None
        cull.delete()
        self.assertIsNone(self.sub1.death_date)
        self.assertEqual(self.sub1.cull_method, '')
        self.assertTrue(self.sub1.alive())

    def test_update_subject_death(self):
        # now add a death date and make sure a cull action is created
        self.assertFalse(hasattr(self.sub2, 'cull'))
        self.sub2.death_date = '2019-07-18'
        self.sub2.save()
        self.assertEqual(self.sub2.cull.date, self.sub2.death_date)
        # it should work on updates too
        self.sub2.death_date = '2019-07-11'
        self.sub2.cull_method = 'CO2'
        self.sub2.save()
        self.assertEqual(self.sub2.cull.date, self.sub2.death_date)
        self.assertEqual(str(self.sub2.cull.cull_method), self.sub2.cull_method)
