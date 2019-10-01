from django.forms.models import model_to_dict

from subjects.models import Subject, Project
from actions.models import Cull

def compare_querysets(qs0, qs1, exclude_fields=None, include_fields=None, verbose=True):
    pk0 = list(qs0.values_list('pk', flat=True))
    pk1 = list(qs1.values_list('pk', flat=True))
    pks = list(set(pk0 + pk1))
    for pk in pks:
        if pk not in pk1:
            if verbose:
                print(f'{pk} does not exist on right')
            continue
        if pk not in pk0:
            if verbose:
                print(f'{pk} does not exist on left')
            continue
        o1 = qs1.get(pk=pk)
        o0 = qs0.get(pk=pk)
        d0 = model_to_dict(o0)
        d1 = model_to_dict(o1)
        for ff in d0:
            if exclude_fields and ff in exclude_fields:
                continue
            if include_fields and ff not in include_fields:
                continue
            if not d0[ff] == d1[ff]:
                print(o0, d0[ff], d1[ff])


def compare_model(model, db0='cortexlab', db1='default', typ='intersect', **kwargs):
    # type intersect, left or right
    pk0 = model.objects.using(db0).values_list('id', flat=True)
    pk1 = model.objects.using(db1).values_list('id', flat=True)
    if typ == 'left':
        pk_ref = list(pk0)
    elif typ == 'right':
        pk_ref = list(pk1)
    elif typ == 'intersect':
        pk_ref = list(set(pk0).intersection(set(pk1)))
    qs0 = model.objects.using(db0).filter(pk__in=pk_ref)
    qs1 = model.objects.using(db1).filter(pk__in=pk_ref)
    compare_querysets(qs0, qs1, **kwargs)


# compare Projects and Subjects
compare_model(Project, typ='intersect')
compare_model(Subject, db0='cortexlab', db1='default', include_fields=['projects'], typ='left',
              verbose=False)

# compare ull objects Subjects
subs = Subject.objects.values_list('pk', flat=True)
qs0 = Cull.objects.using('cortexlab').filter(subject__pk__in=list(subs))
subs = Subject.objects.using('cortexlab').values_list('pk', flat=True)
qs1 = Cull.objects.filter(subject__pk__in=list(subs))
compare_querysets(qs0, qs1)
