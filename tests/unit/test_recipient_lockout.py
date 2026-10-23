"""
Recipient Lockout & Exponential Backoff Test Suite
Validates persistent database-backed rate-limiting lockout per pass and per IP:
1. Locks after 5 failed attempts with HTTP 429 and Retry-After header
2. Survives cleared cookies and new sessions
3. Backoff grows exponentially (1m, 2m, 4m... up to 24 hours)
4. Failure count and lockout reset on successful key entry
5. Handles concurrent verification attempts atomically with select_for_update
"""

import threading
from datetime import timedelta
from django.test import TestCase, Client, TransactionTestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from sharing.models import SharePass, SharePassLockout
from documents.models import Document

from tests.unit import get_test_password
from audit.models import get_client_ip
from django.test import override_settings

User = get_user_model()


class RecipientLockoutTests(TestCase):
    """Unit tests for recipient lockout behavior and exponential backoff."""

    def setUp(self):
        self.password = get_test_password()
        self.owner = User.objects.create_user(
            username="lockoutowner",
            email="owner@passli.dev",
            password=self.password,
            is_active=True,
        )
        self.doc = Document.objects.create(
            user=self.owner,
            title="Confidential Report.pdf",
            file="documents/dummy_report.pdf",
            file_size=1024,
            file_type="application/pdf",
        )
        self.share_pass = SharePass.objects.create(
            owner=self.owner,
            title="Partner Review",
            expires_at=timezone.now() + timedelta(hours=2),
            can_view=True,
        )
        self.share_pass.documents.add(self.doc)
        self.correct_key = "8K7P-42XM"
        self.share_pass.set_key(self.correct_key)
        self.share_pass.save()

        self.verify_url = reverse("recipient_verify", kwargs={"pass_id": self.share_pass.id})
        self.client_ip = "198.51.100.42"

    def _post_key(self, client: Client, key: str, ip: str = None):
        client_ip = ip or self.client_ip
        return client.post(
            self.verify_url,
            {"access_key": key},
            REMOTE_ADDR=client_ip,
        )

    def _get_verify(self, client: Client, ip: str = None):
        client_ip = ip or self.client_ip
        return client.get(
            self.verify_url,
            REMOTE_ADDR=client_ip,
        )

    def test_locks_after_5_failures(self):
        """Pass locks after 5 consecutive failures, returning 429 and Retry-After: 60."""
        client = Client()

        # Attempts 1 through 4 should fail but not lock
        for i in range(1, 5):
            res = self._post_key(client, "WRON-GKEY")
            self.assertEqual(res.status_code, 200, f"Attempt {i} should return 200 with form error")
            lockout = SharePassLockout.objects.get(share_pass=self.share_pass, ip_address=self.client_ip)
            self.assertEqual(lockout.failed_attempts, i)
            self.assertFalse(lockout.is_locked)

        # 5th attempt must trigger the first lockout (1 minute = 60 seconds)
        res5 = self._post_key(client, "WRON-GKEY")
        self.assertEqual(res5.status_code, 429)
        self.assertIn("Retry-After", res5.headers)
        self.assertEqual(res5.headers["Retry-After"], "60")

        lockout = SharePassLockout.objects.get(share_pass=self.share_pass, ip_address=self.client_ip)
        self.assertEqual(lockout.failed_attempts, 5)
        self.assertTrue(lockout.is_locked)
        self.assertIsNotNone(lockout.locked_until)

    def test_survives_cleared_cookies_and_new_sessions(self):
        """Lockout persists in database and cannot be bypassed by clearing cookies or opening new sessions."""
        client1 = Client()

        # Trigger lockout with 5 failures
        for _ in range(5):
            self._post_key(client1, "WRON-GKEY")

        lockout = SharePassLockout.objects.get(share_pass=self.share_pass, ip_address=self.client_ip)
        self.assertTrue(lockout.is_locked)

        # 1. Clear cookies on current client
        client1.cookies.clear()
        res_cleared = self._get_verify(client1)
        self.assertEqual(res_cleared.status_code, 429)
        self.assertIn("Retry-After", res_cleared.headers)

        res_cleared_post = self._post_key(client1, self.correct_key)
        self.assertEqual(res_cleared_post.status_code, 429)

        # 2. Brand new client from the same IP (simulating incognito / curl / session reset)
        fresh_client = Client()
        res_fresh_get = self._get_verify(fresh_client)
        self.assertEqual(res_fresh_get.status_code, 429)
        self.assertIn("Retry-After", res_fresh_get.headers)

        # 3. Client from a different IP should NOT be locked
        other_client = Client()
        res_other = self._get_verify(other_client, ip="192.0.2.99")
        self.assertEqual(res_other.status_code, 200)

    def test_backoff_grows_exponentially(self):
        """Lockout backoff doubles on subsequent failures: 60s, 120s, 240s, capped at 24 hours."""
        client = Client()

        # 5 failures -> 60s lockout
        for _ in range(5):
            self._post_key(client, "WRON-GKEY")

        lockout = SharePassLockout.objects.get(share_pass=self.share_pass, ip_address=self.client_ip)
        self.assertEqual(lockout.failed_attempts, 5)

        # Simulate lock expiry by setting locked_until in the past
        lockout.locked_until = timezone.now() - timedelta(seconds=1)
        lockout.save()

        # 6th failure -> doubles to 120 seconds
        res6 = self._post_key(client, "WRON-GKEY")
        self.assertEqual(res6.status_code, 429)
        self.assertEqual(res6.headers["Retry-After"], "120")

        lockout.refresh_from_db()
        self.assertEqual(lockout.failed_attempts, 6)

        # Simulate lock expiry again
        lockout.locked_until = timezone.now() - timedelta(seconds=1)
        lockout.save()

        # 7th failure -> doubles to 240 seconds
        res7 = self._post_key(client, "WRON-GKEY")
        self.assertEqual(res7.status_code, 429)
        self.assertEqual(res7.headers["Retry-After"], "240")

        lockout.refresh_from_db()
        self.assertEqual(lockout.failed_attempts, 7)

        # Test 24-hour cap (86400 seconds)
        lockout.failed_attempts = 19
        lockout.locked_until = timezone.now() - timedelta(seconds=1)
        lockout.save()

        res_capped = self._post_key(client, "WRON-GKEY")
        self.assertEqual(res_capped.status_code, 429)
        self.assertEqual(res_capped.headers["Retry-After"], "86400")

    def test_reset_on_success(self):
        """Successful Share Key verification resets failure counter and clears lockout."""
        client = Client()

        # Make 4 failed attempts
        for _ in range(4):
            self._post_key(client, "WRON-GKEY")

        lockout = SharePassLockout.objects.get(share_pass=self.share_pass, ip_address=self.client_ip)
        self.assertEqual(lockout.failed_attempts, 4)

        # Submit valid key on 5th attempt
        res_success = self._post_key(client, self.correct_key)
        self.assertEqual(res_success.status_code, 302)
        self.assertIn(f"/p/{self.share_pass.id}/portal/", res_success.url)

        # Verify lockout record was reset
        lockout.refresh_from_db()
        self.assertEqual(lockout.failed_attempts, 0)
        self.assertIsNone(lockout.locked_until)

    def test_reset_on_success_after_lockout_expires(self):
        """User who was previously locked out can succeed once timer lapses and reset counters."""
        client = Client()

        for _ in range(5):
            self._post_key(client, "WRON-GKEY")

        lockout = SharePassLockout.objects.get(share_pass=self.share_pass, ip_address=self.client_ip)
        self.assertEqual(lockout.failed_attempts, 5)

        # Expire lock
        lockout.locked_until = timezone.now() - timedelta(seconds=1)
        lockout.save()

        # Now enter correct key
        res_success = self._post_key(client, self.correct_key)
        self.assertEqual(res_success.status_code, 302)

        lockout.refresh_from_db()
        self.assertEqual(lockout.failed_attempts, 0)
        self.assertIsNone(lockout.locked_until)

    def test_spoofed_x_forwarded_for_still_ends_in_lockout(self):
        """
        Spoofing a different leftmost entry in X-Forwarded-For on every attempt
        still resolves to the legitimate client IP (via TRUSTED_PROXY_COUNT) and ends in lockout.
        """
        client = Client()
        proxy_ip = "198.51.100.25"

        for i in range(5):
            spoofed_header = f"192.0.2.{i + 1}, {proxy_ip}"
            res = client.post(
                self.verify_url,
                {"access_key": "WRON-GKEY"},
                HTTP_X_FORWARDED_FOR=spoofed_header,
                REMOTE_ADDR="127.0.0.1",
            )
            if i < 4:
                self.assertEqual(res.status_code, 200)
            else:
                self.assertEqual(res.status_code, 429)
                self.assertIn("Retry-After", res.headers)

        # Confirm lockout row was created for proxy_ip, NOT the fake leftmost IP
        lockout = SharePassLockout.objects.filter(share_pass=self.share_pass, ip_address=proxy_ip).first()
        self.assertIsNotNone(lockout)
        self.assertEqual(lockout.failed_attempts, 5)

        # 6th attempt with yet another spoofed IP is immediately rejected with 429
        res6 = client.post(
            self.verify_url,
            {"access_key": "WRON-GKEY"},
            HTTP_X_FORWARDED_FOR=f"192.0.2.99, {proxy_ip}",
            REMOTE_ADDR="127.0.0.1",
        )
        self.assertEqual(res6.status_code, 429)

    def test_global_counter_locks_pass_across_many_ips(self):
        """
        50 total failed attempts across 50 different IP addresses locks the pass globally
        for 15 minutes regardless of IP, returning HTTP 429 and Retry-After.
        """
        client = Client()

        for i in range(50):
            ip = f"10.0.{i // 250}.{(i % 250) + 1}"
            res = client.post(
                self.verify_url,
                {"access_key": "WRON-GKEY"},
                REMOTE_ADDR=ip,
            )
            if i < 49:
                self.assertEqual(res.status_code, 200)
            else:
                # 50th attempt triggers global lockout
                self.assertEqual(res.status_code, 429)
                self.assertEqual(res.headers.get("Retry-After"), "900")

        self.share_pass.refresh_from_db()
        self.assertTrue(self.share_pass.is_globally_locked)
        self.assertEqual(self.share_pass.global_failed_attempts, 50)

        # Fresh 51st IP gets locked out immediately on GET or POST
        fresh_client = Client()
        res_post = fresh_client.post(
            self.verify_url,
            {"access_key": "WRON-GKEY"},
            REMOTE_ADDR="192.168.200.1",
        )
        self.assertEqual(res_post.status_code, 429)
        self.assertTrue(int(res_post.headers.get("Retry-After", 0)) > 0)

        res_get = fresh_client.get(
            self.verify_url,
            REMOTE_ADDR="192.168.200.1",
        )
        self.assertEqual(res_get.status_code, 429)
        self.assertTrue(int(res_get.headers.get("Retry-After", 0)) > 0)

    def test_legitimate_proxy_request_resolves_correctly(self):
        """Legitimate proxy header resolves to expected hop according to TRUSTED_PROXY_COUNT."""
        from django.test.client import RequestFactory
        factory = RequestFactory()

        # TRUSTED_PROXY_COUNT = 1: takes 1st from right
        with override_settings(TRUSTED_PROXY_COUNT=1):
            req = factory.get("/", HTTP_X_FORWARDED_FOR="192.0.2.1, 198.51.100.10", REMOTE_ADDR="127.0.0.1")
            self.assertEqual(get_client_ip(req), "198.51.100.10")

        # TRUSTED_PROXY_COUNT = 2: takes 2nd from right
        with override_settings(TRUSTED_PROXY_COUNT=2):
            req = factory.get("/", HTTP_X_FORWARDED_FOR="192.0.2.1, 198.51.100.10, 203.0.113.20", REMOTE_ADDR="127.0.0.1")
            self.assertEqual(get_client_ip(req), "198.51.100.10")

        # Header has fewer entries than TRUSTED_PROXY_COUNT: falls back to REMOTE_ADDR
        with override_settings(TRUSTED_PROXY_COUNT=3):
            req = factory.get("/", HTTP_X_FORWARDED_FOR="192.0.2.1", REMOTE_ADDR="127.0.0.1")
            self.assertEqual(get_client_ip(req), "127.0.0.1")


class ConcurrentLockoutTests(TransactionTestCase):
    """Concurrency verification ensuring select_for_update handles parallel requests without race conditions."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username="concurrentowner",
            email="concurrent@passli.dev",
            password=get_test_password(),
            is_active=True,
        )
        self.doc = Document.objects.create(
            user=self.owner,
            title="Financial Statement.pdf",
            file="documents/financials.pdf",
            file_size=2048,
            file_type="application/pdf",
        )
        self.share_pass = SharePass.objects.create(
            owner=self.owner,
            title="Concurrent Security Audit",
            expires_at=timezone.now() + timedelta(hours=1),
            can_view=True,
        )
        self.share_pass.documents.add(self.doc)
        self.share_pass.set_key("CONC-PASS")
        self.share_pass.save()

        self.verify_url = reverse("recipient_verify", kwargs={"pass_id": self.share_pass.id})
        self.client_ip = "203.0.113.10"

    def test_concurrent_attempts(self):
        """Concurrent requests to recipient_verify serialize updates and accurately trigger lockout."""
        num_threads = 5
        responses = []
        errors = []

        def worker():
            from django.db import connection
            try:
                client = Client()
                res = client.post(
                    self.verify_url,
                    {"access_key": "BAD-KEYY"},
                    REMOTE_ADDR=self.client_ip,
                )
                responses.append(res.status_code)
            except Exception as e:
                errors.append(e)
            finally:
                connection.close()

        from django.db import connection
        connection.close()

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent execution produced errors: {errors}")
        self.assertEqual(len(responses), num_threads)

        lockout = SharePassLockout.objects.get(share_pass=self.share_pass, ip_address=self.client_ip)
        self.assertEqual(lockout.failed_attempts, num_threads)
        self.assertTrue(lockout.is_locked)
        self.assertIsNotNone(lockout.locked_until)
