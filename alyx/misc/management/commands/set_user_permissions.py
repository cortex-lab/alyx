"""Create the standard groups for lab members and husbandry staff, and add accounts to them.

Every account except public users is put in the 'Lab members' group. The 'Husbandry' group is
created with the permission to change colony records of its members' labs; accounts are added
to it by hand. The command can be run again at any time. It makes sure the groups have their
standard permissions, and removes from 'Lab members' the permissions it must not have.

It leaves staff status and active status alone: whether an account can sign in to the admin
interface, or at all, is decided when it is created. See docs/06_permissions.md.
"""
import logging
import sys

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from alyx.permissions import CUSTOM_PERMISSIONS, LAB_COLONY_PERMISSION, get_or_create_permission
from misc.management.commands.set_public_permissions import EXCLUDED_APPS

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)-15s %(message)s')

LAB_MEMBERS_GROUP = 'Lab members'
HUSBANDRY_GROUP = 'Husbandry'

# Apps managed by superusers only: identities, email addresses and API tokens of other users.
# Removed rather than just not added, as earlier runs of this command may have granted them.
WITHHELD_APPS = EXCLUDED_APPS + ('authtoken',)

# The only models lab members may delete. Notes only their author may delete, which
# alyx.permissions checks.
DELETABLE_MODELS = ('surgery', 'wateradministration', 'waterrestriction', 'weighing',
                    'subjectrequest', 'note')


def report_members_without_labs(group, stdout):
    """Warn about members of group who are not currently a member of any lab.

    Their group gives them nothing: its permissions apply to the records of their labs.
    """
    for user in group.user_set.order_by('username'):
        if not user.lab_id().exists():
            stdout.write(f"Warning: {user.username} is in group '{group.name}' but not "
                         f"currently a member of any lab, so the group gives them nothing.")


class Command(BaseCommand):
    help = "Set up the 'Lab members' and 'Husbandry' groups and add accounts to 'Lab members'."

    def handle(self, *args, **options):
        group = Group.objects.get_or_create(name=LAB_MEMBERS_GROUP)[0]
        custom = [codename for codename, _ in CUSTOM_PERMISSIONS]

        # No right to delete except a few select models, and none of the custom permissions,
        # which are for the husbandry and pipeline users groups.
        group.permissions.add(*Permission.objects.exclude(
            codename__startswith='delete').exclude(codename__in=custom))
        group.permissions.add(*Permission.objects.filter(
            codename__in=[f'delete_{model}' for model in DELETABLE_MODELS]))

        # Exclude some permissions.
        for m in ('group', 'permission'):
            group.permissions.remove(Permission.objects.get(codename='add_%s' % m))
            group.permissions.remove(Permission.objects.get(codename='change_%s' % m))

        # Cannot change a few models.
        group.permissions.remove(Permission.objects.get(codename='change_project'))
        group.permissions.remove(Permission.objects.get(codename='add_project'))
        # group.permissions.remove(Permission.objects.get(codename='change_lab'))
        group.permissions.remove(Permission.objects.get(codename='change_datasettype'))
        group.permissions.remove(Permission.objects.get(codename='add_datasettype'))
        group.permissions.remove(
            *Permission.objects.filter(content_type__app_label__in=WITHHELD_APPS))
        group.permissions.remove(*Permission.objects.filter(codename__in=custom))

        self.stdout.write("%d permissions have been set on group %s." %
                          (group.permissions.count(), group))

        husbandry = Group.objects.get_or_create(name=HUSBANDRY_GROUP)[0]
        husbandry.permissions.add(get_or_create_permission(LAB_COLONY_PERMISSION))
        self.stdout.write("Group %s can change the colony records of its members' labs."
                          % husbandry)

        # Set user permissions.
        # Public users are deliberately skipped: adding them to the lab members group would
        # grant members of the public write access to every model.
        users = get_user_model().objects.exclude(is_public_user=True)
        for user in users:
            user.groups.add(group)
            # Set super users and stock managers for a few select users.
            user.is_superuser = user.is_superuser or user.username in settings.SUPERUSERS
            user.is_stock_manager = (
                user.is_stock_manager or user.username in settings.STOCK_MANAGERS)
            user.save(update_fields=['is_superuser', 'is_stock_manager'])
        skipped = get_user_model().objects.count() - users.count()
        self.stdout.write("%d users have been successfully updated." % users.count())
        if skipped:
            self.stdout.write("%d public/redacted users were skipped." % skipped)
        report_members_without_labs(husbandry, self.stdout)
