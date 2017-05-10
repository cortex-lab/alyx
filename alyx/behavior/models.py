from django.db import models
from data.models import Dataset, TimeSeries, BaseExperimentalData
from equipment.models import Appliance
from misc.models import BrainLocation


class PupilTracking(BaseExperimentalData):
    """
    Describes the results of a pupil tracking algorithm.
    """
    EYES = (
        ('L', 'Left'),
        ('R', 'Right'),
    )

    x_y_d = models.ForeignKey(TimeSeries, blank=True, null=True, related_name="pupil_tracking_x_y_d",
                              help_text="n*3 timeseries giving x and y coordinates "
                              "of center plus diameter")
    movie = models.ForeignKey(TimeSeries, blank=True, null=True, related_name="pupil_tracking_movie",
                              help_text="Link to raw data")
    eye = models.CharField(max_length=1,
                           choices=EYES,
                           blank=True,  # I suggest we don't have a default for this
                           help_text="Which eye was tracked; left or right")
    description = models.TextField(blank=True,
                                   help_text="misc. narrative e.g. "
                                   "('unit: mm' or 'unknown scale factor')")
    generating_software = models.CharField(max_length=255, blank=True,
                                           help_text="e.g. 'PupilTracka 0.8.3'")
    provenance_directory = models.ForeignKey(Dataset, blank=True, null=True,
                                             related_name="pupil_tracking_provenance",
                                             help_text="link to directory containing "
                                             "intermediate results")

    class Meta:
        verbose_name_plural = 'Pupil tracking'


class HeadTracking(BaseExperimentalData):
    """
    Describes the results of a head tracking algorithm.
    """
    x_y_theta = models.ForeignKey(TimeSeries, blank=True, null=True,
                                  related_name="head_tracking_x_y_d",
                                  help_text="3*n timeseries giving x and y coordinates "
                                  "of head plus angle")
    movie = models.ForeignKey(TimeSeries, blank=True, null=True,
                              related_name="head_tracking_movie",
                              help_text="Link to raw data")
    description = models.TextField(blank=True,
                                   help_text="misc. narrative e.g. "
                                   "('unit: cm' or 'unknown scale factor')")
    generating_software = models.CharField(max_length=255, blank=True,
                                           help_text="e.g. 'HeadTracka 0.8.3'")
    provenance_directory = models.ForeignKey(Dataset, blank=True, null=True,
                                             related_name="head_tracking_provenance",
                                             help_text="link to directory containing "
                                             "intermediate results")

    class Meta:
        verbose_name_plural = 'Head tracking'


class EventSeries(BaseExperimentalData):
    """
    Links to a file containing a set of event times and descriptions,
    such as behavioral events or sensory stimuli.
    """
    event_times = models.ForeignKey(Dataset, blank=True, null=True,
                                    related_name="event_series_event_times",
                                    help_text="n*1 array of times in seconds (universal timescale)")
    type_descriptions_id = models.ForeignKey(Dataset, blank=True, null=True)
    event_types_id = models.ForeignKey(Dataset, blank=True, null=True,
                                       related_name="event_series_event_descriptions",
                                       help_text="n*1 array listing the type of each event")
    description = models.TextField(blank=True,
                                   help_text="misc. narrative e.g. "
                                   "'drifting gratings of different orientations', "
                                   "'ChoiceWorld behavior events'")
    generating_software = models.CharField(max_length=255, blank=True,
                                           help_text="e.g. 'ChoiceWorld 0.8.3'")
    provenance_directory = models.ForeignKey(Dataset, blank=True, null=True,
                                             related_name="event_series_provenance",
                                             help_text="link to directory containing "
                                             "intermediate results")

    class Meta:
        verbose_name_plural = 'Event series'


class IntervalSeries(BaseExperimentalData):
    """
    Links to a file containing a set of start/end pairs and descriptions,
    such as behavioral intervals or extended sensory stimuli.
    """
    interval_times = models.ForeignKey(Dataset, blank=True, null=True,
                                       related_name="interval_series_interval_times",
                                       help_text="n*2 array, with associated array "
                                       "of row labels.")
    interval_descriptions = models.ForeignKey(Dataset, blank=True, null=True,
                                              related_name="interval_series_"
                                              "interval_descriptions",
                                              help_text="n*1 array listing the type "
                                              "of each interval")
    description = models.TextField(blank=True,
                                   help_text="misc. narrative e.g. "
                                   "'drifting gratings of different orientations', "
                                   "'ChoiceWorld behavior intervals'")
    generating_software = models.CharField(max_length=255, blank=True,
                                           help_text="e.g. 'ChoiceWorld 0.8.3'")
    provenance_directory = models.ForeignKey(Dataset, blank=True, null=True,
                                             related_name="interval_series_provenance",
                                             help_text="link to directory containing "
                                             "intermediate results")

    class Meta:
        verbose_name_plural = 'Interval series'


class OptogeneticStimulus(BaseExperimentalData):
    """
    This is a special type of interval series, to deal with optogenetic stimuli.
    """
    apparatus = models.ForeignKey(Appliance, null=True, blank=True,
                                  help_text="e.g. Laser that was used for stimulation.")
    # TODO: should this be a ManyToManyField? Also what is this class? It should subclass
    # Appliance rather than call it directly")
    # This is a good example of how there will be new types of appliance all the time. I have
    # added a new one LightSource - but probably people will want to reference Appliance
    # directly sometimes
    light_delivery = models.CharField(max_length=255, blank=True,
                                      help_text="e.g. 'fiber pointed at craniotomy'")
    description = models.CharField(max_length=255, blank=True,
                                   help_text="e.g. 'square pulses', 'ramps'")
    wavelength = models.FloatField(null=True, blank=True, help_text="in nm")
    brain_location = models.ForeignKey(BrainLocation, null=True, blank=True,
                                       help_text="of fiber tip, craniotomy, etc.")
    stimulus_times = models.ForeignKey(Dataset, blank=True, null=True,
                                       related_name="optogenetic_stimulus_times",
                                       help_text="link to an n*2 array of start and stop "
                                       "of each pulse (sec)")
    stimulus_positions = models.ForeignKey(Dataset, blank=True, null=True,
                                           related_name="optogenetic_stimulus_positions",
                                           help_text="link to an n*3 array of stimulus positions")
    power = models.ForeignKey(Dataset, blank=True, null=True,
                              related_name="optogenetic_stimulus_power",
                              help_text="link to an n*1 array giving each pulse power")
    power_calculation_method = models.CharField(max_length=255, blank=True,
                                                help_text="TODO: normalize? measured, nominal")
    waveform = models.ForeignKey(Dataset, blank=True, null=True,
                                 related_name="optogenetic_stimulus_waveform",
                                 help_text="link to a file giving the waveform "
                                 "of each stimulus.?")

    class Meta:
        verbose_name_plural = 'Optogenetic stimulus'


class Pharmacology(BaseExperimentalData):
    # Let's not worry about this now! we aren't going to use it in our lab
    """
    Describes a drug application during the session.
    """
    drug = models.CharField(max_length=255, blank=True,
                            help_text="TODO: normalize? Also say what it is "
                            "dissolved in (DMSO etc)")
    administration_route = models.CharField(max_length=255, blank=True,
                                            help_text="TODO: normalize? IP, IV, IM, surface etc…")
    start_time = models.FloatField(null=True, blank=True,
                                   help_text="in seconds relative to session start. "
                                   "TODO: not DateTimeField? / TimeDifference")
    end_time = models.FloatField(null=True, blank=True,
                                 help_text="equals start time if single application. "
                                 "TODO: should this be an offset? Or DateTimeField? "
                                 "Or TimeDifference?")
    concentration = models.CharField(max_length=255, blank=True,
                                     help_text="TODO: not FloatField? include unit "
                                     "(e.g. g/kg; mM; %)")
    volume = models.CharField(max_length=255, blank=True,
                              help_text="TODO: not FloatField? include unit (e.g. µL)")

    class Meta:
        verbose_name_plural = 'Pharmacology'
