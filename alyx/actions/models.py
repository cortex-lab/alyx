from datetime import timedelta
import logging
from math import inf

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.contrib.postgres.fields import JSONField

from alyx.base import BaseModel, modify_fields, alyx_mail
from misc.models import Lab, LabLocation, LabMember, Note


logger = logging.getLogger(__name__)


def _default_water_type():
    s = WaterType.objects.filter(name='Water')
    if s:
        return s[0].pk
    return None


@modify_fields(name={
    'blank': False,
})
class ProcedureType(BaseModel):
    """
    A procedure to be performed on a subject.
    """
    description = models.TextField(blank=True,
                                   help_text="Detailed description "
                                   "of the procedure")

    def __str__(self):
        return self.name


class Weighing(BaseModel):
    """
    A weighing of a subject.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        help_text="The user who weighed the subject")
    subject = models.ForeignKey(
        'subjects.Subject', related_name='weighings',
        on_delete=models.CASCADE,
        help_text="The subject which was weighed")
    date_time = models.DateTimeField(
        null=True, blank=True, default=timezone.now)
    weight = models.FloatField(
        validators=[MinValueValidator(limit_value=0)],
        help_text="Weight in grams")

    def expected(self):
        """Expected weighing."""
        wc = self.subject.water_control
        return wc.expected_weight(self.date_time)

    def save(self, *args, **kwargs):
        super(Weighing, self).save(*args, **kwargs)
        from actions.notifications import check_weighing
        check_weighing(self.subject)

    def __str__(self):
        return 'Weighing %.2f g for %s' % (self.weight,
                                           str(self.subject),
                                           )


class WaterType(BaseModel):
    name = models.CharField(max_length=128, unique=True)

    def __str__(self):
        return self.name


class WaterAdministration(BaseModel):
    """
    For keeping track of water for subjects not on free water.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.SET_NULL,
                             help_text="The user who administered water")
    subject = models.ForeignKey('subjects.Subject',
                                on_delete=models.CASCADE,
                                related_name='water_administrations',
                                help_text="The subject to which water was administered")
    date_time = models.DateTimeField(null=True, blank=True,
                                     default=timezone.now)
    session = models.ForeignKey('Session', null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='wateradmin_session_related')
    water_administered = models.FloatField(validators=[MinValueValidator(limit_value=0)],
                                           null=True, blank=True,
                                           help_text="Water administered, in milliliters")
    water_type = models.ForeignKey(WaterType, null=True, blank=True, on_delete=models.SET_NULL)
    adlib = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.water_type:
            wr = WaterRestriction.objects.filter(subject=self.subject).\
                order_by('start_time').last()
            if wr:
                self.water_type = wr.water_type
            else:
                self.water_type = WaterType.objects.get(pk=_default_water_type())
        return super(WaterAdministration, self).save(*args, **kwargs)

    def expected(self):
        wc = self.subject.water_control
        return wc.expected_water(date=self.date_time)

    @property
    def hydrogel(self):
        return 'hydrogel' in self.water_type.name.lower() if self.water_type else None

    def __str__(self):
        if self.water_administered:
            return 'Water %.2fg for %s' % (self.water_administered,
                                           str(self.subject),
                                           )
        else:
            return 'Water adlib for %s' % str(self.subject)


class BaseAction(BaseModel):
    """
    Base class for an action performed on a subject, such as a recording;
    surgery; etc. This should always be accessed through one of its subclasses.
    """

    users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True,
                                   help_text="The user(s) involved in this action")
    subject = models.ForeignKey('subjects.Subject',
                                on_delete=models.CASCADE,
                                related_name="%(app_label)s_%(class)ss",
                                help_text="The subject on which this action was performed")
    location = models.ForeignKey(LabLocation, null=True, blank=True, on_delete=models.SET_NULL,
                                 help_text="The physical location at which the action was "
                                 "performed")
    lab = models.ForeignKey(Lab, null=True, blank=True, on_delete=models.SET_NULL)
    procedures = models.ManyToManyField('ProcedureType', blank=True,
                                        help_text="The procedure(s) performed")
    narrative = models.TextField(blank=True)
    start_time = models.DateTimeField(
        null=True, blank=True, default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return '%s for %s' % (self.__class__.__name__, self.subject)

    class Meta:
        abstract = True


class VirusInjection(BaseAction):
    """
    A virus injection.
    """
    INJECTION_TYPES = (
        ('I', 'Iontophoresis'),
        ('P', 'Pressure'),
    )
    virus_batch = models.CharField(max_length=255, null=True, blank=True)
    injection_volume = models.FloatField(
        null=True, blank=True, help_text="Volume in nanoliters")
    rate_of_injection = models.FloatField(
        null=True, blank=True, help_text="TODO: Nanoliters per second / per minute?")
    injection_type = models.CharField(max_length=1,
                                      choices=INJECTION_TYPES,
                                      default='I', blank=True,
                                      help_text="Whether the injection was through "
                                      "iontophoresis or pressure")


def _default_surgery_location():
    s = LabLocation.objects.filter(name='Surgery Room')
    if s:
        return s[0].pk
    return None


class Surgery(BaseAction):
    """
    Surgery performed on a subject.
    """
    OUTCOME_TYPES = (
        ('a', 'Acute'),
        ('r', 'Recovery'),
        ('n', 'Non-recovery'),
    )
    outcome_type = models.CharField(max_length=1,
                                    choices=OUTCOME_TYPES,
                                    blank=True,
                                    )
    location = models.ForeignKey(LabLocation, null=True, blank=True,
                                 on_delete=models.SET_NULL,
                                 default=_default_surgery_location,
                                 help_text="The physical location at which the surgery was "
                                 "performed")

    class Meta:
        verbose_name_plural = "surgeries"

    def save(self, *args, **kwargs):
        # Issue #422.
        if self.subject.protocol_number == '1':
            self.subject.protocol_number = '3'
        # Change from mild to moderate.
        if self.subject.actual_severity == 2:
            self.subject.actual_severity = 3

        if self.outcome_type == 'a' and self.start_time:
            self.subject.death_date = self.start_time
        self.subject.save()
        return super(Surgery, self).save(*args, **kwargs)


class Session(BaseAction):
    """
    A recording or training session performed on a subject. There is normally only one of
    these per day, for example corresponding to a  period of uninterrupted head fixation.

    Note that you can organize sessions hierarchically by assigning a parent_session.
    Sub-sessions could for example corresponding to periods of time in which the same
    neurons were recorded, or a particular set of stimuli were presented. Top-level sessions
    should have parent_session set to null.

    If the fields (e.g. users) of a subsession are null, they should inherited from the parent.
    """
    parent_session = models.ForeignKey('Session', null=True, blank=True,
                                       on_delete=models.SET_NULL,
                                       help_text="Hierarchical parent to this session")
    project = models.ForeignKey('subjects.Project', null=True, blank=True,
                                on_delete=models.SET_NULL, verbose_name='Session Project')
    type = models.CharField(max_length=255, null=True, blank=True,
                            help_text="User-defined session type (e.g. Base, Experiment)")
    number = models.IntegerField(null=True, blank=True,
                                 help_text="Optional session number for this level")
    task_protocol = models.CharField(max_length=1023, blank=True, default='')
    n_trials = models.IntegerField(blank=True, null=True)
    n_correct_trials = models.IntegerField(blank=True, null=True)

    QC_CHOICES = [
        (50, 'CRITICAL',),
        (40, 'FAIL',),
        (30, 'WARNING',),
        (0, 'NOT_SET',),
        (10, 'PASS',),
    ]

    qc = models.IntegerField(default=0, choices=QC_CHOICES)
    extended_qc = JSONField(null=True, blank=True,
                            help_text="Structured data about session QC,"
                                      "formatted in a user-defined way")

    def save(self, *args, **kwargs):
        # Default project is the subject's project.
        if not self.project_id:
            self.project = self.subject.projects.first()
        if not self.lab:
            self.lab = self.subject.lab
        return super(Session, self).save(*args, **kwargs)

    def __str__(self):
        try:
            string = "%s/%s/%s/%s" % (str(self.pk)[:8],
                                      self.subject,
                                      str(self.start_time)[:10],
                                      str(self.number).zfill(3))
        except Exception:
            string = "%s/%s" % (str(self.pk)[:8], self.subject)
        return string

    @property
    def notes(self):
        return Note.objects.filter(object_id=self.pk)


class EphysSession(Session):
    """
    This proxy class allows to register as a different admin page.
    The database is left untouched
    New methods are fine but not new fields
    """
    class Meta:
        proxy = True


class WaterRestriction(BaseAction):
    """
    Water restriction.
    """

    reference_weight = models.FloatField(
        validators=[MinValueValidator(limit_value=0)],
        default=0,
        help_text="Weight in grams")
    water_type = models.ForeignKey(WaterType, null=True, blank=True,
                                   default=_default_water_type, on_delete=models.SET_NULL,
                                   help_text='Default Water Type when creating water admin')

    def is_active(self):
        return self.start_time is not None and self.end_time is None

    def save(self, *args, **kwargs):
        if not self.reference_weight and self.subject:
            w = self.subject.water_control.last_weighing_before(self.start_time)
            if w:
                self.reference_weight = w[1]
                # makes sure the closest weighing is one week around, break if not
                assert(abs(w[0] - self.start_time) < timedelta(days=7))
        return super(WaterRestriction, self).save(*args, **kwargs)


class OtherAction(BaseAction):
    """
    Another type of action.
    """
    pass


# Notifications
# ---------------------------------------------------------------------------------

NOTIFICATION_TYPES = (
    ('responsible_user_change', 'responsible user has changed'),
    ('mouse_underweight', 'mouse is underweight'),
    ('mouse_water', 'water to give to mouse'),
    ('mouse_training', 'check training days'),
)


# Minimum delay, in seconds, until the same notification can be sent again.
NOTIFICATION_MIN_DELAYS = {
    'responsible_user_change': 3600,
    'mouse_underweight': 3600,
    'mouse_water': 3600,
}


def delay_since_last_notification(notification_type, title, subject):
    """Return the delay since the last notification corresponding to the given
    type, title, subject, in seconds, wheter it was actually sent or not."""
    last_notif = Notification.objects.filter(
        notification_type=notification_type,
        title=title,
        subject=subject).exclude(status='no-send').order_by('send_at').last()
    if last_notif:
        date = last_notif.sent_at or last_notif.send_at
        return (timezone.now() - date).total_seconds()
    return inf


def check_scope(user, subject, scope):
    if subject is None:
        return True
    # Default scope: mine.
    scope = scope or 'mine'
    assert scope in ('none', 'mine', 'lab', 'all')
    if scope == 'mine':
        return subject.responsible_user == user
    elif scope == 'lab':
        return subject.lab.name in (user.lab or ())
    elif scope == 'all':
        return True
    elif scope == 'none':
        return False


def get_recipients(notification_type, subject=None, users=None):
    """Return the list of users that will receive a notification."""
    # Default: initial list of recipients is the subject's responsible user.
    if users is None and subject and subject.responsible_user:
        users = [subject.responsible_user]
    if users is None:
        users = []
    if not subject:
        return users
    members = LabMember.objects.all()
    rules = NotificationRule.objects.filter(notification_type=notification_type)
    # Dictionary giving the scope of every user in the database.
    user_rules = {user: None for user in members}
    user_rules.update({rule.user: rule.subjects_scope for rule in rules})
    # Remove 'none' users from the specified users.
    users = [user for user in users if user_rules.get(user, None) != 'none']
    # Return the selected users, and those who opted in in the notification rules.
    return users + [member for member in members
                    if check_scope(member, subject, user_rules.get(member, None)) and
                    member not in users]


def create_notification(
        notification_type, message, subject=None, users=None, force=None, details=''):
    delay = delay_since_last_notification(notification_type, message, subject)
    max_delay = NOTIFICATION_MIN_DELAYS.get(notification_type, 0)
    if not force and delay < max_delay:
        logger.warning(
            "This notification was sent %d s ago (< %d s), skipping.", delay, max_delay)
        return
    notif = Notification.objects.create(
        notification_type=notification_type,
        title=message,
        message=message + '\n\n' + details,
        subject=subject)
    recipients = get_recipients(notification_type, subject=subject, users=users)
    if recipients:
        notif.users.add(*recipients)
    logger.debug(
        "Create notification '%s' for %s (%s %s)",
        message, ', '.join(map(str, notif.users.all())),
        notif.status, notif.send_at.strftime('%Y-%m-%d %H:%M'))
    notif.send_if_needed()
    return notif


def send_pending_emails():
    """Send all pending notifications."""
    notifications = Notification.objects.filter(status='to-send', send_at__lte=timezone.now())
    for notification in notifications:
        notification.send_if_needed()


class Notification(BaseModel):
    STATUS_TYPES = (
        ('no-send', 'do not send'),
        ('to-send', 'to send'),
        ('sent', 'sent'),
    )

    send_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    notification_type = models.CharField(max_length=32, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    subject = models.ForeignKey(
        'subjects.Subject', null=True, blank=True, on_delete=models.SET_NULL)
    users = models.ManyToManyField(LabMember)
    status = models.CharField(max_length=16, default='to-send', choices=STATUS_TYPES)

    def ready_to_send(self):
        return (
            self.status == 'to-send' and
            self.send_at <= timezone.now()
        )

    def send_if_needed(self):
        """Send the email if needed and change the status to 'sent'"""
        if self.status == 'sent':
            logger.warning("Email already sent at %s.", self.sent_at)
            return False
        if not self.ready_to_send():
            logger.warning("Email not ready to send.")
            return False
        emails = [user.email for user in self.users.all() if user.email]
        if alyx_mail(emails, self.title, self.message):
            self.status = 'sent'
            self.sent_at = timezone.now()
            self.save()
            return True

    def __str__(self):
        return "<Notification '%s' (%s) %s>" % (self.title, self.status, self.send_at)


class NotificationRule(BaseModel):
    """For each user and notification type, send the notifications for
    a given set of mice (none, all, mine, lab)."""

    SUBJECT_SCOPES = (
        ('none', 'none'),
        ('all', 'all'),
        ('mine', 'mine'),
        ('lab', 'lab')
    )

    user = models.ForeignKey(LabMember, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=32, choices=NOTIFICATION_TYPES)
    subjects_scope = models.CharField(max_length=16, choices=SUBJECT_SCOPES)

    class Meta:
        unique_together = [('user', 'notification_type')]

    def __str__(self):
        return "<Notification rule for %s: %s '%s'>" % (
            self.user, self.notification_type, self.subjects_scope)


class CullReason(BaseModel):
    description = models.TextField(blank=True, max_length=255)

    def __str__(self):
        return self.name


class CullMethod(BaseModel):
    description = models.TextField(blank=True, max_length=255)

    def __str__(self):
        return self.name


class Cull(BaseModel):
    """
    Culling action
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        help_text="The user who culled the subject")
    subject = models.OneToOneField(
        'subjects.Subject', related_name='cull', on_delete=models.CASCADE,
        help_text="The culled subject")
    date = models.DateField(null=False, blank=False)
    description = models.TextField(blank=True, max_length=255, help_text='Narrative/Details')

    cull_reason = models.ForeignKey(
        CullReason, null=True, blank=True, on_delete=models.SET_NULL,
        help_text="Reason for culling the subject")
    cull_method = models.ForeignKey(
        CullMethod, null=True, blank=True, on_delete=models.SET_NULL,
        help_text="How the subject was culled")

    def __str__(self):
        return "%s Cull" % (self.subject)

    def save(self, *args, **kwargs):
        subject_change = False
        if self.subject.death_date != self.date:
            self.subject.death_date = self.date
            subject_change = True
        if self.subject.cull_method != str(self.cull_method):
            self.subject.cull_method = str(self.cull_method)
            subject_change = True
        if subject_change:
            self.subject.save()
            # End all open water restrictions.
            for wr in WaterRestriction.objects.filter(
                    subject=self.subject, start_time__isnull=False, end_time__isnull=True):
                wr.end_time = self.date
                logger.debug("Ending water restriction %s.", wr)
                wr.save()
        return super(Cull, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # on deletion of the Cull object, setting the death_date of the related subject to None
        sub = self.subject
        output = super(Cull, self).delete(*args, **kwargs)
        sub.cull = None
        sub.death_date = None
        sub.cull_method = ''
        sub.save()
        return output
