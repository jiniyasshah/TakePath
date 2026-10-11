"""Regression coverage: fixed-duration waits and editor insertion/selection behavior.

The timer must not depend on a matching title, and an old project whose
title-based Wait has no value must remain usable after loading.
"""
import unittest
from pathlib import Path
from action_studio.core import Action, Project, WAIT_MODES


ROOT = Path(__file__).resolve().parents[1]


class FixedWaitTests(unittest.TestCase):
    def test_new_wait_default_is_fixed_duration(self):
        a = Action(kind="wait", delay=3.0)
        self.assertIn("duration", WAIT_MODES)
        self.assertEqual(a.wait_mode, "duration")
        self.assertIn("3.00 s", a.label())

    def test_beta2_blank_title_wait_becomes_three_second_pause(self):
        old = {
            "kind": "wait", "delay": 3.0, "wait_mode": "target_title",
            "wait_value": "", "wait_timeout": 15.0,
        }
        action = Action.from_dict(old)
        self.assertEqual(action.wait_mode, "duration")
        self.assertEqual(action.delay, 3.0)
        self.assertEqual(action.label(), "Pause for 3.00 s")

    def test_legacy_wait_roundtrip_keeps_delay_and_fixed_mode(self):
        p = Project(actions=[
            Action.from_dict({"kind": "wait", "delay": 3.0,
                              "wait_mode": "target_title", "wait_value": ""})
        ])
        saved = Project.from_dict(p.to_dict())
        self.assertEqual(saved.actions[0].wait_mode, "duration")
        self.assertEqual(saved.actions[0].delay, 3)

    def test_valid_title_wait_keeps_condition(self):
        a = Action.from_dict({"kind": "wait", "wait_mode": "target_title",
                              "wait_value": "Settings", "wait_timeout": 8})
        self.assertEqual(a.wait_mode, "target_title")
        self.assertEqual(a.wait_value, "Settings")
        self.assertEqual(a.wait_timeout, 8)

    def test_other_wait_conditions_remain_supported(self):
        for mode in ("active_title", "focused_safe", "focused_protected", "control_name"):
            with self.subTest(mode=mode):
                a = Action.from_dict({"kind": "wait", "wait_mode": mode,
                                      "wait_value": "test"})
                self.assertEqual(a.wait_mode, mode)

    def test_playback_duration_path_has_one_wall_clock_wait(self):
        src = (ROOT / "action_studio" / "playback.py").read_text(encoding="utf-8")
        self.assertIn('if a.kind == "wait" and a.wait_mode == "duration":', src)
        self.assertIn("self._wait(a.delay, recover_focus=True)", src)
        self.assertIn('if a.wait_mode == "duration":', src)
        self.assertIn("self._run_wait_action(a)", src)
        self.assertIn("wait_until_ready(", src)

    def test_editor_exposes_insert_before_and_fixed_duration_controls(self):
        src = (ROOT / "action_studio" / "ui.py").read_text(encoding="utf-8")
        self.assertIn("Pause for a fixed duration", src)
        self.assertIn("self.delay_caption.setText('WAIT DURATION'", src)
        self.assertIn("def add_action(self, before=False):", src)
        self.assertIn("pos=(min(rows) if rows else 0) if before else", src)
        self.assertIn("self.before_action_button", src)
        self.assertIn("a.delay=3.0", src)

    def test_editor_click_away_preserves_inspector_and_command_actions(self):
        src = (ROOT / "action_studio" / "ui.py").read_text(encoding="utf-8")
        self.assertIn("QApplication.instance().installEventFilter(self)", src)
        self.assertIn("def clear_action_selection(self):", src)
        self.assertIn("def eventFilter(self, obj, event):", src)
        self.assertIn("self.inspector_panel, self.add_action_button", src)
        self.assertIn("self._inside_widget(obj, viewport)", src)
        self.assertIn("self.owner.clear_action_selection()", src)


if __name__ == "__main__":
    unittest.main()
