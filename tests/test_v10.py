"""V10 retake recovery & packaging regressions (Windows GUI not required)."""
import tempfile
import unittest
from pathlib import Path
from action_studio.core import Project, Action
from action_studio.retakes import RetakeHistory

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/'action_studio'/'ui.py').read_text(encoding='utf-8')

class V10Tests(unittest.TestCase):
    def test_retake_history_is_copy_not_alias(self):
        old=Project(actions=[Action(kind='type',text='Original text')])
        history=RetakeHistory()
        history.capture(old,Path('old.vas.json'),True,{'key':'session-secret'})
        old.actions[0].text='Changed during next take'
        self.assertEqual(history.restore().project.actions[0].text,'Original text')
        self.assertFalse(history.available)

    def test_retake_history_undo_restores_metadata_in_memory(self):
        previous=Project(actions=[Action(kind='click',x=55,y=66)])
        h=RetakeHistory();h.capture(previous,Path('first.vas.json'),False,{})
        item=h.restore()
        self.assertEqual(item.path,Path('first.vas.json'))
        self.assertFalse(item.dirty)
        self.assertEqual(item.project.actions[0].x,55)

    def test_no_automatic_disk_writes_or_password_serialization(self):
        self.assertNotIn('save_project', (ROOT/'action_studio'/'retakes.py').read_text(encoding="utf-8"))
        project=Project(actions=[Action(kind='secure_input',text='example-secret')])
        history=RetakeHistory();history.capture(project,None,True,{'ref':'example-secret'})
        self.assertNotIn('example-secret',str(history.restore().project.to_dict()))

    def test_dock_retakes_and_restore(self):
        self.assertIn("owner.retake,'Retake: record again",UI)
        self.assertIn("owner.retake,'Discard this take",UI)
        self.assertIn("menu.addAction('Restore previous take'",UI)
        retake=UI.split('    def retake(self):',1)[1].split('    def restore_previous_take(self):',1)[0]
        self.assertIn("self._arm('record')",retake)
        self.assertIn('self.recorder.stop()',retake)
        record=UI.split('    def _recording_done(self,actions,target_title,bounds):',1)[1].split('    def _complete_recording(self):',1)[0]
        self.assertIn('self.take_history.capture',record)
        self.assertIn('self.project_path=None',record)
        self.assertIn('if self.restart_recording:',record)
        self.assertIn('if not actions and self.retake_pending:',record)

    def test_retake_is_disabled_during_replay(self):
        self.assertIn('self.active_retake.setVisible(recording)',UI)
        self.assertIn('self.retake_button.setVisible(bool(self.owner.project.actions) and not busy)',UI)
        self.assertIn("self.replay.clicked.connect(owner.start_playback)",UI)

    def test_brand_and_installer_assets(self):
        self.assertTrue((ROOT/'assets'/'takepath.ico').is_file())
        self.assertTrue((ROOT/'assets'/'takepath-icon.png').is_file())
        build=(ROOT/'build_windows_exe.bat').read_text(encoding="utf-8")
        self.assertIn('--icon "assets\\takepath.ico"',build)
        self.assertIn('--add-data "assets;assets"',build)
        self.assertIn("brandbox.addWidget(L('TakePath','brand'))",UI)
        self.assertIn('QSystemTrayIcon(app_icon(),self)',UI)

if __name__=='__main__':unittest.main()
