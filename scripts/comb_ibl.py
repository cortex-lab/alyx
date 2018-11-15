from actions.models import Session

# No null type sessions
ses = Session.objects.filter(type__isnull=True)
assert(ses.count() == 0)

# No Base sessions
ses = Session.objects.filter(type='Base')
assert(ses.count() == 0)

# No Session should have a parent session labeled in
ses = Session.objects.exclude(parent_session__isnull=True)
assert(ses.count() == 0)
