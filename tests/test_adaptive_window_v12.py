"""TakePath 1.2: geometry anchoring and best-effort visual readiness tests."""
import unittest
from pathlib import Path

from action_studio.core import Action, Project
from action_studio.window_geometry import remap_action, remap_point
from action_studio.adaptive_ready import (
    average_difference, wait_for_visual_settle, VisualSettlingInterrupted
)


class Clock:
    def __init__(self):
        self.t=0.0
    def now(self):
        return self.t
    def sleep(self,seconds):
        self.t+=seconds


class GeometryTests(unittest.TestCase):
    def test_moving_window_preserves_relative_click_location(self):
        self.assertEqual(remap_point(150,250,[100,200,800,600],
                                     [300,400,800,600]),(350,450))

    def test_resizing_window_scales_clicks_and_drag_ends(self):
        a=Action(kind='drag',x=100,y=100,end_x=400,end_y=300,
                 raw_path=[[100,100,0],[400,300,0.4]])
        mapped=remap_action(a,[0,0,800,600],[50,30,1600,1200])
        self.assertEqual((mapped.x,mapped.y),(250,230))
        self.assertEqual((mapped.end_x,mapped.end_y),(850,630))
        self.assertEqual(mapped.raw_path[0], [250,230,0])
        self.assertEqual(mapped.raw_path[1], [850,630,0.4])
        self.assertEqual((a.x,a.y),(100,100))  # original project unchanged

    def test_negative_monitor_positions(self):
        self.assertEqual(remap_point(-900,200,[-1000,0,900,800],
                                     [100,50,900,800]), (200,250))

    def test_extreme_resize_refuses_to_guess(self):
        with self.assertRaisesRegex(ValueError,'size changed too much'):
            remap_point(30,30,[0,0,1000,1000],[0,0,80,100])

    def test_invalid_geometry_refuses_mapping(self):
        with self.assertRaises(ValueError):
            remap_point(10,10,[],[0,0,800,600])

    def test_nonpointer_action_not_modified(self):
        a=Action(kind='type',text='Hello')
        self.assertIs(remap_action(a,[0,0,800,600],[0,0,1000,800]),a)

    def test_project_roundtrip_includes_anchor_and_preference(self):
        p=Project(recorded_window_bounds=[-500,100,1000,700],adaptive_wait=True)
        q=Project.from_dict(p.to_dict())
        self.assertEqual(q.recorded_window_bounds,p.recorded_window_bounds)
        self.assertTrue(q.adaptive_wait)

    def test_legacy_project_keeps_old_behavior(self):
        data=Project(actions=[Action(kind='click')]).to_dict()
        data.pop('recorded_window_bounds')
        data.pop('adaptive_wait')
        p=Project.from_dict(data)
        self.assertEqual(p.recorded_window_bounds,[])
        self.assertFalse(p.adaptive_wait)


class VisualReadinessTests(unittest.TestCase):
    def test_unchanged_screen_quietly_continues(self):
        clock=Clock()
        settled=wait_for_visual_settle(lambda:b'abc',clock=clock.now,
                                       sleep=clock.sleep,unchanged_grace=.5,poll=.1)
        self.assertTrue(settled)
        self.assertGreaterEqual(clock.t,.5)

    def test_change_then_settle(self):
        clock=Clock()
        def sample():
            return bytes([0 if clock.t<.15 else 220]*100)
        self.assertTrue(wait_for_visual_settle(sample,clock=clock.now,
                                               sleep=clock.sleep,poll=.1,
                                               unchanged_grace=.8,quiet_seconds=.3))
        self.assertGreaterEqual(clock.t,.4)

    def test_continuous_change_times_out(self):
        clock=Clock()
        def sample():
            return bytes([int(clock.t*100)%256]*100)
        self.assertFalse(wait_for_visual_settle(sample,clock=clock.now,
                                                sleep=clock.sleep,max_seconds=1,
                                                quiet_seconds=.25,unchanged_grace=.7,poll=.1))

    def test_fractional_visual_timeout_never_spins_forever(self):
        clock=Clock()
        calls=[0]
        def tracked_sleep(duration):
            calls[0]+=1
            if calls[0]>100:
                self.fail('Adaptive wait timed out but its fake clock never advances')
            clock.sleep(duration)
        def moving_sample():
            return bytes([int(clock.t*100) % 256]*100)
        self.assertFalse(wait_for_visual_settle(
            moving_sample,clock=clock.now,sleep=tracked_sleep,
            max_seconds=1,quiet_seconds=.25,unchanged_grace=.7,poll=.1))
        self.assertLess(calls[0],30)

    def test_missing_capture_returns_fallback(self):
        self.assertFalse(wait_for_visual_settle(lambda:None))

    def test_fails_safe_when_user_cancels(self):
        clock=Clock()
        with self.assertRaises(VisualSettlingInterrupted):
            wait_for_visual_settle(lambda:b'aaa',cancel=lambda:clock.t>.2,
                                   clock=clock.now,sleep=clock.sleep,poll=.1)

    def test_differing_length_samples_do_not_look_equal(self):
        self.assertEqual(average_difference(b'abc',b'abc'),0)
        self.assertEqual(average_difference(b'aaa',b'zzz'),25)
        self.assertEqual(average_difference(b'abc',b'ab'),float('inf'))

    def test_player_and_editor_are_wired(self):
        root=Path(__file__).resolve().parents[1]
        player=(root/'action_studio/playback.py').read_text(encoding='utf-8')
        editor=(root/'action_studio/ui.py').read_text(encoding='utf-8')
        recorder=(root/'action_studio/recorder.py').read_text(encoding='utf-8')
        self.assertIn('self._map_to_current_window(action)',player)
        self.assertIn('self._wait_for_visual_idle()',player)
        self.assertIn('self.project.recorded_window_bounds=',editor)
        self.assertIn('self.auto_wait_toggle',editor)
        self.assertIn('self.recorded_window_bounds = list(window_rect(target))',recorder)


if __name__=='__main__':
    unittest.main()
