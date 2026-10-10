"""Pure tests for replay focus recovery and protected input guardrails.

These tests intentionally run without Qt, a desktop display, or credentials.
"""
import unittest
from pathlib import Path
from action_studio.replay_safety import ReplaySafetyError, require_protected_field, wait_for_target_window


class Clock:
    def __init__(self):
        self.now = 0.0
    def time(self):
        return self.now
    def sleep(self, seconds):
        self.now += seconds


class ReplaySafetyTests(unittest.TestCase):
    def test_original_window_returns_before_timeout(self):
        c = Clock()
        events = []
        def foreground():
            return 123 if c.now >= 0.25 else 456
        wait_for_target_window(123, foreground, timeout=0.8, clock=c.time,
                               sleep=c.sleep, status=events.append, poll=0.05)
        self.assertEqual(events, [True, False])

    def test_never_accepts_a_different_window(self):
        c = Clock()
        events = []
        with self.assertRaisesRegex(ReplaySafetyError, 'did not regain focus'):
            wait_for_target_window(123, lambda: 456, timeout=0.2,
                                   clock=c.time, sleep=c.sleep, poll=0.05,
                                   status=events.append)
        self.assertEqual(events, [True, False])

    def test_abort_during_recovery_stops_early(self):
        c = Clock()
        with self.assertRaisesRegex(ReplaySafetyError, 'stopped by user'):
            wait_for_target_window(123, lambda: 456, timeout=10,
                                   cancelled=lambda: c.now >= 0.15,
                                   clock=c.time, sleep=c.sleep)
        self.assertLess(c.now, 0.5)

    def test_pause_time_does_not_exhaust_focus_timeout(self):
        c = Clock()
        wait_for_target_window(123, lambda: 123 if c.now >= 0.7 else 456,
                               timeout=0.3,
                               paused=lambda: 0.1 <= c.now < 0.6,
                               clock=c.time, sleep=c.sleep, poll=0.05)
        self.assertGreaterEqual(c.now, 0.7)

    def test_focused_original_window_returns_immediately(self):
        c = Clock()
        events = []
        wait_for_target_window(123, lambda: 123, clock=c.time,
                               sleep=c.sleep, status=events.append)
        self.assertEqual(c.now, 0)
        self.assertEqual(events, [])

    def test_rejects_missing_target_and_invalid_timeout(self):
        with self.assertRaises(ReplaySafetyError):
            wait_for_target_window(0, lambda: 0)
        with self.assertRaises(ValueError):
            wait_for_target_window(1, lambda: 1, timeout=-1)

    def test_secure_field_must_be_explicitly_verified(self):
        require_protected_field(lambda: 'protected')
        for state in ('safe', 'unknown', '', None):
            with self.subTest(state=state):
                with self.assertRaisesRegex(ReplaySafetyError, 'Secure input blocked'):
                    require_protected_field(lambda: state)
        with self.assertRaises(ReplaySafetyError):
            require_protected_field(lambda: 1/0)

    def test_security_error_does_not_include_secret(self):
        try:
            require_protected_field(lambda: 'safe')
        except ReplaySafetyError as error:
            self.assertNotIn('hunter2', str(error))

    def test_player_guards_automatic_secret_dispatch_and_uses_focus_gate(self):
        source = (Path(__file__).resolve().parents[1] / 'action_studio' / 'playback.py').read_text(encoding='utf-8')
        self.assertIn('require_protected_field(focus_status)', source)
        self.assertIn('protected=True)', source)
        self.assertIn('recover_focus=True', source)
        self.assertIn('status=self.focus_waiting.emit', source)
        self.assertNotIn('activate_target_window(', source)


if __name__ == '__main__':
    unittest.main()
