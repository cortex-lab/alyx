from rest_framework import serializers
from alyx.base import BaseSerializerEnumField
from actions.models import Session
from experiments.models import (ProbeInsertion, TrajectoryEstimate, ProbeModel, CoordinateSystem,
                                Channel, BrainRegion, ChronicInsertion, FOV, FOVLocation,
                                ImagingType, ImagingStack)
from data.models import DatasetType, Dataset, DataRepository, FileRecord
from subjects.models import Subject
from misc.models import Lab


class SessionListSerializer(serializers.ModelSerializer):

    @staticmethod
    def setup_eager_loading(queryset):
        """ Perform necessary eager loading of data to avoid horrible performance."""
        queryset = queryset.select_related('subject', 'lab')
        return queryset.order_by('-start_time')

    subject = serializers.SlugRelatedField(read_only=True, slug_field='nickname')
    lab = serializers.SlugRelatedField(read_only=True, slug_field='name')

    class Meta:
        model = Session
        fields = ('subject', 'start_time', 'number', 'lab', 'id', 'task_protocol')


class TrajectoryEstimateSerializer(serializers.ModelSerializer):
    probe_insertion = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='id', many=False,
        queryset=ProbeInsertion.objects.all(),
    )
    x = serializers.FloatField(required=True, allow_null=True)
    y = serializers.FloatField(required=True, allow_null=True)
    z = serializers.FloatField(required=False, allow_null=True)
    depth = serializers.FloatField(required=True, allow_null=True)
    theta = serializers.FloatField(required=True, allow_null=True)
    phi = serializers.FloatField(required=True, allow_null=True)
    roll = serializers.FloatField(required=False, allow_null=True)
    provenance = BaseSerializerEnumField(required=True)
    session = SessionListSerializer(read_only=True)
    probe_name = serializers.CharField(read_only=True)
    coordinate_system = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='name', many=False,
        queryset=CoordinateSystem.objects.all(),
    )

    class Meta:
        model = TrajectoryEstimate
        fields = '__all__'


class ChannelSerializer(serializers.ModelSerializer):
    trajectory_estimate = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='id', many=False,
        queryset=TrajectoryEstimate.objects.all(),
    )
    brain_region = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='id', many=False,
        queryset=BrainRegion.objects.all(),
    )

    class Meta:
        model = Channel
        fields = '__all__'


class FilterDatasetSerializer(serializers.ListSerializer):

    def to_representation(self, dsets):
        if len(DataRepository.objects.filter(globus_is_personal=False)) > 0:
            frs = FileRecord.objects.filter(pk__in=dsets.values_list("file_records", flat=True))
            pkd = frs.filter(exists=True, data_repository__globus_is_personal=False
                             ).values_list("dataset", flat=True)
            dsets = dsets.filter(pk__in=pkd)
        return super(FilterDatasetSerializer, self).to_representation(dsets)


class ProbeInsertionDatasetsSerializer(serializers.ModelSerializer):

    dataset_type = serializers.SlugRelatedField(
        read_only=False, slug_field='name',
        queryset=DatasetType.objects.all(),
    )

    class Meta:
        list_serializer_class = FilterDatasetSerializer
        model = Dataset
        fields = ('id', 'name', 'dataset_type', 'data_url', 'url', 'file_size',
                  'hash', 'version', 'collection')


class ChronicProbeInsertionListSerializer(serializers.ModelSerializer):

    @staticmethod
    def setup_eager_loading(queryset):
        """ Perform necessary eager loading of data to avoid horrible performance."""
        queryset = queryset.select_related('session__subject__nickname')
        return queryset

    model = serializers.SlugRelatedField(read_only=True, slug_field='name')
    session_info = SessionListSerializer(read_only=True, source='session')

    class Meta:
        model = ProbeInsertion
        fields = ('id', 'name', 'model', 'serial', 'session_info')


class ProbeInsertionListSerializer(serializers.ModelSerializer):

    @staticmethod
    def setup_eager_loading(queryset):
        """ Perform necessary eager loading of data to avoid horrible performance."""
        queryset = queryset.select_related('model', 'session')
        queryset = queryset.prefetch_related('session__subject', 'session__lab', 'datasets')
        return queryset.order_by('-session__start_time')

    session = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='id',
        queryset=Session.objects.all(),
    )
    model = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='probe_model',
        queryset=ProbeModel.objects.all(),
    )
    session_info = SessionListSerializer(read_only=True, source='session')

    def validate(self, data):
        chronic_insertion = data.get('chronic_insertion', None)
        serial = data.get('serial', None)
        if chronic_insertion:
            cr = ChronicInsertion.objects.get(id=chronic_insertion.id)
            if cr.serial != serial:
                raise serializers.ValidationError("serial number of chronic insertion "
                                                  "and probe insertion do not match")

        return data

    class Meta:
        model = ProbeInsertion
        fields = '__all__'


class ProbeInsertionDetailSerializer(serializers.ModelSerializer):
    session = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='id',
        queryset=Session.objects.all(),
    )
    model = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='probe_model',
        queryset=ProbeModel.objects.all(),
    )
    session_info = SessionListSerializer(read_only=True, source='session')

    datasets = serializers.SerializerMethodField()

    def get_datasets(self, obj):
        qs = obj.session.data_dataset_session_related.all().filter(collection__icontains=obj.name)

        request = self.context.get('request', None)
        dsets = ProbeInsertionDatasetsSerializer(qs, many=True, context={'request': request})
        return dsets.data

    class Meta:
        model = ProbeInsertion
        fields = '__all__'


class ChronicInsertionListSerializer(serializers.ModelSerializer):

    @staticmethod
    def setup_eager_loading(queryset):
        """ Perform necessary eager loading of data to avoid horrible performance."""
        queryset = queryset.select_related('model', 'subject', 'lab')
        queryset = queryset.prefetch_related('probe_insertion')
        return queryset

    subject = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='nickname',
        queryset=Subject.objects.all(),
    )
    model = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='probe_model',
        queryset=ProbeModel.objects.all(),
    )

    lab = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='name',
        queryset=Lab.objects.all(),
    )

    probe_insertion = serializers.SerializerMethodField()

    def get_probe_insertion(self, obj):
        qs = obj.probe_insertion.all()
        request = self.context.get('request', None)
        dsets = ChronicProbeInsertionListSerializer(qs, many=True, context={'request': request})
        return dsets.data

    class Meta:
        model = ChronicInsertion
        fields = ('id', 'name', 'subject', 'lab', 'model', 'start_time',
                  'serial', 'json', 'probe_insertion')


class ChronicInsertionDetailSerializer(serializers.ModelSerializer):

    subject = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='nickname',
        queryset=Subject.objects.all(),
    )
    model = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='probe_model',
        queryset=ProbeModel.objects.all(),
    )

    lab = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='name',
        queryset=Lab.objects.all(),
    )

    probe_insertion = serializers.SerializerMethodField()

    def get_probe_insertion(self, obj):
        qs = obj.probe_insertion.all()
        request = self.context.get('request', None)
        dsets = ChronicProbeInsertionListSerializer(qs, many=True, context={'request': request})
        return dsets.data

    class Meta:
        model = ChronicInsertion
        fields = ('id', 'name', 'subject', 'lab', 'model', 'start_time',
                  'serial', 'json', 'probe_insertion')


class BrainRegionSerializer(serializers.ModelSerializer):
    # we do not want anybody to update the ontology from rest ! Only the description
    id = serializers.IntegerField(read_only=True)
    acronym = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    parent = serializers.SlugRelatedField(read_only=True, slug_field='id')

    class Meta:
        model = BrainRegion
        fields = ('id', 'acronym', 'name', 'description', 'parent', 'related_descriptions')


class FOVLocationDetailSerializer(serializers.ModelSerializer):
    brain_region = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='id', many=True,
        queryset=BrainRegion.objects.all(),
    )
    coordinate_system = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='name', many=False, default='IBL-Allen',
        queryset=CoordinateSystem.objects.all(),
    )
    provenance = serializers.ChoiceField(choices=FOVLocation.Provenance.values)
    x = serializers.ListField()
    y = serializers.ListField()
    z = serializers.ListField()
    n_xyz = serializers.ListField()

    @staticmethod
    def setup_eager_loading(queryset):
        """Perform necessary eager loading of data to avoid horrible performance."""
        queryset = queryset.select_related('coordinate_system')
        queryset = queryset.prefetch_related('brain_region')
        return queryset

    class Meta:
        model = FOVLocation
        exclude = ('name',)


class FOVLocationListSerializer(FOVLocationDetailSerializer):

    class Meta:
        model = FOVLocation
        exclude = ('name', 'json', 'field_of_view')


class FOVSerializer(serializers.ModelSerializer):
    imaging_type = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='name', queryset=ImagingType.objects.all())
    location = FOVLocationListSerializer(read_only=True, many=True)

    @staticmethod
    def setup_eager_loading(queryset):
        """Perform necessary eager loading of data to avoid horrible performance."""
        queryset = queryset.select_related('model', 'session')
        queryset = queryset.prefetch_related(
            'session__subject', 'session__lab', 'location', 'datasets')
        return queryset.order_by('-session__start_time')

    class Meta:
        model = FOV
        exclude = ('json',)


class ImagingStackDetailSerializer(serializers.ModelSerializer):
    slices = FOVSerializer(read_only=True, many=True)
    name = serializers.CharField()

    @staticmethod
    def setup_eager_loading(queryset):
        """Perform necessary eager loading of data to avoid horrible performance."""
        queryset = queryset.prefetch_related('slices')
        return queryset.order_by('slices__z__0')

    class Meta:
        model = ImagingStack
        fields = '__all__'


class ImagingStackListSerializer(ImagingStackDetailSerializer):
    name = None  # Only show name on read, but allow filtering by name

    class Meta:
        model = ImagingStack
        exclude = ('json', 'name')
