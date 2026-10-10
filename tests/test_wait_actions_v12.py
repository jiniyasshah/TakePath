"""Regression tests for explicitly configured readiness Wait actions."""
import unittest
from pathlib import Path

from action_studio.action_wait import (
    ConditionCancelled, ConditionTimeout, contains_title, wait_until_ready,
)
from action_studio.core import Action, Project


class FakeClock:
    def __init__(self):
        self.t=0.0
    def now(self):
        return self.t
    def sleep(self,duration):
        self.t+=duration


class ReadinessWaitTests(unittest.TestCase):
    def test_requires_stable_positive_checks(self):
        clock=FakeClock()
        results=iter((False,True,False,True,True))
        markers=[]
        wait_until_ready(lambda:next(results),timeout=2,clock=clock.now,
                         sleep=clock.sleep,poll=0.1,status=markers.append)
        self.assertEqual(markers,[True,False])

    def test_times_out_without_input(self):
        clock=FakeClock()
        with self.assertRaises(ConditionTimeout):
            wait_until_ready(lambda:False,timeout=0.35,clock=clock.now,
                             sleep=clock.sleep,poll=0.05)
        self.assertLess(clock.t,0.5)

    def test_fractional_timeout_never_spins_forever(self):
        clock=FakeClock()
        calls=[0]
        def tracked_sleep(duration):
            calls[0]+=1
            if calls[0] > 100:
                self.fail('Timed-out Wait action is trapped in a zero-progress loop')
            clock.sleep(duration)
        with self.assertRaises(ConditionTimeout):
            wait_until_ready(lambda:False, timeout=0.35, clock=clock.now,
                             sleep=tracked_sleep, poll=0.05)
        self.assertLess(calls[0],30)

    def test_cancel_and_cleanup(self):
        clock=FakeClock()
        markers=[]
        with self.assertRaises(ConditionCancelled):
            wait_until_ready(lambda:False,timeout=5,clock=clock.now,
                             sleep=clock.sleep,cancel=lambda:clock.t>=0.2,
                             status=markers.append)
        self.assertEqual(markers,[True,False])

    def test_pause_does_not_consume_timeout(self):
        clock=FakeClock()
        wait_until_ready(lambda:clock.t>=0.8,timeout=0.4,
                         paused=lambda:0.1<=clock.t<0.6,
                         clock=clock.now,sleep=clock.sleep,poll=0.05,
                         stable_polls=1)

    def test_window_title_match(self):
        self.assertTrue(contains_title('Save As — Chrome','save as'))
        self.assertFalse(contains_title('Save As',''))
        self.assertFalse(contains_title('Sign In','Save As'))

    def test_roundtrip_preserves_wait_condition(self):
        a=Action(kind='wait',wait_mode='active_title',wait_value='Save As',
                 wait_timeout=18.5)
        restored=Project.from_dict(Project(actions=[a]).to_dict()).actions[0]
        self.assertEqual(restored.wait_mode,'active_title')
        self.assertEqual(restored.wait_value,'Save As')
        self.assertEqual(restored.wait_timeout,18.5)

    def test_invalid_wait_values_sanitized(self):
        a=Action.from_dict({'kind':'wait','wait_mode':'invalid',
                            'wait_timeout':999,'wait_value':'X'*200})
        self.assertEqual(a.wait_mode,'target_title')
        self.assertEqual(a.wait_timeout,120)
        self.assertEqual(len(a.wait_value),160)

    def test_old_project_defaults_unaffected(self):
        p=Project.from_dict(Project(actions=[Action(kind='click',x=55)]).to_dict())
        self.assertEqual(p.actions[0].kind,'click')
        self.assertEqual(p.actions[0].wait_mode,'target_title')

    def test_ui_and_playback_integrated(self):
        root=Path(__file__).resolve().parents[1]
        ui=(root/'action_studio/ui.py').read_text(encoding='utf-8')
        player=(root/'action_studio/playback.py').read_text(encoding='utf-8')
        self.assertIn("'secure_input','wait'",ui)
        self.assertIn('self.wait_container.setVisible',ui)
        self.assertIn('self._run_wait_action(a)',player)
        self.assertIn('self.readiness_waiting.emit',player)


if __name__=='__main__':
    unittest.main()
