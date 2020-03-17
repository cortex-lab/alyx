from datetime import datetime

from django.urls import reverse
from django.contrib.auth import get_user_model

from alyx.base import BaseTests
from misc.models import LabMembership, Lab


class APIActionsTests(BaseTests):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')
        self.lab = Lab.objects.create(name='basement')

    def test_create_lab_membership(self):
        # first test creation of lab through rest endpoint
        response = self.post(reverse('lab-list'), {'name': 'superlab'})
        d = self.ar(response, 201)
        self.assertTrue(d['name'])
        # create a membership
        lm = LabMembership.objects.create(user=self.superuser, lab=self.lab)
        # date should be populated as default
        self.assertTrue(lm.start_date.date() == datetime.now().date())
        self.assertTrue(self.superuser.lab == [self.lab.name])
        # create an expired membership, should change output
        lm = LabMembership.objects.create(user=self.superuser,
                                          start_date=datetime(2018, 9, 1),
                                          end_date=datetime(2018, 10, 1),
                                          lab=Lab.objects.get(name='superlab'))
        self.assertTrue(self.superuser.lab == [self.lab.name])
        lm.end_date = None
        lm.save()
        self.assertTrue(set(self.superuser.lab) == set(['superlab', self.lab.name]))
        # now makes sure the REST endpoint returns the same thing
        response = self.client.get(reverse('user-list') + '/test')
        d = self.ar(response, 200)
        self.assertTrue(set(d['lab']) == set(self.superuser.lab))

    def test_user_rest(self):
        response = self.client.get(reverse('user-list') + '/test')
        self.ar(response, 200)
