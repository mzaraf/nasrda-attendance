from django.test import SimpleTestCase
from rest_framework.views import APIView
from rest_framework.test import APIRequestFactory

from .throttling import IppisLoginRateThrottle


class IppisLoginRateThrottleTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def cache_key_for(self, ippis_number):
        raw_request = self.factory.post("/api/auth/login/", {"ippis_number": ippis_number}, format="json")
        request = APIView().initialize_request(raw_request)
        throttle = IppisLoginRateThrottle()
        throttle.scope = "login"
        return throttle.get_cache_key(request, None)

    def test_each_ippis_number_has_its_own_login_throttle_key(self):
        self.assertNotEqual(self.cache_key_for("10001"), self.cache_key_for("10002"))

    def test_whitespace_does_not_create_a_different_staff_throttle_key(self):
        self.assertEqual(self.cache_key_for(" 10001 "), self.cache_key_for("10001"))

    def test_axes_lockout_is_limited_to_the_username(self):
        from django.conf import settings

        self.assertEqual(settings.AXES_LOCKOUT_PARAMETERS, ["username"])
