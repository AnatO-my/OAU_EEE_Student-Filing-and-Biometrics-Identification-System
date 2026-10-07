"""Failed-login throttling tests through the real csrf and login endpoints."""
import time

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from .models import User
from .throttling import LOGIN_FAILURE_LIMIT, login_failure_key


class LoginThrottlingTests(TestCase):
    #the counter lives in a process wide cache, so every test starts from zero
    #and cannot be poisoned by failures recorded by an earlier test
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.staff = User.objects.create_user(
            username="example-staff-throttle",
            password="synthetic-test-password",
            is_staff=True,
        )
        self.other = User.objects.create_user(
            username="example-staff-other-throttle",
            password="synthetic-test-password",
            is_staff=True,
        )

    #method that posts credentials through the real endpoint, fetching a csrf
    #token first because login enforces it
    def _attempt(self, username, password):
        token = self.client.get("/api/auth/csrf/").data["csrfToken"]
        return self.client.post(
            "/api/auth/login/",
            {"username": username, "password": password},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

    def test_repeated_failures_are_paused_with_429_and_retry_after(self):
        for _ in range(LOGIN_FAILURE_LIMIT):
            response = self._attempt("example-staff-throttle", "wrong-password")
            self.assertEqual(response.status_code, 400)

        blocked = self._attempt("example-staff-throttle", "synthetic-test-password")
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("Too many failed sign in attempts", blocked.data["detail"])
        self.assertGreater(int(blocked["Retry-After"]), 0)
        self.assertLessEqual(int(blocked["Retry-After"]), 60 * 15)

    def test_successful_sign_in_clears_the_count(self):
        for _ in range(LOGIN_FAILURE_LIMIT - 1):
            response = self._attempt("example-staff-throttle", "wrong-password")
            self.assertEqual(response.status_code, 400)

        allowed = self._attempt("example-staff-throttle", "synthetic-test-password")
        self.assertEqual(allowed.status_code, 200)

        #the count restarted at zero, so the same number of failures is again
        #accepted rather than refused as a lockout
        for _ in range(LOGIN_FAILURE_LIMIT - 1):
            response = self._attempt("example-staff-throttle", "wrong-password")
            self.assertEqual(response.status_code, 400)

    def test_lockout_is_scoped_to_the_submitted_username(self):
        for _ in range(LOGIN_FAILURE_LIMIT):
            self._attempt("example-staff-throttle", "wrong-password")

        blocked = self._attempt("example-staff-throttle", "synthetic-test-password")
        self.assertEqual(blocked.status_code, 429)

        #a colleague at the same address with a different username is unaffected
        unaffected = self._attempt("example-staff-other-throttle", "synthetic-test-password")
        self.assertEqual(unaffected.status_code, 200)

    def test_unknown_username_counts_toward_the_same_limit(self):
        for _ in range(LOGIN_FAILURE_LIMIT):
            response = self._attempt("example-ghost-throttle", "whatever")
            self.assertEqual(response.status_code, 400)

        blocked = self._attempt("example-ghost-throttle", "anything-else")
        self.assertEqual(blocked.status_code, 429)

    def test_blocked_answer_is_identical_for_wrong_and_right_passwords(self):
        for _ in range(LOGIN_FAILURE_LIMIT):
            self._attempt("example-staff-throttle", "wrong-password")

        wrong = self._attempt("example-staff-throttle", "wrong-password")
        right = self._attempt("example-staff-throttle", "synthetic-test-password")
        self.assertEqual(wrong.status_code, 429)
        self.assertEqual(right.status_code, 429)
        self.assertEqual(wrong.data, right.data)

    def test_an_expired_window_allows_attempts_again(self):
        for _ in range(LOGIN_FAILURE_LIMIT):
            self._attempt("example-staff-throttle", "wrong-password")

        key = login_failure_key("127.0.0.1", "example-staff-throttle")
        count, _reset_at = cache.get(key)
        #simulates the window eluding the cache timeout, the counter must treat
        #the entry as gone rather than blocking forever
        cache.set(key, (count, time.time() - 1))

        allowed = self._attempt("example-staff-throttle", "synthetic-test-password")
        self.assertEqual(allowed.status_code, 200)
        self.assertIsNone(cache.get(key))
