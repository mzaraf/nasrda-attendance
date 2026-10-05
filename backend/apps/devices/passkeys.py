import json

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from webauthn import (generate_authentication_options, generate_registration_options,
                      options_to_json, verify_authentication_response,
                      verify_registration_response)
from webauthn.helpers import base64url_to_bytes
from webauthn.helpers.structs import (AuthenticatorAttachment, AuthenticatorSelectionCriteria,
                                      PublicKeyCredentialDescriptor, ResidentKeyRequirement,
                                      UserVerificationRequirement)

from apps.core.errors import DomainError
from apps.core.models import get_setting
from .models import PasskeyCredential, RegisteredDevice

TTL = 300


def _key(kind, uid):
    return f"webauthn:{kind}:{uid}"


def registration_options(user):
    active = user.devices.exclude(status="revoked")
    if active.count() >= get_setting("max_devices"):
        raise DomainError("DEVICE_LIMIT", "You have reached the maximum number of registered devices. "
                                          "Ask an administrator to reset your device.", 409)
    opts = generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID, rp_name=settings.WEBAUTHN_RP_NAME,
        user_id=str(user.pk).encode(), user_name=user.ippis_number,
        user_display_name=user.get_full_name() or user.ippis_number,
        # A revoked device is no longer trusted. Keeping it in WebAuthn's exclusion
        # list prevents that staff member from registering the same phone again after
        # an approved device-removal request (the browser reports it as previously
        # registered). Only credentials that are still usable or awaiting approval
        # should block a duplicate registration.
        exclude_credentials=[PublicKeyCredentialDescriptor(id=bytes(c.credential_id))
                             for c in PasskeyCredential.objects.filter(
                                 device__user=user,
                                 device__status__in=[RegisteredDevice.Status.ACTIVE,
                                                     RegisteredDevice.Status.PENDING])],
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,   # phone/laptop biometric
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED),
    )
    cache.set(_key("reg", user.pk), opts.challenge, TTL)
    return json.loads(options_to_json(opts))


def finish_registration(user, credential, label, user_agent):
    challenge = cache.get(_key("reg", user.pk))
    cache.delete(_key("reg", user.pk))
    if not challenge:
        raise DomainError("CHALLENGE_EXPIRED", "Registration expired. Please try again.")
    try:
        v = verify_registration_response(
            credential=credential, expected_challenge=challenge,
            expected_rp_id=settings.WEBAUTHN_RP_ID, expected_origin=settings.WEBAUTHN_ORIGIN,
            require_user_verification=True)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("WebAuthn registration verify failed: %s", exc)  # TEMP: remove after debugging
        raise DomainError("PASSKEY_INVALID", "Could not verify this device. Please try again.")
    status = "pending" if get_setting("device_approval_required") else "active"
    device = RegisteredDevice.objects.create(user=user, label=label[:80], status=status,
                                             user_agent=user_agent[:300])
    PasskeyCredential.objects.create(device=device, credential_id=v.credential_id,
                                     public_key=v.credential_public_key, sign_count=v.sign_count)
    return device


def authentication_options(user):
    creds = PasskeyCredential.objects.filter(device__user=user, device__status="active")
    if not creds.exists():
        raise DomainError("DEVICE_NOT_REGISTERED",
                          "This account has no active registered device. Please register your device.", 409)
    opts = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        allow_credentials=[PublicKeyCredentialDescriptor(id=bytes(c.credential_id)) for c in creds],
        user_verification=UserVerificationRequirement.REQUIRED)
    cache.set(_key("auth", user.pk), opts.challenge, TTL)
    return json.loads(options_to_json(opts))


def verify_assertion(user, assertion):
    """Proves: registered device + private key + biometric/PIN. Returns the RegisteredDevice."""
    challenge = cache.get(_key("auth", user.pk))
    cache.delete(_key("auth", user.pk))                     # single use: replay-proof
    if not challenge:
        raise DomainError("CHALLENGE_EXPIRED", "Verification expired. Please try again.")
    try:
        cred = PasskeyCredential.objects.select_related("device").get(
            credential_id=base64url_to_bytes(assertion["id"]),
            device__user=user, device__status="active")
    except (PasskeyCredential.DoesNotExist, KeyError, TypeError):
        raise DomainError("DEVICE_NOT_REGISTERED", "This device is not registered to your account.", 403)
    try:
        v = verify_authentication_response(
            credential=assertion, expected_challenge=challenge,
            expected_rp_id=settings.WEBAUTHN_RP_ID, expected_origin=settings.WEBAUTHN_ORIGIN,
            credential_public_key=bytes(cred.public_key),
            credential_current_sign_count=cred.sign_count, require_user_verification=True)
    except Exception:
        raise DomainError("PASSKEY_INVALID", "Biometric verification failed.", 403)
    cred.sign_count = v.new_sign_count
    cred.save(update_fields=["sign_count"])
    cred.device.last_seen_at = timezone.now()
    cred.device.save(update_fields=["last_seen_at"])
    return cred.device


def require_factor(user, assertion):
    """Returns (device|None, auth_method). Honours the `require_passkey` setting."""
    if not get_setting("require_passkey"):
        return None, "password_only"
    if not assertion:
        raise DomainError("PASSKEY_REQUIRED", "Biometric verification is required.", 403)
    return verify_assertion(user, assertion), "passkey"
