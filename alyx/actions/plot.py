import io
import matplotlib.pyplot as plt

from django.http import HttpResponse
from subjects.models import Subject
from actions.models import Weighing


def weighing_plot(request, subject_id=None):
    subj = Subject.objects.get(pk=subject_id)
    weighins = Weighing.objects.filter(subject_id=subj.id).order_by('date_time')
    x, y = zip(*((w.date_time, w.weight) for w in weighins))
    f, ax = plt.subplots(1, 1)
    ax.plot(x, y)

    buf = io.BytesIO()
    f.savefig(buf, format='png')
    buf.seek(0)
    return HttpResponse(buf.read(), content_type="image/png")
