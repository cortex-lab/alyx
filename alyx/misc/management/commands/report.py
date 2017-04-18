from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from alyx.base import alyx_mail
from actions.models import WaterRestriction


class ReportMaker(object):
    def make_water_restriction(self, user):
        wr = WaterRestriction.objects.filter(start_time__isnull=False,
                                             end_time__isnull=True,
                                             subject__responsible_user=user,
                                             )
        subject = '%d mice on water restriction' % len(wr)
        text = "Mice on water restriction:\n"
        text += '\n'.join('* %s since %s' % (w.subject.nickname, w.start_time.date())
                          for w in wr)
        print(user.email, subject, text)


class Command(BaseCommand):
    help = "Generate daily reports"

    def add_arguments(self, parser):

        parser.add_argument('-U', '--users', nargs='*',
                            help='Usernames')

        parser.add_argument('names', nargs='*',
                            help='List of report names to make')

    def handle(self, *args, **options):
        rm = ReportMaker()
        users = options.get('users')
        users = User.objects.filter(username__in=users) if users else User.objects.all()
        for name in options.get('names'):
            method = getattr(rm, 'make_%s' % name, None)
            if method:
                self.stdout.write("Making report %s." % name)
                for user in users:
                    method(user)
