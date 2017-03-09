from django.db import models
from data.models import Dataset, BaseExperimentalData
from equipment.models import ExtracellularProbe, Amplifier, DAQ, PipettePuller
from misc.models import BrainLocation, CoordinateTransformation


class ExtracellularRecording(BaseExperimentalData):
    """
    There is one document in this collection each time you make an extracellular recording.
    There will typically be one spike_sorting entry associated with it
    (although there could be more). The data files directly associated with this document
    are raw_data and lfp (raw_data downsampled). Note that we assume channels are recorded
    in the same order every time a probe is used. (TODO: do we? Where?)

    TODO: sample rate? dead channels? Some linking of the same chronic implant location between
    multiple recordings/days?
    """

    @property
    def classname(self):
        return 'extracellular-recording'

    RECORDING_TYPES = (
        ('C', 'Chronic'),
        ('A', 'Acute'),
    )

    raw_data = models.ForeignKey(Dataset, blank=True, null=True,
                                 related_name="extracellular_recording_raw",
                                 help_text="Raw electrophysiology recording data in "
                                 "flat binary format")
    lowpass_data = models.ForeignKey(Dataset, blank=True, null=True,
                                     related_name="extracellular_recording_lpf",
                                     help_text="Extracellular low-passed data")
    highpass_data = models.ForeignKey(Dataset, blank=True, null=True,
                                      related_name="extracellular_recording_hpf",
                                      help_text="Extracellular high-passed data")
    filter_info = models.CharField(max_length=255, blank=True,
                                   help_text="Details of hardware corner frequencies, filter "
                                   "type, order. TODO: make this more structured?")
    start_time = models.FloatField(null=True, blank=True,
                                   help_text="in seconds relative to experiment start.")
    #                                  TODO: not DateTimeField? / TimeDifference")
    # the idea is that the experiment has a single DateTime when it started,
    # then all times are in seconds relative to this. TimeDifference could work also,
    # but why not just float?
    end_time = models.FloatField(null=True, blank=True,
                                 help_text="in seconds relative to experiment start")
    recording_type = models.CharField(max_length=1, choices=RECORDING_TYPES,
                                      help_text="Whether the recording is chronic or acute", blank=True)
    ground_electrode = models.CharField(max_length=255, blank=True,
                                        help_text="e.g. 'screw above cerebellum'")
    reference_electrode = models.CharField(max_length=255, blank=True,
                                           help_text="e.g. 'shorted to ground'")
    impedances = models.ForeignKey(Dataset, blank=True, null=True,
                                   related_name="extracellular_impedances",
                                   help_text="binary array for measured impedance of "
                                   "each channel (ohms).")
    amplifier = models.ForeignKey(Amplifier, blank=True, null=True,
                                  help_text="The amplifier used in this recording.")
    # TODO: multiple amplifiers?
    # they would have their own ExtracellularRecording objects in
    # that case.
    daq_description = models.ForeignKey(DAQ, blank=True, null=True,
                                        help_text="The DAQ used.")
    #  TODO: should this be a separate class?
    # in the long run maybe, but let's keep things simpler
    electrode_depth = models.FloatField(null=True, blank=True,
                                        help_text="estimated depth of electrode tip from "
                                        "brain surface. ")
    # TODO: recording tip? or actual tip?
    # actual tip: because you know how far you advanced that.
    probe_location = models.ForeignKey(CoordinateTransformation, null=True, blank=True,
                                       help_text="from probe tip")
    extracellular_probe = models.ForeignKey(ExtracellularProbe, null=True, blank=True,
                                            help_text="Which probe model was used.")
    # TODO: What if more than one used simultaneously?
    # ugh, this is a problem. not sure what to do if they use multiple probes,
    # recorded together.


class SpikeSorting(BaseExperimentalData):
    """
    An entry in the `spike_sorting` table contains metadata about a single spike sorting run
    of an extracellular recording. There will usually be only one of these per recording,
    but there could be several if you want to store multiple alternative clusterings.
    Note that the database only describes the final spike sorting results, not
    intermediate steps such as feature vectors, to allow flexibility if algorithms change later.
    However, it does contain a provenance_directory that can contain these intermediate steps,
    in a non-standardized format.

    Finally, while multiple extracellular_recordings can be sorted together,
    they must all belong to the same experiment (i.e. the same action).
    This is required as time zero is defined separately for each experiment.
    When multiple experiments are clustered together (e.g. in a chronic recording
    over several days), you will need to create multiple spike_sorting documents,
    and link them together (to be determined exactly how).

    """
    spike_times = models.ForeignKey(Dataset, blank=True, null=True,
                                    related_name="spike_sorting_spike_times",
                                    help_text="time of each spike relative to experiment "
                                    "start in seconds.")
    # TODO: experiment or recording start?
    # Experiment start. Everything should be relative to that.
    cluster_assignments = models.ForeignKey(Dataset, blank=True, null=True,
                                            related_name="spike_sorting_cluster_assignments",
                                            help_text="cluster assignment of each spike")
    mean_unfiltered_waveform = models.ForeignKey(Dataset, blank=True, null=True,
                                                 related_name="spike_sorting_"
                                                 "unfiltered_waveforms",
                                                 help_text="mean unfiltered waveforms of "
                                                 "every spike on every channel")
    mean_filtered_waveform = models.ForeignKey(Dataset, blank=True, null=True,
                                               related_name="spike_sorting_filtered_waveforms",
                                               help_text="mean filtered waveforms of every spike "
                                               "on every channel")
    generating_software = models.CharField(max_length=255, blank=True,
                                           help_text="e.g. 'phy 0.8.3'")
    provenance_directory = models.ForeignKey(Dataset, blank=True, null=True,
                                             related_name="spike_sorting_provenance",
                                             help_text="link to directory containing "
                                             "intermediate results")


class SpikeSortedUnit(BaseExperimentalData):
    """
    This is going to be the biggest table, containing information on every unit resulting
    from spike sorting. (There is a separate table for units resulting from 2-photon).
    """
    CLUSTER_GROUPS = (
        ('0', 'Noise'),
        ('1', 'Multi-unit activity'),
        ('2', 'Single-unit activity')
    )

    WIDTH_CLASSES = (
        ('N', 'Narrow'),
        ('W', 'Wide'),
    )

    cluster_number = models.IntegerField(null=True, blank=True)
    spike_sorting = models.ForeignKey('SpikeSorting', blank=True, null=True,
                                      help_text="The spike sorting this unit came from")

    # automatically computed information:
    channel_group = models.IntegerField(null=True, blank=True,
                                        help_text="which shank this unit came from "
                                        "(an integer not a link)")
    trough_to_peak_width = models.FloatField(null=True, blank=True,
                                             help_text="ms, computed from unfiltered "
                                             "mean spike waveform.")
    half_width = models.FloatField(null=True, blank=True,
                                   help_text="ms, half width of negative peak in "
                                   "unfiltered spike waveform.")
    trough_to_peak_amplitude = models.FloatField(null=True, blank=True,
                                                 help_text="µV, from filtered spike waveform.")
    # when you say which waveform, do you mean which channel? I guess the
    # peak, but we can leave it unspecified...
    refractory_violation_rate = models.FloatField(null=True, blank=True,
                                                  help_text="fraction of spikes "
                                                  "occurring < 2ms. ")
    # TODO: is 2ms going to be hard-coded?
    # i guess... what's the alternative?
    isolation_distance = models.FloatField(null=True, blank=True,
                                           help_text="A measure of isolation quality")
    # Not better to go in JSON? difficult call. I think we should leave it
    # here, because we want quality measures to be prominent
    l_ratio = models.FloatField(null=True, blank=True,
                                help_text="A measure of isolation quality")
    mean_firing_rate = models.FloatField(null=True, blank=True,
                                         help_text="spikes/s")
    location_center_of_mass = models.FloatField(null=True, blank=True,
                                                help_text="3x1 in estimated stereotaxic "
                                                "coordinates.")
    # does this FloatField store 3 numbers of just one?

    # human decisions:
    cluster_group = models.CharField(max_length=1, choices=CLUSTER_GROUPS,
                                     help_text="Human decision on cluster group")
    spike_width_class = models.CharField(max_length=1, choices=WIDTH_CLASSES,
                                         help_text="Human decision on spike width")
    optogenetic_response = models.CharField(max_length=255, blank=True,
                                            help_text="e.g. 'Short latency' (only if applicable)")
    putative_cell_type = models.CharField(max_length=255, blank=True,
                                          help_text="e.g. 'Sst interneuron', 'PT cell'. ")
    # TODO: more structured? match with Allen Cell Type nomenclature?
    # i think that would be premature
    estimated_layer = models.CharField(max_length=255, blank=True,
                                       help_text="e.g. 'Layer 5b'. ")
    # TODO: more structured?
    # again, probably premature


class IntracellularRecording(BaseExperimentalData):
    """
    This describes a single intracellular electrode used in one recording.
    """
    ELECTRODE_TYPES = (
        ('W', 'Whole-cell'),
        ('S', 'Sharp'),
    )

    tip_location = models.ForeignKey(BrainLocation, null=True, blank=True,
                                     help_text="Estimated location of probe tip")
    electrode_type = models.CharField(max_length=1, choices=ELECTRODE_TYPES)
    pipette_puller = models.ForeignKey(PipettePuller, null=True, blank=True)
    inner_diameter = models.FloatField(null=True, blank=True,
                                       help_text="mm – before pulling")
    outer_diameter = models.FloatField(null=True, blank=True,
                                       help_text=" mm – before pulling")
    electrode_solution = models.TextField(blank=True,
                                          help_text="Solution details.")
    # TODO: standardize
    # that's what the Solutions object would be. but let's not prioritize this
    # now.

    # for voltage clamp
    cp_fast = models.FloatField(null=True, blank=True,
                                help_text="(pF)")
    cp_slow = models.FloatField(null=True, blank=True,
                                help_text="(pF)")
    whole_cell_cap_comp = models.FloatField(null=True, blank=True,
                                            help_text="(pF)")
    whole_cell_series_resistance = models.FloatField(null=True, blank=True,
                                                     help_text="(Mohm)")
    series_resistance_compensation_bandwidth = models.FloatField(null=True, blank=True,
                                                                 help_text="(kHz)")
    series_resistance_compensation_correction = models.FloatField(null=True, blank=True,
                                                                  help_text="(%)")
    series_resistance_compensation_prediction = models.FloatField(null=True, blank=True,
                                                                  help_text="(%)")
    recorded_current = models.ForeignKey(Dataset, blank=True, null=True,
                                         related_name="intracellular_recording_recorded_current",
                                         help_text="nA. TODO: time series? flat file? "
                                         "sample rate?")
    # it is a timeseries. But the plan was that would be taken care of by the file.timestamps etc.
    # however we could have a timeseries class, that subclasses Dataset.
    voltage_command = models.ForeignKey(Dataset, blank=True, null=True,
                                        related_name="intracellular_recording_voltage_command",
                                        help_text="mV")
    gain = models.FloatField(null=True, blank=True,
                             help_text="(A/V) – for info only; not required to convert "
                             "raw data to amps")

    # for current clamp
    pipette_cap_comp = models.FloatField(null=True, blank=True,
                                         help_text="(pF)")
    bridge_balance = models.FloatField(null=True, blank=True,
                                       help_text="(M Ohm)")
    recorded_voltage = models.ForeignKey(Dataset, blank=True, null=True,
                                         related_name="intracellular_recording_recorded_voltage",
                                         help_text="mV")
    current_command = models.ForeignKey(Dataset, blank=True, null=True,
                                        related_name="intracellular_recording_current_command",
                                        help_text="nA")
    gain = models.FloatField(null=True, blank=True,
                             help_text="(V/V) – for info only; not required to convert "
                             "raw data to volts")
