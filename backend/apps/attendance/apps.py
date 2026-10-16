import os
import threading

from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.attendance'

    def ready(self):
        # Model loading is expensive. Warm the matching model in the background
        # without delaying Django startup or breaking installations without ML.
        if os.environ.get("FACE_MODEL_WARMUP", "true").lower() in {"1", "true", "yes"}:
            from .face import warmup
            threading.Thread(target=warmup, name="face-model-warmup", daemon=True).start()
