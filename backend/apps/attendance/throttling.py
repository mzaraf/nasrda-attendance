"""Rate-limit helpers for authentication endpoints."""

from hashlib import sha256

from rest_framework.throttling import ScopedRateThrottle


class IppisLoginRateThrottle(ScopedRateThrottle):
    """Apply the sign-in rate limit separately to each submitted IPPIS number.

    DRF's ``ScopedRateThrottle`` normally groups anonymous requests by client
    IP address.  Staff commonly share an office network, so that would let one
    person's repeated mistakes throttle colleagues' sign-ins.  Hashing keeps
    the cache key compact without placing the staff identifier in it verbatim.
    """

    def get_cache_key(self, request, view):
        ippis_number = str(request.data.get("ippis_number", "")).strip()
        if not ippis_number:
            # Invalid requests still need a bounded key, but must not consume a
            # real staff member's allowance.
            ippis_number = "missing"
        identifier = sha256(ippis_number.encode("utf-8")).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": identifier}
