from misc.models import Lab
from experiments.models import ProbeInsertion
Lab.objects.filter(name='cortexlab').update(json=Lab.objects.using('cortexlab').get(name='cortexlab').json)

for pi in ProbeInsertion.objects.filter(session__lab__name='cortexlab'):
    pi.save()
