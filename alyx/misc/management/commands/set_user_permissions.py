import logging
import sys

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)-15s %(message)s')


class Command(BaseCommand):
    help = "Set the appropriate group and permissions."

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

    def handle(self, *args, **options):

        # Create the lab members group.
        group = Group.objects.get_or_create(name='Lab members')[0]
        group.save()

        # No right to delete except a few select models.
        group.permissions.add(*Permission.objects.exclude(codename__startswith='delete'))
        group.permissions.add(Permission.objects.get(codename='delete_surgery'))
        group.permissions.add(Permission.objects.get(codename='delete_wateradministration'))
        group.permissions.add(Permission.objects.get(codename='delete_waterrestriction'))
        group.permissions.add(Permission.objects.get(codename='delete_weighing'))
        group.permissions.add(Permission.objects.get(codename='delete_subjectrequest'))

        # Exclude some permissions.
        for m in ('group', 'permission'):
            group.permissions.remove(Permission.objects.get(codename='add_%s' % m))
            group.permissions.remove(Permission.objects.get(codename='change_%s' % m))

        group.save()
        self.stdout.write("%d permissions have been set on group %s." %
                          (len(group.permissions.all()), group))

        # Set user permissions.
        users = get_user_model().objects.all()
        for user in users:
            # Add all users to the group.
            user.groups.add(group)
            # Set super users for a few select users.
            user.is_superuser = user.username in settings.SUPERUSERS
            user.is_stock_manager = user.username in settings.STOCK_MANAGERS
            user.save()
        self.stdout.write("%d users have been successfully updated." % len(users))
