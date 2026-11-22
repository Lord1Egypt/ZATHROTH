"""Unit tests for the abuse limits and the CAPTCHA."""

import re
import unittest

import guard
from guard import ALPHABET, AuthGuard, Captchas, draw


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class AuthGuardTest(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.guard = AuthGuard(self.clock)

    def test_an_address_needs_a_captcha_then_is_blocked_then_recovers(self):
        for attempt in range(guard.IP_BLOCK_AFTER):
            self.assertFalse(self.guard.blocked("203.0.113.7"), attempt)
            self.assertEqual(self.guard.needs_captcha("203.0.113.7"), attempt >= guard.IP_CAPTCHA_AFTER)
            self.guard.failed("203.0.113.7", f"user{attempt}")
        self.assertTrue(self.guard.blocked("203.0.113.7"))
        self.assertFalse(self.guard.blocked("203.0.113.8"))
        self.clock.now += guard.IP_WINDOW + 1
        self.assertFalse(self.guard.blocked("203.0.113.7"))
        self.assertFalse(self.guard.needs_captcha("203.0.113.7"))

    def test_an_account_is_blocked_whoever_is_guessing(self):
        for attempt in range(guard.ACCOUNT_BLOCK_AFTER):
            self.assertFalse(self.guard.blocked(f"198.51.100.{attempt}", " Victim "))
            self.guard.failed(f"198.51.100.{attempt}", " Victim ")
        self.assertTrue(self.guard.blocked("192.0.2.1", "victim"))
        self.assertFalse(self.guard.blocked("192.0.2.1", "someone-else"))
        self.clock.now += guard.ACCOUNT_WINDOW + 1
        self.assertFalse(self.guard.blocked("192.0.2.1", "victim"))

    def test_new_accounts_are_limited_per_address_and_overall(self):
        for _ in range(guard.REGISTRATIONS_PER_IP):
            self.assertTrue(self.guard.may_register("203.0.113.7"))
            self.guard.registered("203.0.113.7")
        self.assertFalse(self.guard.may_register("203.0.113.7"))
        self.assertTrue(self.guard.may_register("203.0.113.8"))
        self.clock.now += 86401
        self.assertTrue(self.guard.may_register("203.0.113.7"))

        for index in range(guard.REGISTRATIONS_PER_HOUR):
            self.guard.registered(f"10.0.{index // 250}.{index % 250}")
        self.assertFalse(self.guard.may_register("192.0.2.99"))
        self.clock.now += 3601
        self.assertTrue(self.guard.may_register("192.0.2.99"))

    def test_tracking_is_bounded(self):
        for index in range(guard.MAX_TRACKED + 50):
            self.guard.failed(f"host{index}", "")
        self.assertLessEqual(len(self.guard.ip_failures), guard.MAX_TRACKED)


class CaptchaTest(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.captchas = Captchas(self.clock)

    def answer(self, token):
        return self.captchas.pending[token][0]

    def test_a_challenge_is_answered_once_ignoring_case_and_spaces(self):
        token, _ = self.captchas.issue()
        code = self.answer(token)
        self.assertEqual(len(code), guard.LENGTH)
        self.assertTrue(set(code) <= set(ALPHABET))
        self.assertTrue(self.captchas.verify(token, f" {code[:2].lower()} {code[2:].lower()} "))
        self.assertFalse(self.captchas.verify(token, code))

    def test_a_wrong_answer_uses_the_challenge_up(self):
        token, _ = self.captchas.issue()
        code = self.answer(token)
        self.assertFalse(self.captchas.verify(token, "WRONG"))
        self.assertFalse(self.captchas.verify(token, code))

    def test_unknown_expired_and_odd_answers_fail(self):
        self.assertFalse(self.captchas.verify("0" * 32, "ABCDE"))
        token, _ = self.captchas.issue()
        self.assertFalse(self.captchas.verify(token, "ÄÖÜ✓"))
        token, _ = self.captchas.issue()
        code = self.answer(token)
        self.clock.now += guard.LIFETIME + 1
        self.assertFalse(self.captchas.verify(token, code))

    def test_pending_challenges_are_bounded(self):
        first, _ = self.captchas.issue()
        for _ in range(guard.MAX_PENDING):
            self.captchas.issue()
        self.assertLessEqual(len(self.captchas.pending), guard.MAX_PENDING)
        self.assertNotIn(first, self.captchas.pending)

    def test_the_picture_never_contains_the_answer_as_text(self):
        for _ in range(20):
            token, picture = self.captchas.issue()
            code = self.answer(token)
            self.assertTrue(picture.startswith("<svg") and picture.endswith("</svg>"))
            self.assertNotIn("<text", picture)
            self.assertNotIn(code, picture)
            self.assertNotRegex(picture, r"<script|on\w+=|style=|href=")

    def test_every_glyph_draws(self):
        class Fixed:
            def uniform(self, low, high):
                return (low + high) / 2

        for char in ALPHABET:
            self.assertRegex(draw(char * 3, Fixed()), r'<path d="M[^"]+" stroke="#ece0c0"')


if __name__ == "__main__":
    unittest.main()
