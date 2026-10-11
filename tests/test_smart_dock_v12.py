"""Smart Click-Through Dock regressions (Windows recording and replay)."""
import unittest
from unittest.mock import patch

from action_studio.recorder import Recorder
from action_studio.core import ActionBuilder


class RecorderOverlayFilteringTests(unittest.TestCase):
    def setUp(self):
        self.rec=Recorder()
        self.rec.active=True
        self.rec.builder=ActionBuilder()
        self.rec.started_at=0.0
        self.rec.own_hwnd=1234
        self.rec.dock_bounds=(0,0,846,84)
        self.rec._inside=lambda:True
        self.rec.set_interactive_bounds((650,10,196,64))

    def test_passive_dock_area_is_recordable(self):
        # URL bar behind the former full-width 846px dock is no longer
        # swallowed by _inside_at; only the small controller is excluded.
        with patch('action_studio.recorder.sys.platform','win32'):
            self.assertTrue(self.rec._inside_at(55,40))
            self.assertTrue(self.rec._inside_at(420,40))
            self.assertFalse(self.rec._inside_at(680,40))
            self.assertTrue(self.rec._inside_at(420,120))

    def test_interactive_controller_clicks_do_not_enter_project(self):
        with patch('action_studio.recorder.sys.platform','win32'):
            self.rec._click(680,35,'Button.left',True)
            self.rec._click(680,35,'Button.left',False)
        self.assertEqual(self.rec.builder.finish(),[])
        self.assertFalse(self.rec.excluded_buttons)

    def test_dragging_controller_beyond_bounds_is_never_recorded(self):
        with patch('action_studio.recorder.sys.platform','win32'):
            self.rec._click(680,35,'Button.left',True)
            self.assertIn('left',self.rec.excluded_buttons)
            self.rec._move(970,180)
            self.rec._click(970,180,'Button.left',False)
            self.rec._click(110,135,'Button.left',True)
            self.rec._click(110,135,'Button.left',False)
        actions=self.rec.builder.finish()
        self.assertEqual(len(actions),1)
        self.assertEqual(actions[0].kind,'click')
        self.assertEqual(actions[0].x,110)
        self.assertEqual(self.rec.excluded_buttons,set())

    def test_moving_island_updates_only_exclusion_rectangle(self):
        with patch('action_studio.recorder.sys.platform','win32'):
            self.rec.set_interactive_bounds((400,20,196,64))
            self.assertFalse(self.rec._inside_at(420,50))
            self.assertTrue(self.rec._inside_at(680,40))
            self.rec.set_interactive_bounds(None)
            self.assertTrue(self.rec._inside_at(420,50))
            self.assertTrue(self.rec._inside_at(680,40))

    def test_left_grip_is_excluded_but_adjacent_status_is_recordable(self):
        with patch('action_studio.recorder.sys.platform','win32'):
            self.rec.set_interactive_bounds((650,10,116,64),(10,20,34,42))
            self.assertFalse(self.rec._inside_at(22,38))
            self.assertTrue(self.rec._inside_at(55,38))
            self.assertTrue(self.rec._inside_at(420,38))
            self.assertFalse(self.rec._inside_at(680,38))
            self.rec._click(22,38,'Button.left',True)
            self.assertIn('left',self.rec.excluded_buttons)
            self.rec._move(400,150)
            self.rec._click(400,150,'Button.left',False)
            self.assertFalse(self.rec.excluded_buttons)
            self.assertEqual(self.rec.builder.finish(),[])
            self.rec.set_interactive_bounds(None)
            self.assertIsNone(self.rec.interactive_grip_bounds)
            self.assertTrue(self.rec._inside_at(22,38))

    def test_other_platforms_keep_legacy_dock_exclusion(self):
        with patch('action_studio.recorder.sys.platform','darwin'):
            self.assertFalse(self.rec._inside_at(420,50))
            self.assertTrue(self.rec._inside_at(900,50))


if __name__=='__main__':
    unittest.main()
