"""API error responses shared across the attendance system."""
from math import ceil

from rest_framework.exceptions import Throttled
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Keep throttle responses useful without changing the configured limits."""
    response = exception_handler(exc, context)
    if response is not None and isinstance(exc, Throttled):
        seconds = max(0, ceil(exc.wait or 0))
        if seconds >= 60:
            minutes = ceil(seconds / 60)
            unit = "minute" if minutes == 1 else "minutes"
            response.data["detail"] = f"Request was throttled. Please try again in about {minutes} {unit}."
        else:
            unit = "second" if seconds == 1 else "seconds"
            response.data["detail"] = f"Request was throttled. Please try again in {seconds} {unit}."
    return response
