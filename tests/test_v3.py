"""V3 project interoperability and intentional minimal control separation."""
from pathlib import Path
import tempfile
import unittest
from action_studio.core import Action, Project, load_project, save_project


class VersionThreeTests(unittest.TestCase):
    def test_screen_scope_roundtrip(self):
        project = Project(target_mode='screen', actions=[Action(kind='type', text='A corrected title')])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'screen.vas.json'
            save_project(project,path)
            restored=load_project(path)
            self.assertEqual(restored.target_mode,'screen')
            self.assertEqual(restored.actions[0].text,'A corrected title')

    def test_old_v2_project_defaults_to_window(self):
        data=Project().to_dict()
        data.pop('target_mode')
        self.assertEqual(Project.from_dict(data).target_mode,'window')

    def test_invalid_scope_fails_safe(self):
        data=Project().to_dict()
        data['target_mode']='secret-other-app'
        self.assertEqual(Project.from_dict(data).target_mode,'window')

    def test_v3_hides_advanced_controls_from_dock(self):
        source=(Path(__file__).resolve().parents[1]/'action_studio'/'ui.py').read_text(encoding='utf-8')
        dock=source.split('class ControlDock(QWidget):',1)[1].split('class MainWindow(',1)[0]
        editor=source.split('class MainWindow(',1)[1]
        self.assertNotIn('record_limit',dock)
        self.assertNotIn('play_limit',dock)
        self.assertNotIn('set_cursor_mode(',dock)
        self.assertIn('self.global_mode=QComboBox()',editor)  # V8 uses an unboxed MOUSE PATH label
        self.assertIn('Apply to selected',editor)
        self.assertIn("self.play_center=QPushButton('Center cursor')",editor)  # compact V8 toggle


if __name__=='__main__': unittest.main()
