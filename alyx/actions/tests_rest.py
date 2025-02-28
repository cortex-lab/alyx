import datetime
import numpy as np

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.timezone import now

from alyx import base
from alyx.base import BaseTests
from subjects.models import Subject, Project
from misc.models import Lab, Note, ContentType
from actions.models import (
    Session,
    WaterType,
    WaterAdministration,
    Surgery,
    ProcedureType,
)
from data.models import Dataset, DatasetType, FileRecord, DataRepository


class APIActionsBaseTests(BaseTests):
    def setUp(self):
        base.DISABLE_MAIL = True
        self.superuser = get_user_model().objects.create_superuser(
            "test", "test", "test"
        )
        self.superuser2 = get_user_model().objects.create_superuser(
            "test2", "test2", "test2"
        )
        self.client.login(username="test", password="test")
        self.subject = Subject.objects.all().first()
        self.lab01 = Lab.objects.create(name="superlab")
        self.lab02 = Lab.objects.create(name="awesomelab")
        self.projectX = Project.objects.create(name="projectX")
        self.projectY = Project.objects.create(name="projectY")
        self.test_protocol = "test_passoire"
        # Create a surgery with an implant weight.
        self.surgery = Surgery.objects.create(
            subject=self.subject,
            implant_weight=4.56,
            start_time=now() - datetime.timedelta(days=7),
        )
        implant_proc, _ = ProcedureType.objects.get_or_create(name="Headplate implant")
        self.surgery.procedures.add(implant_proc.pk)
        self.subject.save()

    def tearDown(self):
        base.DISABLE_MAIL = False


class APIActionsSessionsTests(APIActionsBaseTests):
    def test_sessions_projects(self):
        ses1dict = {
            "subject": self.subject.nickname,
            "users": [self.superuser.username],
            "projects": [self.projectX.name, self.projectY.name],
            "start_time": "2020-07-09T12:34:56",
            "end_time": "2020-07-09T12:34:57",
            "type": "Base",
            "number": "1",
            "lab": self.lab01.name,
            "task_protocol": self.test_protocol,
        }
        ses2dict = {
            "subject": self.subject.nickname,
            "users": [self.superuser.username, self.superuser2.username],
            "projects": [self.projectX.name],
            "start_time": "2020-07-09T12:34:56",
            "end_time": "2020-07-09T12:34:57",
            "type": "Base",
            "number": "2",
            "lab": self.lab01.name,
            "task_protocol": self.test_protocol,
        }
        self.ar(self.post(reverse("session-list"), data=ses1dict), 201)
        self.ar(self.post(reverse("session-list"), data=ses2dict), 201)
        # Test the user filter, this should return 2 sessions
        d = self.ar(
            self.client.get(reverse("session-list") + f"?projects={self.projectX.name}")
        )
        self.assertEqual(len(d), 2)
        # This should return only one session
        d = self.ar(
            self.client.get(reverse("session-list") + f"?projects={self.projectY.name}")
        )
        self.assertEqual(len(d), 1)
        # test the legacy filter that should act in the same way
        d = self.ar(
            self.client.get(reverse("session-list") + f"?project={self.projectX.name}")
        )
        self.assertEqual(len(d), 2)
        d = self.ar(
            self.client.get(reverse("session-list") + f"?projects={self.projectY.name}")
        )
        self.assertEqual(len(d), 1)

    def test_sessions(self):
        a_dict4json = {
            "String": "this is not a JSON",
            "Integer": 4,
            "List": ["titi", 4],
        }
        ses_dict = {
            "subject": self.subject.nickname,
            "users": [self.superuser2.username],
            "projects": [self.projectX.name, self.projectY.name],
            "narrative": "auto-generated-session, test",
            "start_time": "2018-07-09T12:34:56",
            "end_time": "2018-07-09T12:34:57",
            "type": "Base",
            "number": "1",
            "parent_session": "",
            "lab": self.lab01.name,
            "n_trials": 100,
            "n_correct_trials": 75,
            "task_protocol": self.test_protocol,
            "json": a_dict4json,
        }
        # Test the session creation
        r = self.post(reverse("session-list"), data=ses_dict)
        self.ar(r, 201)
        s1_details = r.data
        # makes sure the task_protocol is returned
        self.assertEqual(self.test_protocol, s1_details["task_protocol"])
        # the json is in the session details
        r = self.client.get(reverse("session-list") + "/" + s1_details["url"][-36:])
        self.assertEqual(r.data["json"], a_dict4json)
        # but not in the session list
        r = self.client.get(reverse("session-list") + "?id=" + s1_details["url"][-36:])
        s1 = self.ar(r)[0]
        self.assertFalse("json" in s1)
        # create another session for further testing
        ses_dict["start_time"] = "2018-07-11T12:34:56"
        ses_dict["end_time"] = "2018-07-11T12:34:57"
        # should use default user when not provided
        del ses_dict["users"]
        ses_dict["lab"] = self.lab02.name
        ses_dict["n_correct_trials"] = 37
        r = self.post(reverse("session-list"), data=ses_dict)
        s2 = self.ar(r, code=201)
        self.assertEqual(["test"], s2["users"])
        s2.pop("json")
        # Test the date range filter
        r = self.client.get(
            reverse("session-list") + "?date_range=2018-07-09,2018-07-09"
        )
        rdata = self.ar(r)
        self.assertEqual(rdata[0], s1)
        # Test the user filter, this should return 1 session
        d = self.ar(self.client.get(reverse("session-list") + "?users=test"))
        self.assertEqual(len(d), 1)
        # This should return 0 sessions
        d = self.ar(self.client.get(reverse("session-list") + "?users=foo"))
        self.assertEqual(len(d), 0)
        # This should return only one session
        d = self.ar(self.client.get(reverse("session-list") + "?lab=awesomelab"))
        self.assertEqual(len(d), 1)
        for k in d[0]:
            self.assertEqual(d[0][k], s2[k])
        # Test performance: gte, lte and ensures null performances not included
        d = self.ar(self.client.get(reverse("session-list") + "?performance_gte=50"))
        self.assertEqual(d[0]["url"], s1["url"])
        self.assertTrue(len(d) == 1)
        d = self.ar(self.client.get(reverse("session-list") + "?performance_lte=50"))
        self.assertEqual(d[0]["url"], s2["url"])
        self.assertEqual(1, len(d))
        # test the Session serializer water admin related field
        ses = Session.objects.get(
            subject=self.subject,
            users=self.superuser2,
            lab__name="superlab",
            start_time__date="2018-07-09",
        )
        WaterAdministration.objects.create(
            subject=self.subject, session=ses, water_administered=1
        )
        d = self.ar(
            self.client.get(
                reverse("session-list") + "?date_range=2018-07-09,2018-07-09"
            )
        )
        d = self.ar(self.client.get(d[0]["url"]))
        self.assertEqual(d["wateradmin_session_related"][0]["water_administered"], 1)
        # test the Notes
        ct = ContentType.objects.filter(model="session")[0]
        Note.objects.create(
            user=self.superuser,
            text="gnagnagna",
            content_type=ct,
            object_id=s1["url"][-36:],
        )
        d = self.ar(self.client.get(reverse("session-detail", args=[s1["url"][-36:]])))
        self.assertEqual("gnagnagna", d["notes"][0]["text"])
        # test dataset type filters

    def test_sessions_with_related_datasets(self):
        """
        This tests the query of sessions with related datasets
        :return:
        """

        data_repository = DataRepository.objects.get_or_create(
            name="test_repo", globus_is_personal=False
        )[0]
        dataset_types = {
            "_ibl_trials.table.pqt": DatasetType.objects.get_or_create(
                name="trials.table"
            )[0],
            "_ibl_wheel.position.npy": DatasetType.objects.get_or_create(
                name="wheel.position"
            )[0],
        }
        qc_dict = {
            "_ibl_trials.table.pqt": 30,  # all trials set to warning
            "_ibl_wheel.position.npy": 40,  # wheel position set to fail
        }
        dataset_links = {
            "n_trials_non_exist": [0, 0, 0, 0, 1, 0, 0, 1],
            "n_trials_exists": [0, 1, 1, 1, 0, 2, 2, 1],
            "n_wheel_non_exist": [0, 0, 0, 1, 1, 1, 0, 0],
            "n_wheel_exists": [0, 1, 0, 0, 0, 0, 0, 0],
        }

        def create_dataset(session, name, collection, exists):
            print(f"Creating dataset {name} for session {session}, exists={exists}")
            dset = Dataset.objects.create(
                session=Session.objects.get(pk=session),
                name=name,
                dataset_type=dataset_types[name],
                qc=qc_dict[name],
                collection=collection,
            )
            FileRecord.objects.create(
                dataset=dset,
                data_repository=data_repository,
                exists=exists,
                relative_path=f"{session}/{collection}",
            )

        sessions = []
        for i in range(8):
            dset_count = 0
            ses_dict = {
                "subject": self.subject.nickname,
                "users": [self.superuser.username],
                "projects": [self.projectX.name],
                "start_time": datetime.datetime(2020, 7, i + 1, 12, 34, 56),
                "end_time": datetime.datetime(2020, 7, i + 1, 13, 34, 56),
                "type": "Base",
                "number": "1",
                "lab": self.lab01.name,
                "task_protocol": self.test_protocol,
            }
            r = self.ar(self.post(reverse("session-list"), data=ses_dict), 201)
            for exists in [False] * dataset_links["n_trials_non_exist"][i] + [
                True
            ] * dataset_links["n_trials_exists"][i]:
                create_dataset(
                    session=r["id"],
                    name="_ibl_trials.table.pqt",
                    collection=str(dset_count),
                    exists=exists,
                )
                dset_count += 1
            for exists in [False] * dataset_links["n_wheel_non_exist"][i] + [
                True
            ] * dataset_links["n_wheel_exists"][i]:
                create_dataset(
                    session=r["id"],
                    name="_ibl_wheel.position.npy",
                    exists=exists,
                    collection=str(dset_count),
                )
                dset_count += 1
            sessions.append(r["id"])

        def assert_dataset_filter(query, expected_sessions):
            rses = [
                r["id"]
                for r in self.ar(self.client.get(reverse("session-list") + query))
            ]
            _, ises, _ = np.intersect1d(sessions, rses, return_indices=True)
            np.testing.assert_array_equal(np.sort(ises), expected_sessions)

        # only dataset index 1 has both wheel and trials
        assert_dataset_filter(
            "?datasets=_ibl_wheel.position.npy,_ibl_trials.table.pqt",
            expected_sessions=[1],
        )
        # only dataset index 1 has wheel
        assert_dataset_filter(
            "?datasets=_ibl_wheel.position.npy", expected_sessions=[1]
        )
        # only dataset index 1 has trials
        assert_dataset_filter(
            "?datasets=_ibl_trials.table.pqt", expected_sessions=[1, 2, 3, 5, 6, 7]
        )
        # the wheel dataset is failing qc
        assert_dataset_filter(
            "?datasets=_ibl_wheel.position.npy&dataset_qc_lte=WARNING",
            expected_sessions=[],
        )
        assert_dataset_filter(
            "?datasets=_ibl_wheel.position.npy,_ibl_trials.table.pqt&dataset_qc_lte=WARNING",
            expected_sessions=[],
        )
        assert_dataset_filter(
            "?datasets=_ibl_wheel.position.npy,_ibl_trials.table.pqt&dataset_qc_lte=FAIL",
            expected_sessions=[1],
        )
        # no dataset passes qc
        assert_dataset_filter("?dataset_qc_lte=10", expected_sessions=[])
        # NB: here the non-existent datasets are included in the dataset_qc_lte filter.
        # This may have to change
        assert_dataset_filter(
            "?dataset_qc_lte=WARNING", expected_sessions=[1, 2, 3, 4, 5, 6, 7]
        )


class APIActionsTests(APIActionsBaseTests):
    def test_create_weighing(self):
        url = reverse("weighing-create")
        data = {"subject": self.subject.nickname, "weight": 12.3}
        response = self.post(url, data)
        self.ar(response, 201)
        d = response.data
        self.assertTrue(d["date_time"])
        self.assertEqual(d["subject"], self.subject.nickname)
        self.assertEqual(d["weight"], 12.3)

    def test_create_water_administration(self):
        url = reverse("water-administration-create")
        ses_uuid = Session.objects.last().id
        water_type = WaterType.objects.last().name
        data = {
            "subject": self.subject.nickname,
            "water_administered": 1.23,
            "session": ses_uuid,
            "water_type": water_type,
        }
        response = self.post(url, data)
        self.ar(response, 201)
        d = response.data
        self.assertTrue(d["date_time"])
        self.assertEqual(d["subject"], self.subject.nickname)
        self.assertEqual(d["water_administered"], 1.23)
        self.assertEqual(d["water_type"], water_type)
        self.assertEqual(d["session"], ses_uuid)

    def test_list_water_administration_1(self):
        url = reverse("water-administration-create")
        response = self.client.get(url)
        d = self.ar(response)[0]
        self.assertTrue(
            set(
                (
                    "date_time",
                    "url",
                    "subject",
                    "user",
                    "water_administered",
                    "water_type",
                )
            ) <= set(d)
        )

    def test_list_water_administration_filter(self):
        url = reverse("water-administration-create")
        data = {"subject": self.subject.nickname, "water_administered": 1.23}
        response = self.post(url, data)
        url = (
            reverse("water-administration-create") + "?nickname=" + self.subject.nickname
        )
        response = self.client.get(url)
        d = self.ar(response)[0]
        self.assertTrue(
            set(
                (
                    "date_time",
                    "url",
                    "subject",
                    "user",
                    "water_administered",
                    "water_type",
                    "adlib",
                )
            ) <= set(d)
        )

    def test_list_weighing_1(self):
        url = reverse("weighing-create")
        response = self.client.get(url)
        d = self.ar(response)[0]
        self.assertTrue(
            set(("date_time", "url", "subject", "user", "weight")) <= set(d)
        )

    def test_list_weighing_filter(self):
        url = reverse("weighing-create")
        data = {"subject": self.subject.nickname, "weight": 12.3}
        response = self.post(url, data)

        url = reverse("weighing-create") + "?nickname=" + self.subject.nickname
        response = self.client.get(url)
        d = self.ar(response)[0]
        self.assertTrue(
            set(("date_time", "url", "subject", "user", "weight")) <= set(d)
        )

    def test_water_requirement(self):
        # Create water administered and weighing.
        self.post(
            reverse("water-administration-create"),
            {"subject": self.subject.nickname, "water_administered": 1.23},
        )
        self.post(
            reverse("weighing-create"),
            {"subject": self.subject.nickname, "weight": 12.3},
        )

        url = reverse("water-requirement", kwargs={"nickname": self.subject.nickname})

        date = now().date()
        start_date = date - datetime.timedelta(days=2)
        end_date = date + datetime.timedelta(days=2)
        response = self.client.get(
            url + "?start_date=%s&end_date=%s" %
            (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        )
        self.ar(response)
        d = response.data
        self.assertEqual(d["subject"], self.subject.nickname)
        self.assertEqual(d["implant_weight"], 4.56)
        self.assertTrue(
            set(
                (
                    "date",
                    "weight",
                    "expected_weight",
                    "expected_water",
                    "given_water_reward",
                    "given_water_supplement",
                )
            ) <= set(d["records"][0])
        )
        dates = sorted(_["date"] for _ in d["records"])
        assert len(dates) == 5
        assert dates[0] == start_date
        assert dates[-1] == end_date
        assert dates[2] == date
        assert d["records"][2]["weighing_at"] > 0
        for i in range(2, 5):
            assert d["records"][i]["weight"] > 0

    def test_extended_qc_filters(self):
        extended_qc = [
            {"tutu_bool": True, "tata_pct": 0.3},
            {"tutu_bool": False, "tata_pct": 0.4},
            {"tutu_bool": False, "tata_pct": 0.5},
            {"tutu_bool": True, "tata_pct": 0.6},
        ]
        ses = Session.objects.all()
        # patch the first 4 sessions the QCs above
        for i, ext_qc in enumerate(extended_qc):
            r = self.patch(
                reverse("session-detail", args=[ses[i].pk]),
                data={"extended_qc": ext_qc},
            )
            data = self.ar(r)
            self.assertEqual(data["extended_qc"], ext_qc)

        def check_filt(filt, qs):
            d = self.ar(self.client.get(reverse("session-list") + filt))
            uuids = Session.objects.filter(
                pk__in=[dd["url"][-36:] for dd in d]
            ).values_list("pk", flat=True)
            self.assertTrue(set(qs.values_list("pk", flat=True)) == set(uuids))

        check_filt(
            "?extended_qc=tutu_bool,True",
            Session.objects.filter(extended_qc__tutu_bool=True),
        )
        check_filt(
            "?extended_qc=tutu_bool,False",
            Session.objects.filter(extended_qc__tutu_bool=False),
        )
        check_filt(
            "?extended_qc=tata_pct__gte,0.5",
            Session.objects.filter(extended_qc__tata_pct__gte=0.5),
        )

        check_filt(
            "?extended_qc=tata_pct__lt,0.5,tutu_bool,True",
            Session.objects.filter(
                extended_qc__tata_pct__lt=0.5, extended_qc__tutu_bool=True
            ),
        )

    def test_procedures(self):
        self.ar(self.client.get(reverse("procedures-list")), 200)

    def test_surgeries(self):
        from actions.models import Surgery

        ns = Surgery.objects.all().count()
        sr = self.ar(
            self.client.get(
                reverse(
                    "surgeries-list",
                )
            )
        )
        self.assertTrue(ns > 0)
        self.assertTrue(len(sr) == ns)
        self.assertTrue(
            set(sr[0].keys()) == {
                "id",
                "subject",
                "name",
                "json",
                "narrative",
                "start_time",
                "end_time",
                "outcome_type",
                "lab",
                "location",
                "users",
                "procedures",
                "implant_weight",
            }
        )

    def test_list_retrieve_water_restrictions(self):
        url = reverse("water-restriction-list")
        response = self.client.get(url)
        d = self.ar(response)[0]
        self.assertTrue(
            set(d.keys()) >= set(
                ["reference_weight", "water_type", "subject", "start_time", "end_time"]
            )
        )
        url = reverse("water-restriction-list") + "?subject=" + d["subject"]
        response = self.client.get(url)
        d2 = self.ar(response)[0]
        self.assertEqual(d, d2)

    def test_list_retrieve_lab_locations(self):
        # test list
        url = reverse("location-list")
        l = self.ar(self.client.get(url))
        self.assertTrue(len(l) > 0)
        self.assertEqual(set(l[0].keys()), {"name", "json", "lab"})
        # test detail
        url = reverse("location-detail", args=[l[0]["name"]])
        d = self.ar(self.client.get(url))
        self.assertEqual(d, l[0])
        # test patch
        url = reverse("location-detail", args=[l[0]["name"]])
        json_dict = {
            "string": "look at me! I'm a Json field",
            "integer": 15,
            "list": ["tutu", 5],
        }
        p = self.ar(self.patch(url, data={"json": json_dict}))
        self.assertEqual(p["json"], json_dict)

    def test_custom_django_filters(self):
        d = self.ar(
            self.client.get(
                reverse("session-list") + "?django=start_time__date__lt,2017-06-05"
            )
        )
        fcount = Session.objects.filter(start_time__date__lt="2017-06-05").count()
        self.assertTrue(len(d) == fcount)
        # performs the reverse query and makes sure we have all the sessions
        resp = self.client.get(
            reverse("session-list") + "?django=~start_time__date__lt,2017-06-05"
        )
        self.ar(resp)
        self.assertTrue(len(d) + resp.data["count"] == Session.objects.count())
