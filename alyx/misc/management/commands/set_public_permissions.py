"""Create the group that grants read-only access to a public Alyx database.

Run this on the internal database as well as the public one. The group has to exist on both:
a public database built by copying and pruning the internal one inherits its groups, so a group
that only ever existed on the public side would be destroyed by the next release.
"""
import logging
import sys

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)-15s %(message)s')

GROUP_NAME = 'Public users'

# Models a public user has no business seeing in the admin, even read-only. Accounts and the
# permission structure itself are withheld: on a public database with self-registration, the
# user table holds email addresses and password hashes of members of the public.
EXCLUDED_MODELS = (
    ('misc', 'labmember'),
    ('auth', 'group'),
    ('auth', 'permission'),
    ('authtoken', 'token'),
    ('authtoken', 'tokenproxy'),
    ('sessions', 'session'),
    ('admin', 'logentry'),
    ('reversion', 'revision'),
    ('reversion', 'version'),
    ('contenttypes', 'contenttype'),
)


class Command(BaseCommand):
    help = "Create/update the '%s' group with read-only permissions." % GROUP_NAME

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            '--database', action='store', dest='database', default='default',
            help='Database alias to operate on (default: default)')

    def handle(self, *args, **options):
        database = options['database']
        group, created = Group.objects.using(database).get_or_create(name=GROUP_NAME)

        # View permissions only. Add/change/delete are additionally refused for public users by
        # alyx.base.BaseAdmin and BaseRestPublicPermission, but there is no reason to grant them
        # here and then rely on that.
        permissions = Permission.objects.using(database).filter(codename__startswith='view_')
        for app_label, model in EXCLUDED_MODELS:
            permissions = permissions.exclude(
                content_type__app_label=app_label, content_type__model=model)

        group.permissions.set(permissions)
        group.save()

        self.stdout.write(
            "%s group '%s' on database '%s' with %d view permissions."
            % ('Created' if created else 'Updated', GROUP_NAME, database, permissions.count()))
        self.stdout.write(
            'Excluded models: %s' % ', '.join(f'{a}.{m}' for a, m in EXCLUDED_MODELS))
