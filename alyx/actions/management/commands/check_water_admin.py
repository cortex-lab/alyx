from django.core.management import BaseCommand
from actions.models import WaterRestriction
from actions.notifications import check_water_administration


class Command(BaseCommand):
    help = "Check all water administrations."

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        wrs = WaterRestriction.objects.filter(
            start_time__isnull=False, end_time__isnull=True). \
            select_related('subject'). \
            order_by('subject__nickname')
        for wr in wrs:
            check_water_administration(wr.subject)
