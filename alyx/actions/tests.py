import datetime
import numpy as np
from django.test import TestCase
from django.utils import timezone

from alyx import base
from actions.water_control import to_date
from actions.models import (
    WaterAdministration, WaterRestriction, WaterType, Weighing,
    Notification, NotificationRule, create_notification)
from actions.notifications import check_water_administration, check_weighed
from misc.models import LabMember, LabMembership, Lab
from subjects.models import Subject


class WaterControlTests(TestCase):
    fixtures = ['actions.watertype.json']

    def setUp(self):
        base.DISABLE_MAIL = True
        # create a subject
        self.lab = Lab.objects.create(name='test_lab')
        sub = Subject.objects.create(nickname='bigboy', birth_date='2018-09-01', lab=self.lab)
        self.sub = Subject.objects.get(pk=sub.pk)
        # 50 days of loosing weight and getting 0.98 mL water
        self.start_date = datetime.datetime(year=2018, month=10, day=1)
        self.rwind = 5  # water restriction will start on the fifth day
        self.wei = np.linspace(25, 20, 50)
        for n, w in enumerate(np.linspace(25, 20, 50)):
            date_w = datetime.timedelta(days=n) + self.start_date
            Weighing.objects.create(weight=w, subject=self.sub, date_time=date_w)
            WaterAdministration.objects.create(
                water_administered=0.98,
                subject=self.sub,
                date_time=date_w)
        # first test assert that water administrations previously created have the correct default
        wa = WaterAdministration.objects.filter(subject=self.sub)
        self.assertTrue(wa.values_list('water_type__name').distinct()[0][0] == 'Water')
        # create labs with different weight measurement techniques
        Lab.objects.create(name='zscore', reference_weight_pct=0, zscore_weight_pct=0.85)
        Lab.objects.create(name='rweigh', reference_weight_pct=0.85, zscore_weight_pct=0)
        Lab.objects.create(name='mixed', reference_weight_pct=0.425, zscore_weight_pct=0.425)
        # Create an initial Water Restriction
        start_wr = self.start_date + datetime.timedelta(days=self.rwind)
        water_type = WaterType.objects.get(name='Hydrogel 5% Citric Acid')
        self.wr = WaterRestriction.objects.create(subject=self.sub, start_time=start_wr,
                                                  water_type=water_type)
        # from now on new water administrations should have water_type as default
        wa = WaterAdministration.objects.create(
            water_administered=1.02,
            subject=self.sub,
            date_time=datetime.datetime.now())
        self.assertEqual(water_type, wa.water_type)

    def tearDown(self):
        base.DISABLE_MAIL = False

    def test_water_administration_expected(self):
        wc = self.sub.water_control
        wa = WaterAdministration.objects.filter(subject=self.sub)
        # the method from the wa model should return the expectation at the corresponding date
        self.assertTrue(wa[0].expected() == wc.expected_water(date=wa[0].date_time))
        self.assertTrue(wa[40].expected() == wc.expected_water(date=wa[40].date_time))

    def test_water_control_thresholds(self):
        # test computation on reference weight lab alone
        self.sub.lab = Lab.objects.get(name='rweigh')
        self.sub.save()
        wc = self.sub.reinit_water_control()
        wc.expected_weight()
        self.assertAlmostEqual(self.wei[self.rwind], wc.reference_weight())
        self.assertAlmostEqual(self.wei[self.rwind], wc.expected_weight())
        # test computation on zscore weight lab alone
        self.sub.lab = Lab.objects.get(name='zscore')
        self.sub.save()
        wc = self.sub.reinit_water_control()
        wc.expected_weight()
        self.assertAlmostEqual(self.wei[self.rwind], wc.reference_weight())
        zscore = wc.zscore_weight()
        # test computation on mixed lab
        self.sub.lab = Lab.objects.get(name='mixed')
        self.sub.save()
        wc = self.sub.reinit_water_control()
        self.assertAlmostEqual(self.wei[self.rwind], wc.reference_weight())
        self.assertAlmostEqual(wc.expected_weight(), (wc.reference_weight() + zscore) / 2)
        # test that the thresholds are all above 70%
        self.assertTrue(all([thrsh[0] > 0.4 for thrsh in wc.thresholds]))
        # if we change the reference weight of the water restriction, this should change in wc too
        self.assertAlmostEqual(wc.reference_weight(), self.wr.reference_weight)
        self.wr.reference_weight = self.wr.reference_weight + 1
        self.wr.save()
        wc = self.sub.reinit_water_control()
        self.assertAlmostEqual(wc.reference_weight(), self.wr.reference_weight)


class NotificationTests(TestCase):
    def setUp(self):
        base.DISABLE_MAIL = True
        self.lab = Lab.objects.create(name='testlab', reference_weight_pct=.85)

        self.user1 = LabMember.objects.create(username='test1')
        self.user2 = LabMember.objects.create(username='test2')

        LabMembership.objects.create(user=self.user1, lab=self.lab, start_date='2018-01-01')
        LabMembership.objects.create(user=self.user2, lab=self.lab, start_date='2018-01-01')

        self.subject = Subject.objects.create(
            nickname='test', birth_date=to_date('2018-01-01'), lab=self.lab,
            responsible_user=self.user1)
        Weighing.objects.create(
            subject=self.subject, weight=10,
            date_time=timezone.datetime(2018, 6, 1, 12, 0, 0)
        )
        self.water_restriction = WaterRestriction.objects.create(
            subject=self.subject,
            start_time=timezone.datetime(2018, 6, 2, 12, 0, 0),
            reference_weight=10.,
        )
        self.water_administration = WaterAdministration.objects.create(
            subject=self.subject,
            date_time=timezone.datetime(2018, 6, 3, 12, 0, 0),
            water_administered=10,
        )
        self.date = to_date('2018-06-10')

    def tearDown(self):
        base.DISABLE_MAIL = False

    def test_notif_weighing_0(self):
        n = len(Notification.objects.all())
        Weighing.objects.create(
            subject=self.subject, weight=9,
            date_time=timezone.datetime(2018, 6, 9, 8, 0, 0)
        )
        # No notification created here.
        self.assertTrue(len(Notification.objects.all()) == n)

    def test_notif_weighing_1(self):
        Weighing.objects.create(
            subject=self.subject, weight=7,
            date_time=timezone.datetime(2018, 6, 9, 12, 0, 0)
        )
        notif = Notification.objects.last()
        self.assertTrue(notif.title.startswith('WARNING: test weight was 70.0%'))

    def test_notif_weighing_2(self):
        Weighing.objects.create(
            subject=self.subject, weight=8.6,
            date_time=timezone.datetime(2018, 6, 9, 16, 0, 0)
        )
        notif = Notification.objects.last()
        self.assertTrue(notif.title.startswith('ATTENTION'))

    def test_notif_weighed(self):
        """Test for actions.notifications.check_weighed function."""
        check_weighed(self.subject, self.date)
        notif = Notification.objects.last()
        self.assertTrue(notif.title.startswith('ATTENTION'))
        self.assertIn('weighing missing', notif.title)
        self.assertIn(self.date.date().isoformat(), notif.title)

        # Create weighing for the day
        Weighing.objects.create(subject=self.subject, weight=25.,
                                date_time=self.date.replace(second=0, hour=0, minute=0))
        n = Notification.objects.count()
        check_weighed(self.subject, self.date)
        self.assertEqual(n, Notification.objects.count(), 'created unexpected notification')

    def test_notif_water_1(self):
        date = timezone.datetime(2018, 6, 3, 16, 0, 0)
        check_water_administration(self.subject, date=date)
        notif = Notification.objects.last()
        self.assertTrue(notif is None)

    def test_notif_water_2(self):
        # If the last water admin was on June 3 at 12pm, the notification
        # should be created after June 4 at 11am.
        l = ((9, False), (10, False), (11, True), (12, True))
        for (h, r) in l:
            date = timezone.datetime(2018, 6, 4, h, 0, 0)
            check_water_administration(self.subject, date=date)
            notif = Notification.objects.last()
            self.assertTrue((notif is not None) is r)

    def test_notif_user_change_1(self):
        self.subject.responsible_user = self.user2
        self.subject.save()
        notif = Notification.objects.last()
        self.assertTrue(notif is not None)
        self.assertEqual(notif.title, 'Responsible user of test changed from test1 to test2')

    def test_notif_rule_1(self):
        nt = 'mouse_water'
        nr = NotificationRule.objects.create(
            user=self.user1, notification_type=nt)

        def _assert_users(users, expected):
            n = create_notification(nt, '', subject=self.subject, users=users, force=True)
            self.assertEqual(list(n.users.all()), expected)

        _assert_users(None, [self.user1])

        nr.subjects_scope = 'none'
        nr.save()
        _assert_users(None, [])

        nr.subjects_scope = 'lab'
        nr.save()
        _assert_users(None, [self.user1])

        self.subject.responsible_user = self.user2
        self.subject.save()
        _assert_users(None, [self.user1, self.user2])

        nr.subjects_scope = 'all'
        nr.save()
        _assert_users(None, [self.user1, self.user2])

        nr.subjects_scope = 'mine'
        nr.save()
        _assert_users(None, [self.user2])

    def test_notif_rule_2(self):
        nt = 'mouse_water'
        nr = NotificationRule.objects.create(
            user=self.user1, notification_type=nt)

        def _assert_users(users, expected):
            n = create_notification(nt, '', subject=self.subject, users=users, force=True)
            self.assertEqual(list(n.users.all()), expected)

        _assert_users([], [self.user1])
        _assert_users([self.user1], [self.user1])
        _assert_users([self.user2], [self.user1, self.user2])
        _assert_users([self.user1, self.user2], [self.user1, self.user2])

        nr.subjects_scope = 'none'
        nr.save()
        _assert_users([self.user2], [self.user2])
