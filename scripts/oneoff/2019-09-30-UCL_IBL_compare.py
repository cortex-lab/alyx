from django.forms.models import model_to_dict

from subjects.models import Subject, Project
from actions.models import Session


def compare_querysets(qs0, qs1, exclude_fields=None):
    for o0 in qs0:
        try:
            o1 = qs1.get(pk=o0.pk)
        except:
            print(f"{o0} does not exist on slave")
            continue
        d0 = model_to_dict(o0)
        d1 = model_to_dict(o1)
        for ff in d0:
            if exclude_fields and ff in exclude_fields:
                continue
            if not d0[ff] == d1[ff]:
                print(o0, d0[ff], d1[ff])


def compare_model(model, db0='cortexlab', db1='default'):
    qs0 = model.objects.using(db0)
    qs1 = model.objects.using(db1)
    compare_querysets(qs0, qs1, exclude_fields=None)


# compare subjects after having filtered
ses = Session.objects.using('cortexlab').filter(project__name__icontains='ibl')
subs_ibl = ses.values_list('subject', flat=True).distinct()
subs_ucl = Subject.objects.using('cortexlab').filter(pk__in=subs_ibl)
subs_ibl = Subject.objects.using('default').filter(pk__in=list(subs_ibl))
compare_querysets(subs_ucl, subs_ibl, exclude_fields=['request'])

# compare Projects
compare_model(Project)
