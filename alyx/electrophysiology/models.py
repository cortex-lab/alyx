from django.db import models
from data.models import TimeSeries, Dataset, BaseExperimentalData
from equipment.models import ExtracellularProbe, Amplifier, DAQ, PipettePuller
from misc.models import BrainLocation, CoordinateTransformation

#test

class ProbeInsertion(BaseModel):
    """
    Contains info about the geometry and probe model of a single probe insertion. 
    """

    entry_point_rl = models.FloatField(null=True, blank=True,
                                        help_text="mediolateral position of probe entry point "
                                        "relative to midline (microns). Positive means right")
    
    entry_point_ap = models.FloatField(null=True, blank=True,
                                        help_text="anteroposterior position of probe entry point "
                                        "relative to bregma (microns). Positive means anterior")

    vertical_angle = models.FloatField(null=True, blank=True,
                                        help_text="vertical angle of probe (degrees). Zero means "
                                        "horizontal. Positive means pointing down.")

    horizontal_angle = models.FloatField(null=True, blank=True,
                                        help_text="horizontal angle of probe (degrees), after vertical "
                                        "rotation. Zero means anterior. Positive means counterclockwise "
                                        "(i.e. left).")

    axial_angle = models.FloatField(null=True, blank=True,
                                        help_text="axial angle of probe (degrees). Zero means that without "
                                        " vertical and horizontal rotations, the probe contacts would be "
                                        " pointint up. Positive means counterclockwise.")

    distance_advanced = models.FloatField(null=True, blank=True,
                                        help_text="How far the probe was moved forward from its entry point. "
                                        "(microns).")

    probe_model = models.ForeignKey(ProbeModel, blank=True, null=True,
                                        help_text="model of probe used")

class ProbeModel(BaseModel):
    """
    Metadata describing each probe model
    """

    probe_manufacturer = models.ForeignKey(Supplier, blank=True, null=True) 

    probe_model = models.CharField(max_length=255, help_text="manufacturer's part number e.g. A4x8-5mm-100-200-177")
    
    description: models.CharField(max_length=255, null=True, blank=True, 
                                help_text= "optional informal description e.g. 'Michigan 4x4 tetrode'; "
                                "'Neuropixels phase 2 option 1'")

    site_positions: ForeignKey(Dataset, blank=True, null=True, 
                                help_text= "numerical array of size nSites x 2 giving locations of each contact site "
                                "in local coordinates. Probe tip is at the origin.")


class BaseBrainLocation(BaseModel)
    """
    Abstract base class for brain location. Never used directly.

    Contains curated anatomical location in Allen CCG with an acronym.
    This is usually figured out using histology, so should override what you might
    compute from ProbeInsertion. 
    """
    ccf_ap = models.FloatField(help_text="Allen CCF antero-posterior coordinate (microns)")
    ccf_dv = models.FloatField(help_text="Allen CCF dorso-ventral coordinate (microns)")
    ccf_lr = models.FloatField(help_text="Allen CCF left-right coordinate (microns)")

    allen_ontology = models.CharField(max_length=255, blank=True,
                                        help_text="Manually curated site location. Use "
                                        " Allen's acronyms to represent the appropriate "
                                        "hierarchical level, e.g. SS, SSp, or SSp6a")

class RecordingSite(BaseBrainLocation)
    """
    Contains estimated anatomical location of each recording site in each probe insertion.
    This is usually figured out using histology, so should override what you might
    compute from ProbeInsertion. Location a
    """

    probe_insertion = models.ForeignKey(ProbeInsertion, help_text="id of probe insertion")

    site_no = models.IntegerField(help_text="which site on the probe")
    

class ChannelMapping(BaseModel):
    """
    Junction table linking ExtracellularRecording and ProbeInsertion, telling you which channels of which probes 
    were on which channels of which recordings. There is one entry per channel
    """

    extracellular_recording = models.ForeignKey(ExtracellularRecording, help_text="id of extracellular recording")

    channel_no = models.IntegerField(help_text="channel number in raw recording file (counting from 0)")

    probe_insertion = models.ForeignKey(ProbeInsertion, null=True, help_text="which probe insertion was recorded on "
                                        "that channel. NULL if channel not used")

    site_no = models.IntegerField(null=True, help_text="probe site number for that channel "
                                        "(NULL if channel not used or dead)")

class ExtracellularRecording(TimeSeries):
    """
    Superclass of TimeSeries to describe raw data when you make an electrophys recording.
    There should a Dataset of DatasetType "ephys.raw" corresponding to this. 

    You can also link to a lfp timeseries, that contains low-pass data at a lower sample rate
    with the same channel mapping

    """

    @property
    def classname(self):
        return 'extracellular-recording'

    RECORDING_TYPES = (
        ('C', 'Chronic'),
        ('A', 'Acute'),
    )

    lfp = models.ForeignKey(TimeSeries, blank=True, null=True,
                                     related_name="extracellular_recording_lfp",
                                     help_text="lfp: low-pass filtered and downsampled")

    impedances = models.ForeignKey(Dataset, blank=True, null=True,
                                   related_name="extracellular_impedances",
                                   help_text="dataset containing measured impedance of "
                                   "each channel (ohms).")

    gains = models.ForeignKey(Dataset, blank=True, null=True,
                                   related_name="extracellular_gains",
                                   help_text="dataset containing gain of each channel "
                                   " samples/microvolt")

    filter_info = models.CharField(max_length=255, blank=True,
                                   help_text="Details of hardware corner frequencies, filter "
                                   "type, order.")
   
    recording_type = models.CharField(max_length=1, choices=RECORDING_TYPES,
                                      help_text="Whether the recording is chronic or acute",
                                      blank=True)

    ground_electrode = models.CharField(max_length=255, blank=True,
                                        help_text="e.g. 'screw above cerebellum'")

    reference_electrode = models.CharField(max_length=255, blank=True,
                                           help_text="e.g. 'shorted to ground'")

    amplifier = models.ForeignKey(Amplifier, blank=True, null=True,
                                  help_text="The amplifier used in this recording.")

    daq_description = models.ForeignKey(DAQ, blank=True, null=True,
                                        help_text="The DAQ used.")

class SpikeSorting(EventSeries):
    """
    An entry in the `spike_sorting` table contains the output of a single spike sorting run
    of an extracellular recording. There will usually be only one of these per recording,
    but there could be several if you want to store multiple alternative clusterings.

    The event series should have an associated info Dataset of DatasetType spikes.clusters

    Note that the database only describes the final spike sorting results, not
    intermediate steps such as feature vectors, to allow flexibility if algorithms change later.
    However, like models derived from BaseExperimentalData, it does contain a provenance_directory 
    that can contain these intermediate steps, in a non-standardized format.

    """

    extracellular_recording = models.ForeignKey(ExtracellularRecording)
    
    spikes = models.ForeignKey(EventSeries, help_text="EventSeries giving spike times "
                                    "plus clusters and any other info per spike")

    cluster_data = models.ForeignKey(DataCollection, blank=True, null=True, 
                                    help_text="DataCollection of files giving info on clusters: "
                                    "mean waveforms, qualities, etc.")


class SpikeSortedUnit(BaseBrainLocation):
    """
    This is going to be the biggest table, containing anatomical and other information
    on every unit resulting from spike sorting. (There is a separate table for 
    units resulting from 2-photon).
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

    cluster_number = models.IntegerField()

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
    
    refractory_violation_rate = models.FloatField(null=True, blank=True,
                                                  help_text="fraction of spikes "
                                                  "occurring < 2ms. ")
    
    isolation_distance = models.FloatField(null=True, blank=True,
                                           help_text="A measure of isolation quality")
    
    l_ratio = models.FloatField(null=True, blank=True,
                                help_text="A measure of isolation quality")
    
    mean_firing_rate = models.FloatField(null=True, blank=True,
                                         help_text="spikes/s")
    
    # human decisions:
    cluster_group = models.CharField(max_length=1, choices=CLUSTER_GROUPS,
                                     help_text="Human decision on cluster group")
    spike_width_class = models.CharField(max_length=1, choices=WIDTH_CLASSES,
                                         help_text="Human decision on spike width")
    optogenetic_response = models.CharField(max_length=255, blank=True,
                                            help_text="e.g. 'Short latency' (only if applicable)")
    putative_cell_type = models.CharField(max_length=255, blank=True,
                                          help_text="e.g. 'Sst interneuron', 'PT cell'. ")

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
