from django.core.exceptions import ObjectDoesNotExist
from django.utils.encoding import smart_str
from rest_framework import serializers
from rest_framework.exceptions import APIException

from misc.models import Lab
from .models import Subject


class SubjectConflict(APIException):
    """Raised when a nickname matches multiple subjects and no lab disambiguates them."""
    status_code = 409
    default_detail = 'Multiple subjects match this nickname.'
    default_code = 'conflict'


class SubjectField(serializers.SlugRelatedField):
    """Subject nickname field that resolves duplicate nicknames using the lab.

    The lab is taken from the 'lab' field of the submitted data, or else from the lab of the
    instance being updated.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault('slug_field', 'nickname')
        if not kwargs.get('read_only'):
            kwargs.setdefault('queryset', Subject.objects.all())
        super().__init__(**kwargs)

    def _get_labs(self):
        parent = self.parent
        if isinstance(parent, serializers.ManyRelatedField):
            parent = parent.parent
        data = getattr(parent, 'initial_data', None)
        if hasattr(data, 'getlist'):  # QueryDict
            labs = data.getlist('lab')
        else:
            labs = data.get('lab') if isinstance(data, dict) else None
        if not labs:
            lab = getattr(getattr(parent, 'instance', None), 'lab', None)
            labs = lab.name if isinstance(lab, Lab) else None
        return labs

    def to_internal_value(self, data):
        try:
            return self.get_queryset().get_by_nickname(data, labs=self._get_labs())
        except Subject.MultipleObjectsReturned as ex:
            raise serializers.ValidationError(str(ex))
        except ObjectDoesNotExist:
            self.fail('does_not_exist', slug_name=self.slug_field, value=smart_str(data))
        except (TypeError, ValueError):
            self.fail('invalid')
