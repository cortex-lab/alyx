import logging

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from alyx.base import alyx_mail
from actions.models import Surgery, WaterRestriction
from subjects.models import Subject

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Generate daily reports"

    def add_arguments(self, parser):
        parser.add_argument('-U', '--users', nargs='*',
                            help='Usernames')
        parser.add_argument('names', nargs='*',
                            help='List of report names to make')

    def handle(self, *args, **options):
        users = options.get('users')
        users = (User.objects.filter(username__in=users).order_by('username')
                 if users else User.objects.all())
        for name in options.get('names'):
            method = getattr(self, 'make_%s' % name, None)
            if method:
                self.stdout.write("Making report %s." % name)
                for user in users:
                    method(user)

    def make_water_restriction(self, user):
        wr = WaterRestriction.objects.filter(start_time__isnull=False,
                                             end_time__isnull=True,
                                             subject__responsible_user=user,
                                             ).order_by('subject__nickname')
        if not wr:
            return
        if not user.email:
            logger.warn("Skipping user %s because there is no email.", user.username)
            return
        subject = '%d mice on water restriction' % len(wr)
        text = "Mice on water restriction:\n"
        text += '\n'.join('* %s since %s' % (w.subject.nickname, w.start_time.date())
                          for w in wr)
        alyx_mail(user.email, subject, text)

    def make_surgery(self, user):
        surgery_done = set([surgery.subject.nickname for surgery in
                            Surgery.objects.filter(subject__responsible_user=user)])
        subjects_user = set([subject.nickname for subject in
                             Subject.objects.filter(responsible_user=user)])
        surgery_pending = subjects_user - surgery_done
        if not surgery_pending:
            return
        if not user.email:
            logger.warn("Skipping user %s because there is no email.", user.username)
            return
        subject = '%d mice awaiting surgery' % len(surgery_pending)
        text = "Mice awaiting surgery:\n"
        text += '\n'.join('* %s' % nickname for nickname in surgery_pending)
        alyx_mail(user.email, subject, text)
