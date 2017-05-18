import io

from django.http import HttpResponse
from subjects.models import Subject
from actions.models import Weighing
from subjects.water import expected_weighing


class Bunch(dict):
    def __init__(self, *args, **kwargs):
        super(Bunch, self).__init__(*args, **kwargs)
        self.__dict__ = self


def _plot_weighings(ax, weighings, coeff=1., *args, **kwargs):
    if not weighings:
        return
    x, y = zip(*((w.date_time, w.weight * coeff) for w in weighings))
    ax.plot(x, y, *args, **kwargs)


def _plot_bands(ax, weighings, eweighings, y0, y1):
    import numpy as np
    x = [w.date_time.date() for w in weighings]
    n = len(x)
    for threshold, fc in [(.8, '#FFE3D3'), (.7, '#FFC3C0')]:
        where = [w.weight < ew.weight * threshold for w, ew in zip(weighings, eweighings)]
        ax.fill_between(x, y0 * np.ones(n), y1 * np.ones(n), where=where,
                        interpolate=False,
                        lw=0,
                        facecolor=fc,
                        )
        for i in np.nonzero(where)[0]:
            ax.axvline(x[i], lw=10, color=fc)


def weighing_plot(request, subject_id=None):
    if not request.user.is_authenticated():
        return HttpResponse('')
    if subject_id in (None, 'None'):
        return HttpResponse('')

    # Import matplotlib.
    try:
        import matplotlib
    except ImportError:
        return HttpResponse('Please install numpy and matplotlib.')
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mpld
    f, ax = plt.subplots(1, 1, figsize=(8, 3))

    # Get data.
    subj = Subject.objects.get(pk=subject_id)
    weighings = [w for w in Weighing.objects.filter(subject=subj, date_time__isnull=False)
                                            .order_by('date_time')]
    eweighings = [Bunch(date_time=w.date_time,
                        weight=expected_weighing(subj, w.date_time))
                  for w in weighings]

    weights = ([w.weight for w in weighings] +
               [w.weight * .7 for w in eweighings] +
               [w.weight * .8 for w in weighings])

    if weighings:
        xlim = weighings[0].date_time, weighings[-1].date_time
        ylim = min(weights) - 1, max(weights) + 1

        # Axes.
        ax.xaxis.set_major_locator(mpld.AutoDateLocator())
        ax.xaxis.set_major_formatter(mpld.DateFormatter('%d/%m/%y'))

        # Bands.
        _plot_bands(ax, weighings, eweighings, *ylim)

        # Weighing curves.
        _plot_weighings(ax, eweighings, coeff=.8, lw=2, color='#FF7F37')
        _plot_weighings(ax, eweighings, coeff=.7, lw=2, color='#FF4137')
        _plot_weighings(ax, weighings, lw=2, color='k')

        plt.xlim(*xlim)
        plt.ylim(*ylim)

    ax.set_title("Weighings for %s" % subj.nickname)
    plt.xlabel('Date')
    plt.ylabel('Weight (g)')
    plt.tight_layout()
    plt.grid('on')

    # Return the PNG.
    buf = io.BytesIO()
    f.savefig(buf, format='png')
    buf.seek(0)
    return HttpResponse(buf.read(), content_type="image/png")
