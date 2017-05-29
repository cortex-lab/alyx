from django.contrib.auth.models import User
from django.urls import reverse
from alyx.base import BaseTests


class APISubjectsTests(BaseTests):
    def setUp(self):
        self.superuser = User.objects.create_superuser('test', 'test', 'test')
        self.client.login(username='test', password='test')

    def test_list_subjects(self):
        url = reverse('subject-list')
        response = self.client.get(url)
        self.ar(response)
        d = response.data
        assert len(d) > 200
        assert set(('nickname', 'id', 'responsible_user', 'death_date', 'line', 'litter', 'sex', 'genotype', 'url')) <= set(d[0])


    def test_list_alive_subjects(self):
        url = reverse('subject-list') + '?alive=True&stock=True'
        response = self.client.get(url)
        self.ar(response)
        d = response.data
        assert len(d) > 200
        assert set(('nickname', 'id', 'responsible_user', 'death_date')) <= set(d[0])

        # also test that you can get some back when asking for non-stock
        url = reverse('subject-list') + '?alive=True&stock=False'
        response = self.client.get(url)
        self.ar(response)
        d = response.data
        assert len(d) > 0
        assert set(('nickname', 'id', 'responsible_user', 'death_date')) <= set(d[0])

    def test_subject(self):
        # test the individual subject endpoint, i.e. when you ask for a subject by name
        url = reverse('subject-list')
        response = self.client.get(url)
        self.ar(response)
        d = response.data

        response = self.client.get(d[0].url) # just ask for the first subject
        self.ar(response)
        d = response.data

        assert set(('nickname', 'id', 'responsible_user', 'death_date', 'line', 'litter', 'sex', 'genotype', 'url', 'water_requirement_total', 'water_requirement_remaining', 'weighings', 'water_administrations')) <= set(d[0])
        # would be good to check that weighings and water_administrations are not empty for some subject that has them. 
        # not sure how to do it, but maybe could get a random weighing and a random w_a and then query each of those particular subjects

# is this where to test weighings and water_admins? 
# Weighings should have weight and date_time
# W_A should have date_time, water_administered, and hydrogel
# they should each also have those fields when returned within a subject query

# for water-restricted-subjects endpoint, should return at least one record, which should have:
# nickname, water_requirement_total, water_requirement_remaining