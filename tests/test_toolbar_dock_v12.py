"""Pure regression checks for replay step markers and editor toolbar events."""
import unittest
from pathlib import Path
from action_studio.core import Action, format_replay_step

ROOT=Path(__file__).resolve().parents[1]


class DockStepTests(unittest.TestCase):
    def test_wait_and_click_show_original_step_numbers(self):
        self.assertEqual(format_replay_step(Action(kind='wait',delay=3,wait_mode='duration'),7,36),
                         'STEP 008/036 · WAIT 3.0s')
        self.assertEqual(format_replay_step(Action(kind='click',x=1612,y=694),8,36),
                         'STEP 009/036 · CLICK 1612, 694')

    def test_condition_wait_has_no_parameter_leak(self):
        action=Action(kind='wait',wait_mode='target_title',wait_value='Sensitive dashboard')
        message=format_replay_step(action,2,20)
        self.assertIn('WAIT · CONDITION',message)
        self.assertNotIn('Sensitive',message)

    def test_secure_or_typed_text_not_displayed_on_recording_overlay(self):
        for action in [
            Action(kind='type',text='my-private-password'),
            Action(kind='secure_input',text='my-private-password',secure_ref='opaque-secret'),
        ]:
            label=format_replay_step(action,0,2)
            self.assertNotIn('my-private-password',label)
            self.assertNotIn('opaque-secret',label)
        self.assertEqual(format_replay_step(Action(kind='type',text='alice'),1,3),
                         'STEP 002/003 · TYPE (5 chars)')

    def test_editor_has_toolbar_hit_testing_and_dock_progress(self):
        source=(ROOT/'action_studio'/'ui.py').read_text(encoding='utf-8')
        self.assertIn('def _editor_control_hit(self, obj, event):',source)
        self.assertIn('self._click_within(obj, self.toolbar_scroll, event)',source)
        self.assertIn('if not self._editor_control_hit(obj, event):',source)
        self.assertIn('self.step_status.setVisible(playing)',source)
        self.assertIn('summary=format_replay_step(',source)
        self.assertIn('self.dock.sync()\n\n    def _adaptive_wait_status',source)


if __name__=='__main__':
    unittest.main()
