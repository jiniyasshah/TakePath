"""V5: protected field privacy + dock-driven replay staging regressions."""
import unittest
from pathlib import Path
from action_studio.core import Action, ActionBuilder, Project

UI=(Path(__file__).resolve().parents[1]/'action_studio'/'ui.py')
REC=(Path(__file__).resolve().parents[1]/'action_studio'/'recorder.py')
PLAYER=(Path(__file__).resolve().parents[1]/'action_studio'/'playback.py')

class VersionFiveTests(unittest.TestCase):
    def test_protected_input_does_not_store_raw_keys(self):
        b=ActionBuilder()
        b.mouse_down(100,100,1)
        b.mouse_up(100,100,'left',1.07)
        b.protected_input(1.1)
        b.protected_input(1.2)
        b.protected_input(1.4)
        actions=b.finish()
        self.assertEqual([a.kind for a in actions],['click','secure_input'])
        self.assertEqual(actions[-1].text,'')

    def test_contiguous_protected_sessions_are_grouped(self):
        b=ActionBuilder()
        b.protected_input(.5)
        b.protected_input(.6)
        b.leave_protected_input()
        b.protected_input(2)
        self.assertEqual([a.kind for a in b.finish()],['secure_input','secure_input'])

    def test_protected_marker_never_serializes_plaintext(self):
        project=Project(actions=[Action(kind='secure_input',text='do-not-persist',key='secret',delay=2.0)])
        stored=project.to_dict()
        self.assertEqual(stored['actions'][0]['text'],'')
        self.assertEqual(stored['actions'][0]['key'],'enter')
        loaded=Project.from_dict({**stored,'actions':[{**stored['actions'][0],'text':'mischievous-secret','key':'secret'}]})
        self.assertEqual(loaded.actions[0].text,'')
        self.assertEqual(loaded.actions[0].key,'enter')
        self.assertEqual(loaded.actions[0].kind,'secure_input')
        self.assertIn('Protected input',loaded.actions[0].label())

    def test_records_password_marker_without_secret(self):
        src=REC.read_text()
        self.assertIn('focus_status()',src)
        backend=(Path(__file__).resolve().parents[1]/'action_studio/platform_api.py').read_text(encoding='utf-8')
        self.assertIn("'protected' if bool(ctrl.IsPassword)",backend)
        self.assertIn('self.builder.protected_input(self._stamp())',src)
        self.assertIn('if focus_status != "safe":',src)
        self.assertNotIn('self.builder.char(char, self._stamp())',src)

    def test_editor_replay_is_staged(self):
        src=UI.read_text()
        self.assertIn("B('▶  Replay',self.prepare_replay",src)
        prepare=src.split('    def prepare_replay(self):',1)[1].split('    def start_playback(self):',1)[0]
        self.assertIn('self.replay_ready=True',prepare)
        self.assertIn('self.show_dock()',prepare)
        self.assertNotIn("self._arm('play')",prepare)
        start=src.split('    def start_playback(self):',1)[1].split('    def _launch_playback(self,hwnd):',1)[0]
        self.assertIn('not self.replay_ready',start)
        self.assertIn("self._arm('play')",start)
        self.assertIn('self.replay.clicked.connect(owner.start_playback)',src)
        self.assertIn('self.primary_stack.setCurrentIndex(1 if ready else 0)',src)

    def test_player_pauses_at_protected_marker(self):
        src=PLAYER.read_text()
        block=src.split('    def _protected_input(self):',1)[1].split('    def _action(self, a: Action):',1)[0]
        self.assertIn('self.pause_flag.set()',block)
        self.assertIn('self.secure_input_requested.emit()',block)
        self.assertIn('while self.pause_flag.is_set():',block)
        self.assertIn('self._guard()',block)

    def test_new_capture_exits_replay_ready(self):
        src=UI.read_text()
        prepare=src.split('    def prepare_new_capture(self):',1)[1].split('    def start_recording(self):',1)[0]
        self.assertIn('self.replay_ready=False',prepare)
        self.assertIn('self.show_dock()',prepare)

if __name__=='__main__':
    unittest.main()
