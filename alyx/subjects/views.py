import uuid
from dal import autocomplete

from .models import *

from .serializers import *
from rest_framework import generics, permissions, renderers, viewsets


def _autoname_number(model, field, prefix):
    objects = model.objects.filter(**{'%s__istartswith' % field: prefix})
    names = sorted([getattr(obj, field) for obj in objects])
    if not names:
        i = 1
    else:
        i = int(names[-1][-4:]) + 1
    return i


class SubjectList(generics.ListCreateAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectListSerializer
    permission_classes = (permissions.IsAuthenticated,)


class SubjectDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectDetailSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'nickname'


class SubjectAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated():
            return Subject.objects.none()

        qs = Subject.objects.all()

        line = self.forwarded.get('line', None)
        sex = self.forwarded.get('sex', None)
        if line:
            qs = qs.filter(line=line)
        if sex:
            qs = qs.filter(sex=sex)
        if self.q:
            qs = qs.filter(nickname__istartswith=self.q)

        return qs

    def get_result_value(self, result):
        # Bug fix:
        # https://github.com/yourlabs/django-autocomplete-light/pull/799
        out = super(SubjectAutocomplete, self).get_result_value(result)
        # Serialize the UUID field.
        if isinstance(out, uuid.UUID):
            out = str(out)
        return out


class AutoLinenameAutocomplete(autocomplete.Select2ListView):
    _model = None
    _field = ''
    _prefix = ''

    def get_list(self):
        if not self.request.user.is_authenticated():
            return

        if self.q:
            return [self.q]

        line = self.forwarded.get('line', None)
        if not line:
            return []
        line_name = Line.objects.get(pk=line).name
        prefix = self._prefix % line_name
        i = _autoname_number(self._model, self._field, prefix)
        return ['%s%04d' % (prefix, i)]


class CageLabelAutocomplete(AutoLinenameAutocomplete):
    _model = Cage
    _field = 'cage_label'
    _prefix = '%s_C_'


class SubjectNicknameAutocomplete(AutoLinenameAutocomplete):
    _model = Subject
    _field = 'nickname'
    _prefix = '%s_'
