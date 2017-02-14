import io
import matplotlib
matplotlib.use('Agg')  # noqa
import matplotlib.pyplot as plt
from matplotlib.dates import DayLocator, DateFormatter
import seaborn  # noqa

from django.http import HttpResponse
from subjects.models import Subject
from actions.models import Weighing


def weighing_plot(request, subject_id=None):
    if subject_id in (None, 'None'):
        return HttpResponse('')
    subj = Subject.objects.get(pk=subject_id)
    weighins = Weighing.objects.filter(subject_id=subj.id).order_by('date_time')
    if not weighins:
        return HttpResponse('')
    x, y = zip(*((w.date_time, w.weight) for w in weighins))

    f, ax = plt.subplots(1, 1, figsize=(8, 2))
    ax.xaxis.set_major_locator(DayLocator())
    ax.xaxis.set_major_formatter(DateFormatter('%d/%m/%y'))

    ax.plot(x, y)
    ax.set_title("Weighings for %s" % subj.nickname)
    plt.tight_layout()
    plt.grid('on')

    buf = io.BytesIO()
    f.savefig(buf, format='png')
    buf.seek(0)
    return HttpResponse(buf.read(), content_type="image/png")
