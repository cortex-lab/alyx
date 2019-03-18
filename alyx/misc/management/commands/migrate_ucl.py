import logging
import sys

from django.core.management.base import BaseCommand
from django.db.models import Count
from data.models import FileRecord

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)-15s %(message)s')


def duplicates():
    frs = FileRecord.objects.values('relative_path', 'data_repository') \
        .order_by('relative_path').annotate(dcount=Count('data_repository')) \
        .filter(dcount__gt=1)
    return frs


class Command(BaseCommand):
    help = "One-off migration script for UCL"

    def handle(self, *args, **options):
        for fr in duplicates():
            f = FileRecord.objects.filter(
                relative_path=fr['relative_path'],
                data_repository=fr['data_repository'])
            for _ in f[1:]:
                _.delete()
        print(duplicates().count())
