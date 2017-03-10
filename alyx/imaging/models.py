from django.db import models
from data.models import Dataset, BaseExperimentalData
from equipment.models import LightSource
from misc.models import CoordinateTransformation


class WidefieldImaging(BaseExperimentalData):
    # we need to talk this through with nick - not sure if he is using
    # multipel files or just one for multispectral
    raw_data = models.ForeignKey(Dataset, blank=True, null=True, related_name="widefield_raw",
                                 help_text="pointer to nT by nX by nY by nC (colors) binary file")
    compressed_data = models.ForeignKey('SVDCompressedMovie', null=True, blank=True,
                                        related_name="widefield_compressed",
                                        help_text="Link to SVD compressed movie, "
                                        "if compression was run")
    start_time = models.FloatField(null=True, blank=True,
                                   help_text="in seconds relative to session start. "
                                   "TODO: not DateTimeField? / TimeDifference")
    # again, all relative to session start in seconds.
    end_time = models.FloatField(null=True, blank=True,
                                 help_text="Equals start time if single application. "
                                 "TODO: should this be an offset? Or DateTimeField? "
                                 "Or TimeDifference?")
    imaging_indicator = models.CharField(max_length=255, blank=True,
                                         help_text="<GCaMP6f, GCaMP6m, GCaMP6s, "
                                         "VSFPb1.2, intrinsic, …>. TODO: normalize!")
    preprocessing = models.CharField(max_length=255, blank=True,
                                     help_text="e.g. 'computed (F-F0) / F0, "
                                     "estimating F0 as running min'")
    description = models.CharField(max_length=255, blank=True,
                                   help_text="e.g. 'field of view includes V1, S1, "
                                   "retrosplenial'")
    image_position = models.ForeignKey(
        CoordinateTransformation, null=True, blank=True)
    excitation_nominal_wavelength = models.FloatField(null=True, blank=True,
                                                      help_text="in nm. "
                                                      "Can be array for multispectral")
    recording_nominal_wavelength = models.FloatField(null=True, blank=True,
                                                     help_text="in nm. "
                                                     "Can be array for multispectral")
    # excitation_device = models.CharField(max_length=255, null=True, blank=True,
    # help_text="e.g. LED part number. Can be array for multispectral. TODO:
    # Appliance subclass - what name?")
    excitation_device = models.ForeignKey(LightSource, blank=True, null=True)
    recording_device = models.CharField(max_length=255, blank=True,
                                        help_text="e.g. camera manufacturer, plus filter "
                                        "description etc. TODO: Appliance subclass - what name?")


class TwoPhotonImaging(BaseExperimentalData):
    raw_data = models.ForeignKey(Dataset, blank=True, null=True,
                                 related_name="two_photon_raw",
                                 help_text="array of size nT by nX by nY by nZ by nC")
    compressed_data = models.ForeignKey(Dataset, blank=True, null=True,
                                        related_name="two_photon_compressed",
                                        help_text="to Compressed_movie, if compression was run")
    start_time = models.FloatField(null=True, blank=True,
                                   help_text="in seconds relative to session start. "
                                   "TODO: not DateTimeField? / TimeDifference")
    end_time = models.FloatField(null=True, blank=True,
                                 help_text="Equals start time if single application. "
                                 "TODO: should this be an offset? Or DateTimeField? "
                                 "Or TimeDifference?")
    imaging_indicator = models.CharField(max_length=255, blank=True,
                                         help_text="<GCaMP6f, GCaMP6m, GCaMP6s …>. "
                                         "TODO: normalize!")
    description = models.CharField(max_length=255, blank=True,
                                   help_text="e.g. 'V1 layers 2-4'")
    image_position = models.ForeignKey(CoordinateTransformation, null=True, blank=True,
                                       help_text="Note if different planes have different "
                                       "alignment (e.g. flyback plane), this can’t be done "
                                       "in a single 3x3 transformation matrix, instead you "
                                       "would have an array of 3x2 matrices. "
                                       "TODO: how do we deal with this?")
    excitation_wavelength = models.FloatField(null=True, blank=True,
                                              help_text="in nm")
    recording_wavelength = models.FloatField(null=True, blank=True,
                                             help_text="in nm. Can be array for "
                                             "multispectral imaging. TODO: deal with arrays?")
    # does django have a way of encoding small arrays in regular tables? I
    # guess not if they are variable size... so it would need to be json
    reference_stack = models.ForeignKey(Dataset, blank=True, null=True,
                                        related_name="two_photon_reference",
                                        help_text="TODO: reference stack / BrainImage")


class ROIDetection(BaseExperimentalData):
    masks = models.ForeignKey(Dataset, blank=True, null=True,
                              related_name="roi_detection_masks",
                              help_text="array of size nROIs by nX by nY")
    plane = models.IntegerField(null=True, blank=True,
                                help_text="array saying which plane each roi is found in. "
                                "TODO: is this an ArrayField? JSON?")
    generating_software = models.CharField(max_length=255, null=True, blank=True,
                                           help_text="e.g. 'AutoROI 0.8.3'")
    provenance_directory = models.ForeignKey(Dataset, blank=True, null=True,
                                             related_name="roi_detection_provenance",
                                             help_text="link to directory containing "
                                             "intermediate results")
    preprocessing = models.CharField(max_length=255, blank=True,
                                     help_text="computed (F-F0) / F0, estimating "
                                     "F0 as running min'")
    f = models.ForeignKey(Dataset, blank=True, null=True, related_name="roi_detection_f",
                          help_text="array of size nT by nROIs giving raw fluorescence")
    f0 = models.ForeignKey(Dataset, blank=True, null=True, related_name="roi_detection_f0",
                           help_text="array of size nT by nROIs giving resting fluorescence")
    two_photon_imaging_id = models.ForeignKey('TwoPhotonImaging', null=True, blank=True,
                                              help_text="2P imaging stack.")
    # TODO: multiple sortings?
    # taken care of already : this is a many-to-one relationship


class ROI(BaseExperimentalData):
    roi_type = models.CharField(max_length=255, blank=True,
                                help_text="soma, dendrite, neuropil, …> TODO: normalize?")
    optogenetic_response = models.CharField(max_length=255, blank=True,
                                            help_text="e.g. 'Short latency' (only if applicable)")
    putative_cell_type = models.CharField(max_length=255, blank=True,
                                          help_text="e.g. 'Sst interneuron', 'PT cell'")
    estimated_layer = models.CharField(max_length=255, blank=True,
                                       help_text="e.g. 'Layer 5b'")
    roi_detection_id = models.ForeignKey('ROIDetection', blank=True, null=True,
                                         help_text="link to detection entry")


class SVDCompressedMovie(BaseExperimentalData):
    compressed_data_U = models.ForeignKey(Dataset, blank=True, null=True,
                                          related_name="svd_movie_u",
                                          help_text="binary array containing "
                                          "SVD-compression eigenframes")
    compressed_data_V = models.ForeignKey(Dataset, blank=True, null=True,
                                          related_name="svd_movie_v",
                                          help_text="binary array containing "
                                          "SVD-compression timecourses")
