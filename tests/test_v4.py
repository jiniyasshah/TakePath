"""Version 4 regression tests: side buttons, editor priority and navigation."""
import unittest
from pathlib import Path
from action_studio.core import Action, Project, ActionBuilder


class VersionFourTests(unittest.TestCase):
    def test_side_button_roundtrip(self):
        project=Project(actions=[Action(kind='click',button='x1',x=321,y=450),
                                 Action(kind='click',button='x2',x=700,y=800)])
        restored=Project.from_dict(project.to_dict())
        self.assertEqual([a.button for a in restored.actions],['x1','x2'])
        self.assertIn('Back click',restored.actions[0].label())
        self.assertIn('Forward click',restored.actions[1].label())

    def test_side_button_events_are_editable_actions(self):
        b=ActionBuilder()
        b.mouse_down(120,190,1.0)
        b.mouse_up(120,190,'x1',1.1)
        b.mouse_down(144,200,1.3)
        b.mouse_up(144,200,'x2',1.36)
        a=b.finish()
        self.assertEqual([(v.kind,v.button) for v in a],[('click','x1'),('click','x2')])

    def test_side_button_validation_is_strict(self):
        action=Action(kind='click',button='x2000')
        self.assertEqual(Action.from_dict(vars(action)).button,'left')

    def test_editor_new_capture_only_returns_to_dock(self):
        src=(Path(__file__).resolve().parents[1]/'action_studio'/'ui.py').read_text(encoding="utf-8")
        self.assertIn("B('New capture',self.prepare_new_capture",src)
        action=src.split('    def prepare_new_capture(self):',1)[1].split('    def start_recording(self):',1)[0]
        self.assertIn('self.show_dock()',action)
        self.assertNotIn("self._arm('record')",action)

    def test_player_completion_does_not_open_editor(self):
        src=(Path(__file__).resolve().parents[1]/'action_studio'/'ui.py').read_text(encoding="utf-8")
        completion=src.split('    def _play_thread_done(self):',1)[1].split('    def _record_pause_status(self,paused):',1)[0]
        self.assertIn('self.playback_completed=success',completion)
        self.assertNotIn('show_editor',completion)
        self.assertIn('Open editor',src)

    def test_optional_preview_presets_and_default_priority(self):
        src=(Path(__file__).resolve().parents[1]/'action_studio'/'ui.py').read_text(encoding="utf-8")
        self.assertIn("self.preview_mode='hidden'",src)
        self.assertIn("('hidden','Hide map')",src)
        self.assertIn("('expanded','Large map')",src)
        self.assertIn('body.setSizes([150,700])',src)

    def test_side_button_win32_playback_is_supported(self):
        src=(Path(__file__).resolve().parents[1]/'action_studio'/'playback.py').read_text(encoding="utf-8")
        self.assertIn('def send_side_button(',src)
        self.assertIn('0x0080 if pressed else 0x0100',src)
        self.assertIn("if a.button in ('x1','x2'):",src)

    def test_dock_top_center_default(self):
        src=(Path(__file__).resolve().parents[1]/'action_studio'/'ui.py').read_text(encoding="utf-8")
        self.assertIn("'dock_location','top'",src)
        self.assertIn("screen.top()+margin",src)
        self.assertIn('class RecordOrb(QPushButton):',src)
        self.assertIn('painter.drawEllipse(QRectF(17.0, 17.0, 14.0, 14.0))',src)

if __name__=='__main__':
    unittest.main()
