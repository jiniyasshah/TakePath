"""Release-blocker regression tests for V10.1 (Windows GUI not required)."""
import unittest
from pathlib import Path
from action_studio.core import anchor_original_path
from action_studio.win_focus import activate_target_window

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/'action_studio'/'ui.py').read_text('utf-8')
PLAYER=(ROOT/'action_studio'/'playback.py').read_text('utf-8')

class FakeUser32:
    def __init__(self, foreground=8, minimized=False):
        self.foreground=foreground
        self.minimized=minimized
        self.shown=[]
        self.focused=[]
    def IsWindow(self, hwnd):return hwnd>0
    def IsIconic(self, hwnd):return self.minimized
    def ShowWindow(self, hwnd,how):
        self.shown.append((hwnd,how));self.minimized=False
    def GetForegroundWindow(self):return self.foreground
    def SetForegroundWindow(self,hwnd):self.focused.append(hwnd);self.foreground=hwnd

class ReleaseBlockers(unittest.TestCase):
    def test_maximized_target_is_never_unmaximized(self):
        api=FakeUser32(foreground=1,minimized=False)
        self.assertTrue(activate_target_window(8,api,timeout=0))
        self.assertEqual(api.shown,[])
        self.assertEqual(api.focused,[8])

    def test_minimized_target_is_restored_before_focus(self):
        api=FakeUser32(foreground=1,minimized=True)
        self.assertTrue(activate_target_window(8,api,timeout=0))
        self.assertEqual(api.shown,[(8,9)])

    def test_invalid_window_is_not_activated(self):
        api=FakeUser32()
        self.assertFalse(activate_target_window(0,api))
        self.assertEqual(api.shown,[])

    def test_original_mouse_path_no_longer_starts_at_old_dock_coordinates(self):
        path=[[450,990,0],[475,840,.25],[550,500,.5]]
        converted=list(anchor_original_path(path,(600,350)))
        self.assertEqual(converted[-1][:2],(550,500))
        self.assertEqual(converted[0][:2],(550,520))
        self.assertNotEqual(converted[0][:2],tuple(path[0][:2]))
        self.assertIn('anchor_original_path(path, (initial.x, initial.y))',PLAYER)

    def test_replay_does_not_unconditionally_restore_windows(self):
        pending=UI.split('    def _begin_pending(self):',1)[1].split('    def retake(self):',1)[0]
        self.assertNotIn('ShowWindow(hwnd,9)',pending)
        self.assertIn('platform_activate(hwnd)',pending)

    def test_hidden_editor_dialogs_have_visible_dock_parent(self):
        discard=UI.split('    def _discard_ok(self):',1)[1].split('    def new_project(self):',1)[0]
        self.assertIn('_ask_in_front(self._visible_dialog_parent()',discard)
        secure=UI.split('    def _prepare_secure_values(self):',1)[1].split('    def start_playback(self):',1)[0]
        self.assertIn('_foreground_dialog(dlg).exec()',secure)
        self.assertIn('Qt.WindowStaysOnTopHint',UI)

    def test_playback_failure_is_reported_and_dock_remains_ready(self):
        done=UI.split('    def _play_thread_done(self):',1)[1].split('    def _record_pause_status(self,paused):',1)[0]
        self.assertIn('self.replay_ready=bool(self.project.actions)',done)
        self.assertIn("_warn_in_front(self.dock,'Replay stopped',details)",done)
        self.assertNotIn('self.show_editor()',done)

if __name__=='__main__':unittest.main()
