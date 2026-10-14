"""Self-hosted facial-template and passive-liveness integration.

DeepFace/MiniFASNet are deliberately loaded only when used. This keeps ordinary
Django commands operational if the optional ML runtime is not installed, while
attendance correctly fails closed rather than silently accepting an unverified face.
"""
import base64
import hashlib
import io
import json
import math
import os
from typing import Iterable

from django.conf import settings

from apps.core.errors import DomainError


MAX_IMAGE_BYTES = 3 * 1024 * 1024


def _fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        raise DomainError("FACE_SERVICE_UNAVAILABLE", "Facial verification is temporarily unavailable. Please contact the administrator.", 503)
    key = os.environ.get("FACE_TEMPLATE_KEY")
    if key:
        return Fernet(key.encode())
    # Deployment should provide FACE_TEMPLATE_KEY. This deterministic fallback still
    # keeps database-only exposure from revealing templates, using Django's secret.
    derived = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(derived)


def encrypt_template(embedding: list[float]) -> str:
    return _fernet().encrypt(json.dumps(embedding, separators=(",", ":")).encode()).decode()


def decrypt_template(value: str) -> list[float]:
    try:
        return json.loads(_fernet().decrypt(value.encode()).decode())
    except Exception as error:
        if isinstance(error, DomainError):
            raise
        raise DomainError("FACE_TEMPLATE_INVALID", "Your facial-verification profile must be enrolled again.", 409)


def _image(value: str):
    if not isinstance(value, str):
        raise DomainError("INVALID_FACE_CAPTURE", "A camera image is required.")
    encoded = value.split(",", 1)[-1]
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception:
        raise DomainError("INVALID_FACE_CAPTURE", "The camera image could not be read.")
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise DomainError("INVALID_FACE_CAPTURE", "Use a clear camera image smaller than 3 MB.")
    try:
        from PIL import Image
        import numpy as np
        image = Image.open(io.BytesIO(raw)).convert("RGB")
        return np.asarray(image)
    except Exception:
        raise DomainError("INVALID_FACE_CAPTURE", "The camera image is invalid.")


def _deepface():
    try:
        from deepface import DeepFace
        return DeepFace
    except ImportError:
        raise DomainError("FACE_SERVICE_UNAVAILABLE", "Facial verification is temporarily unavailable. Please contact the administrator.", 503)


def _embedding(image) -> list[float]:
    DeepFace = _deepface()
    try:
        faces = DeepFace.extract_faces(image, detector_backend="retinaface", enforce_detection=True, anti_spoofing=True)
        if len(faces) != 1:
            raise DomainError("FACE_CAPTURE_INVALID", "Show exactly one face clearly to the camera.")
        if not faces[0].get("is_real", False):
            raise DomainError("LIVENESS_FAILED", "We could not confirm a live face. Please try again without a photo or screen.", 403)
        result = DeepFace.represent(faces[0]["face"], model_name="ArcFace", detector_backend="skip", enforce_detection=False)
        return [float(value) for value in result[0]["embedding"]]
    except DomainError:
        raise
    except Exception:
        raise DomainError("FACE_CAPTURE_INVALID", "We could not verify your face. Use good lighting and keep your face fully visible.", 422)


def _distance(a: Iterable[float], b: Iterable[float]) -> float:
    a, b = list(a), list(b)
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return 1 - dot / max(norm_a * norm_b, 1e-12)


def enroll(images: list[str]) -> str:
    if not isinstance(images, list) or len(images) < 3:
        raise DomainError("FACE_ENROLLMENT_INCOMPLETE", "Capture three live camera images to enrol your face.")
    embeddings = [_embedding(_image(image)) for image in images[:3]]
    # Average the three captures to make the enrolled reference less sensitive to
    # one imperfect frame; the raw images are discarded immediately.
    avg = [sum(values) / len(values) for values in zip(*embeddings)]
    return encrypt_template(avg)


def verify(images: list[str], encrypted_template: str) -> float:
    if not isinstance(images, list) or len(images) < 3:
        raise DomainError("FACE_VERIFICATION_INCOMPLETE", "Complete all three live camera captures.")
    template = decrypt_template(encrypted_template)
    distances = [_distance(_embedding(_image(image)), template) for image in images[:3]]
    # Require a majority of independently captured, liveness-screened frames.
    threshold = float(os.environ.get("FACE_MATCH_THRESHOLD", "0.35"))
    passed = [distance for distance in distances if distance <= threshold]
    if len(passed) < 2:
        raise DomainError("FACE_NOT_RECOGNISED", "Your face could not be matched. Improve lighting and try again, or contact an administrator.", 403)
    return sum(distances) / len(distances)
