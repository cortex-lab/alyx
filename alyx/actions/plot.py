import io

from django.http import HttpResponse
from subjects.models import Subject
from actions.models import Weighing, WaterRestriction


class Bunch(dict):
    def __init__(self, *args, **kwargs):
        super(Bunch, self).__init__(*args, **kwargs)
        self.__dict__ = self


def _plot_weighings(ax, weighings, *args, coeff=1., expected=False, **kwargs):
    if not weighings:
        return
    x, y = zip(*((w.date_time, (w.expected() if expected else w.weight) * coeff)
                 for w in weighings))
    ax.plot(x, y, *args, **kwargs)


def _plot_bands(ax, weighings, y0, y1):
    import numpy as np
    x = [w.date_time.date() for w in weighings]
    n = len(x)
    for threshold, fc in [(.8, '#FFE3D3'), (.7, '#FFC3C0')]:
        where = [w.weight < w.expected() * threshold for w in weighings]
        ax.fill_between(x, y0 * np.ones(n), y1 * np.ones(n), where=where,
                        interpolate=False, lw=0, facecolor=fc)
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
    weighings = list(Weighing.objects.filter(subject=subj,
                                             date_time__isnull=False).order_by('date_time'))

    # Empty data: skip.
    if not weighings:
        buf = io.BytesIO()
        f.savefig(buf, format='png')
        buf.seek(0)
        return HttpResponse(buf.read(), content_type="image/png")

    # Axes.
    ax.xaxis.set_major_locator(mpld.AutoDateLocator())
    ax.xaxis.set_major_formatter(mpld.DateFormatter('%d/%m/%y'))

    # Limits.
    start, end = weighings[0].date_time, weighings[-1].date_time
    ylim = (min(w.weight for w in weighings) - 3, max(w.weight for w in weighings) + 3)

    # Periods.
    wrs = WaterRestriction.objects.filter(subject=subj).order_by('start_time')
    periods = [(wr.start_time or start, wr.end_time or end) for wr in wrs]

    # Delimit water restriction periods.
    for a, b in periods:
        ax.axvspan(a, b, color='k', alpha=.05)
        ws = [w for w in weighings if (a <= w.date_time <= b)]

        # Bands.
        _plot_bands(ax, ws, *ylim)

        # Weighing curves.
        _plot_weighings(ax, ws, coeff=.8, expected=True, lw=2, color='#FF7F37')
        _plot_weighings(ax, ws, coeff=.7, expected=True, lw=2, color='#FF4137')
        _plot_weighings(ax, ws, lw=2, color='k')

    # Consider periods without water restriction.
    flat_periods = [item for sublist in periods for item in sublist]
    flat_periods.insert(0, start)
    flat_periods.append(end)
    ifp = iter(flat_periods)
    for a, b in zip(ifp, ifp):
        if a == b:
            continue
        ws = [w for w in weighings if (a < w.date_time < b)]
        _plot_weighings(ax, ws, 'ok')

    # Axes and legends.
    plt.xlim(start, end)
    # plt.ylim(*ylim)
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
