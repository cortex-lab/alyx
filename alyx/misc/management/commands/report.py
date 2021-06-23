from datetime import timedelta, date
import inspect
from itertools import groupby
import json
import logging
from operator import itemgetter
from textwrap import dedent

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from alyx.base import alyx_mail
from actions.models import Surgery, WaterRestriction, Session
from subjects.models import Subject

logger = logging.getLogger(__name__)


def _repr_log_entry(l):
    if l.is_addition():
        action = 'Added'
    elif l.is_change():
        action = 'Changed'
    elif l.is_deletion():
        action = 'Deleted'
    changed = json.loads(l.change_message or '[]')
    if changed and changed[0].get('changed', {}):
        changed = ('(%s)' %
                   (', '.join(changed[0].get('changed', {}).get('fields', {}))))
    else:
        changed = ''
    s = '%02d:%02d - %s <%s> %s' % (
        l.action_time.hour,
        l.action_time.minute,
        action,
        # l.content_type,

        # NOTE: use this when debugging repr (the repr string is directly saved in the LogEntry)
        # str(l.get_edited_object()),
        l.object_repr,

        changed,
    )
    return s


class Command(BaseCommand):
    help = "Generate daily reports"

    def add_arguments(self, parser):
        parser.add_argument('-U', '--users', nargs='*',
                            help='Usernames')
        parser.add_argument('names', nargs='*',
                            help='List of reports to make')
        parser.add_argument('--list', action='store_true', default=False,
                            help="List of available reports")
        parser.add_argument('--no-email', action='store_true', default=False,
                            help="Show report without sending an email")
        parser.add_argument('--lab', help='Lab for which to run the report')

    def handle(self, *args, **options):
        # Sort the list of pairs (user, text) by user to collate all emails for every user.
        # This is because groupby() requires the items to be already sorted.
        self.lab = options.get('lab')
        tuples = list(self._generate_email(*args, **options))
        tuples = sorted(tuples, key=lambda k: k[0].username)
        for user, texts in groupby(tuples, itemgetter(0)):
            subject = 'Report on %s' % timezone.now().strftime("%Y-%m-%d")
            self._send(user.email, subject, '\n\n'.join(t or '' for u, t in texts))

    def _generate_email(self, *args, **options):
        if options.get('list'):
            methods = inspect.getmembers(self, predicate=inspect.ismethod)
            names = sorted([m[0][5:] for m in methods if m[0].startswith('make_')])
            self.stdout.write(', '.join(names))
            return
        self.do_send = not options.get('no_email')
        users = options.get('users')
        users = (get_user_model().objects.filter(username__in=users).order_by('username')
                 if users else get_user_model().objects.all())
        for name in options.get('names'):
            method = getattr(self, 'make_%s' % name, None)
            if not method:
                continue
            logger.debug("Making report %s." % name)
            # First case: per-user report.
            if 'user' in inspect.getargspec(method)[0]:
                for user in users:
                    yield user, method(user)
            # Second case: global report to send to several users.
            else:
                text = method()
                for user in users:
                    yield user, text

    def _send(self, to, subject, text=''):
        self.stdout.write('"%s" to be sent to <%s>.\n\n' % (subject, to))
        self.stdout.write(text)
        self.stdout.write("\n\n")
        # NOTE: if there is no '*', it means the email is empty, so we don't send it.
        if to and self.do_send and '*' in text:
            alyx_mail(to, subject, text)
        elif self.do_send and '*' not in text:
            logger.debug("NOT sending an empty email.")

    def make_water_restriction(self, user):
        wr = WaterRestriction.objects.filter(start_time__isnull=False,
                                             end_time__isnull=True,
                                             subject__responsible_user=user,
                                             ).order_by('subject__nickname')
        if not wr:
            return
        text = "Mice on water restriction:\n"
        # Hench since 2017-04-20. Weight yesterday 27.2g (expected 30.0g, 90.7%).
        # Yesterday given 1.02mL (min 0.96mL, excess 0.06mL). Today requires 0.97mL.
        for w in wr:
            s = w.subject
            wc = s.water_control
            sn = w.subject.nickname
            sd = w.start_time.date()
            today = timezone.now()
            yesterday = (today - timedelta(days=1)).date()
            # Weight yesterday.
            wy = wc.last_weighing_before(date=yesterday)
            if wy is None:
                continue
            # Last date with weighing, might be yesterday or earlier.
            last_date = wy[0].date()
            # Number of days ago.
            n = (today.date() - last_date).days
            wy = wy[1]
            # Expected weight at the last date.
            wye = wc.expected_weight(date=last_date)
            wyep = wc.percentage_weight(date=last_date)
            # Water
            way = wc.given_water_total(date=last_date)
            waym = wc.expected_water(date=last_date)
            waye = wc.excess_water(date=last_date)
            wr = wc.remaining_water()  # remaining water TODAY
            s = '''
                * {sn} since {sd}.
                Weight {n} day(s) ago: {wy:.1f}g (expected {wye:.1f}g, {wyep:.1f}%).
                Given  {n} day(s) ago: {way:.2f}mL (min {waym:.2f}mL, excess {waye:.2f}mL).
                Today requires {wr:.2f}mL.
                '''.format(sn=sn, sd=sd, wy=wy, wye=wye, wyep=wyep,
                           n=n,
                           way=way, waym=waym, waye=waye, wr=wr)  # noqa
            text += dedent(s)
        return text

    def make_mouse_weight(self):
        wr = WaterRestriction.objects.filter(start_time__isnull=False,
                                             end_time__isnull=True,
                                             )
        if self.lab:
            wr = wr.filter(subject__lab__name=self.lab)
        subject_ids = [_[0] for _ in wr.values_list('subject').distinct()]
        text = ''
        for subject_id in subject_ids:
            subject = Subject.objects.get(pk=subject_id)
            wc = subject.water_control
            w = wc.weight()
            e = wc.expected_weight()
            p = wc.percentage_weight()
            last_weighing = wc.last_weighing_before()
            if not last_weighing:
                continue
            date = last_weighing[0]
            threshold = max(wc.zscore_weight_pct, wc.reference_weight_pct)
            if wc.weight_status() > 0:
                text += ('* {subject} ({user} <{email}>) weighed {weight:.1f}g '
                         'instead of {expected:.1f}g ({percentage:.1f}%) on {date}\n').format(
                             subject=subject,
                             user=subject.responsible_user,
                             email=subject.responsible_user.email,
                             weight=w,
                             expected=e,
                             percentage=p,
                             date=date,
                )
        text = 'Mice under the {t}% +2% weight limit:\n\n'.format(t=int(100 * threshold)) + text
        return text

    def make_surgery(self, user):
        # Skip surgeries on stock managers.
        if user.is_stock_manager:
            return
        surgery_done = set([surgery.subject.nickname for surgery in
                            Surgery.objects.filter(subject__responsible_user=user,
                                                   subject__cull__isnull=True)])
        subjects_user = set([subject.nickname for subject in
                             Subject.objects.filter(responsible_user=user,
                                                    cull__isnull=True)])
        surgery_pending = sorted(subjects_user - surgery_done)
        if not surgery_pending:
            return
        text = "Mice awaiting surgery:\n"
        text += '\n'.join('* %s' % nickname for nickname in surgery_pending)
        return text

    def make_past_changes(self, user):
        today = timezone.now()
        yesterday = (today - timedelta(days=1)).date()
        logs = LogEntry.objects.filter(user=user,
                                       action_time__date=yesterday,
                                       ).order_by('action_time')
        return 'Your actions yesterday:\n\n' + '\n'.join('* ' + _repr_log_entry(l) for l in logs)

    def make_training(self, user):
        """Send training report to the specified user."""
        wr = WaterRestriction.objects.filter(
            start_time__isnull=False, end_time__isnull=True,
        ).order_by('subject__responsible_user__username', 'subject__nickname')
        last_monday = date.today() - timedelta(days=date.today().weekday() + 5)
        next_monday = last_monday + timedelta(days=7)
        text = "Sessions between %s and %s:\n\n" % (last_monday, next_monday)
        for w in wr:
            sessions = Session.objects.filter(
                subject=w.subject, start_time__gte=last_monday, start_time__lt=next_monday)
            dates = sorted(set([_[0] for _ in sessions.order_by('start_time').
                                values_list('start_time__date')]))
            if len(dates) < 5:
                text += '* %s (%s) was trained %d days: %s\n' % (
                    w.subject.nickname, w.subject.responsible_user.username, len(dates),
                    ', '.join(d.strftime('%a %d %b') for d in dates)
                )
        return text

    def make_todo(self):
        tbg = Subject.objects.filter(to_be_genotyped=True).order_by('nickname')
        tbc = Subject.objects.filter(cull__isnull=True,
                                     to_be_culled=True).order_by('nickname')
        tbr = Subject.objects.filter(cull__isnull=False,
                                     reduced=False).order_by('nickname')

        text = "%d mice to be genotyped:\n" % len(tbg)
        text += '\n'.join('* %s' % s.nickname for s in tbg)

        text += "\n\n%d mice to be culled:\n" % len(tbc)
        text += '\n'.join('* %s' % s.nickname for s in tbc)

        text += "\n\n%d mice to be reduced:\n" % len(tbr)
        text += '\n'.join('* %s' % s.nickname for s in tbr)

        return text
