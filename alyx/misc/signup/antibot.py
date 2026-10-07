"""Bot protection for the public sign-up form.

The exposure here is less the junk accounts than the mail they cause: the form will send a
confirmation to any address given to it, and AWS suspends SES sending when bounces exceed
about 5% of volume. A bot supplying invented addresses reaches that quickly, and the
suspension would take every other Alyx notification with it. Accounts themselves are inert
until confirmed, so they cost little on their own.

Three layers, deliberately ordered by how much they cost a legitimate user:

  honeypot   free and invisible, catches indiscriminate form-fillers
  turnstile  a real challenge, off unless a deployment asks for it
  throttle   a backstop on volume from one address, not a per-person gate

Only the throttle looks at the client address, and that is the layer that cannot tell a
lecture theatre from a botnet - see PUBLIC_SIGNUP_THROTTLE for how that is handled.
"""
import logging
import time

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Rendered as a real field that is hidden from people. Named as something a form-filling bot
# would want to complete; anything that puts a value in it is not a browser driven by a human.
HONEYPOT_FIELD = 'homepage'


def _setting(name, default):
    return getattr(settings, name, default)


def honeypot_tripped(data):
    """Whether the hidden field came back filled in."""
    return bool((data.get(HONEYPOT_FIELD) or '').strip())


def client_ip(request):
    """Best-effort client address, honouring a proxy header when one is trusted.

    Only consulted for throttling, so a spoofed value cannot gain access to anything - at
    worst it lets one client evade a volume cap, which is why the header is used only when the
    deployment says it sits behind a proxy that sets it.
    """
    if _setting('PUBLIC_SIGNUP_TRUST_FORWARDED_FOR', False):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded:
            return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def throttle_exceeded(request):
    """Whether this address has exhausted its sign-up allowance.

    Returns False - never throttling - unless PUBLIC_SIGNUP_THROTTLE is configured, because
    the right ceiling depends entirely on how a deployment is used. Anywhere that runs courses
    or workshops sees a hundred people register from one NAT'd address within minutes, which
    is indistinguishable from a flood by address alone; a limit set for the ordinary case
    would lock out the room. The other two layers do not care where a request comes from, so
    this one is best left as a generous ceiling on damage rather than a gate on people.
    """
    limit = _setting('PUBLIC_SIGNUP_THROTTLE', None)
    if not limit:
        return False
    count, seconds = limit
    ip = client_ip(request)
    if ip in set(_setting('PUBLIC_SIGNUP_THROTTLE_EXEMPT', ()) or ()):
        return False

    key = f'signup-throttle:{ip}'
    now = time.time()
    # Timestamps rather than a counter, so the window slides instead of resetting on the hour
    # and a burst cannot straddle two windows to get double the allowance.
    recent = [t for t in (cache.get(key) or []) if now - t < seconds]
    if len(recent) >= count:
        logger.warning('Sign-up throttled for %s: %d in the last %ds', ip, len(recent), seconds)
        return True
    recent.append(now)
    cache.set(key, recent, seconds)
    return False


def turnstile_configured():
    return bool(_setting('TURNSTILE_SITE_KEY', '') and _setting('TURNSTILE_SECRET_KEY', ''))


def turnstile_passed(request, token):
    """Verify a Cloudflare Turnstile response with Cloudflare.

    Chosen over reCAPTCHA because it does not hand visitor data to Google, which is an
    awkward thing to be doing on the same page that asks for consent to be emailed. A failure
    to reach Cloudflare is treated as a pass: a challenge provider being down should not stop
    people registering, and the other layers still apply.
    """
    if not token:
        return False
    import requests
    try:
        response = requests.post(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data={'secret': _setting('TURNSTILE_SECRET_KEY', ''),
                  'response': token,
                  'remoteip': client_ip(request)},
            timeout=5)
        return bool(response.json().get('success'))
    except Exception as ex:  # network failure, malformed response
        logger.warning('Turnstile verification unavailable (%s); allowing the sign-up', ex)
        return True
