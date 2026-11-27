"""Create the group for pipeline users, the accounts that servers run pipelines with.

Members may change any record of the labs they are members of, whoever the responsible user is.
They get their other permissions from the 'Lab members' group, which set_user_permissions puts
every account in, and they should not have staff status, so that they can only use the REST
API. The command can be run again at any time. See docs/06_permissions.md.
"""
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from alyx.permissions import LAB_RECORDS_PERMISSION, get_or_create_permission
from misc.management.commands.set_user_permissions import (
    LAB_MEMBERS_GROUP, report_members_without_labs)

GROUP_NAME = 'Pipeline users'


class Command(BaseCommand):
    help = "Create/update the '%s' group." % GROUP_NAME

    def handle(self, *args, **options):
        group, created = Group.objects.get_or_create(name=GROUP_NAME)
        group.permissions.add(get_or_create_permission(LAB_RECORDS_PERMISSION))
        self.stdout.write("%s group '%s', which can change any record of its members' labs."
                          % ('Created' if created else 'Updated', GROUP_NAME))

        for user in group.user_set.order_by('username'):
            if user.is_staff:
                self.stdout.write(f'Warning: {user.username} has staff status, so can sign in '
                                  f'to the admin interface. Untick it for a pipeline user.')
            if not user.groups.filter(name=LAB_MEMBERS_GROUP).exists():
                self.stdout.write(f"Warning: {user.username} is not in '{LAB_MEMBERS_GROUP}', "
                                  f"so cannot add or change records: run set_user_permissions.")
        report_members_without_labs(group, self.stdout)
