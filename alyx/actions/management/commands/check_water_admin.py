from django.core.management import BaseCommand
from actions.models import WaterRestriction
from actions.notifications import check_water_administration, check_weighed


class Command(BaseCommand):
    help = "Check all water administrations and weighings."

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        wrs = WaterRestriction.objects.select_related('subject'). \
            filter(
                subject__death_date__isnull=True,
                start_time__isnull=False,
                end_time__isnull=True). \
            order_by('subject__responsible_user__username', 'subject__nickname')
        for wr in wrs:
            check_water_administration(wr.subject)
            check_weighed(wr.subject)
