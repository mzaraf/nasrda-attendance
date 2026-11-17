from django.test import SimpleTestCase
from unittest.mock import patch

from rest_framework.views import APIView
from rest_framework.test import APIRequestFactory

from .throttling import IppisLoginRateThrottle
from .views import LoginView


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

    @patch("apps.attendance.views.IppisLoginRateThrottle.allow_request", return_value=True)
    @patch("apps.attendance.views.log")
    @patch("apps.attendance.views.AxesProxyHandler.is_locked", return_value=False)
    @patch("apps.attendance.views.authenticate", return_value=None)
    @patch("apps.attendance.views.get_user_model")
    def test_failed_login_passes_ippis_to_axes(self, get_user_model, authenticate, is_locked, _log, _throttle):
        get_user_model.return_value.objects.filter.return_value.exists.return_value = True
        request = self.factory.post(
            "/api/auth/login/", {"ippis_number": "482427", "password": "incorrect"}, format="json"
        )

        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 401)
        authenticate.assert_called_once_with(
            authenticate.call_args.args[0], ippis_number="482427", password="incorrect"
        )
        is_locked.assert_called_once_with(is_locked.call_args.args[0], credentials={"ippis_number": "482427"})

    @patch("apps.attendance.views.IppisLoginRateThrottle.allow_request", return_value=True)
    @patch("apps.attendance.views.log")
    @patch("apps.attendance.views.authenticate")
    @patch("apps.attendance.views.get_user_model")
    def test_missing_ippis_explains_that_no_profile_exists(self, get_user_model, authenticate, _log, _throttle):
        get_user_model.return_value.objects.filter.return_value.exists.return_value = False
        request = self.factory.post(
            "/api/auth/login/", {"ippis_number": "000000", "password": "incorrect"}, format="json"
        )

        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["code"], "IPPIS_NOT_FOUND")
        self.assertIn("contact your administrator", response.data["message"])
        authenticate.assert_not_called()
