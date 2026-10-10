"""V8 picker and action-toolbar regressions (pure Python, Windows UI tests pending)."""
import unittest
from pathlib import Path
from action_studio.targets import (
    TargetWindow, is_capture_candidate, friendly_app_name, window_menu_label,
    unique_application_windows,
)

ROOT=Path(__file__).resolve().parents[1]


class PickerV8Tests(unittest.TestCase):
    def test_discard_non_application_shell_windows(self):
        self.assertFalse(is_capture_candidate('Program Manager','Progman','explorer.exe'))
        self.assertFalse(is_capture_candidate('Background','WorkerW','explorer.exe'))
        self.assertFalse(is_capture_candidate('Windows Input Experience','Any','textinputhost.exe'))
        self.assertFalse(is_capture_candidate('Windows Input Experience','ApplicationFrameWindow',''))

    def test_discard_background_overlay_windows(self):
        kw={'title':'Notes', 'class_name':'Notepad', 'process_name':'notepad.exe'}
        for property_name in ('visible','cloaked','tool_window','no_activate','owned'):
            params={property_name:False if property_name=='visible' else True}
            self.assertFalse(is_capture_candidate(**kw,**params),property_name)
        self.assertFalse(is_capture_candidate(**kw,width=20,height=500))
        self.assertFalse(is_capture_candidate(**kw,width=500,height=30))

    def test_preserve_useful_application_windows(self):
        for title,klass,binary in [
            ('A page - Brave','Chrome_WidgetWin_1','brave.exe'),
            ('Settings','ApplicationFrameWindow','applicationframehost.exe'),
            ('Demo.py - Visual Studio Code','Chrome_WidgetWin_1','Code.exe'),
            ('Untitled - Notepad','Notepad','notepad.exe')]:
            self.assertTrue(is_capture_candidate(title,klass,binary),title)

    def test_deduplicate_app_shell_mirrors_without_removing_different_pages(self):
        windows=[
            TargetWindow(1,'Settings',100,'C:/Windows/SystemSettings.exe','Settings'),
            TargetWindow(2,'Settings',101,'C:/Windows/ApplicationFrameHost.exe','Windows App'),
            TargetWindow(3,'First page - Brave',200,'C:/Brave/brave.exe','Brave Browser'),
            TargetWindow(4,'Second page - Brave',200,'C:/Brave/brave.exe','Brave Browser'),
            TargetWindow(5,'First page - Brave',200,'C:/Brave/brave.exe','Brave Browser'),
            TargetWindow(6,'Realtek Audio Console',300,'C:/Realtek/rtk.exe','Realtek Audio Console'),
            TargetWindow(7,'Realtek Audio Console',301,'C:/Realtek/ui.exe','Realtek Audio Console'),
        ]
        self.assertEqual([w.hwnd for w in unique_application_windows(windows)],[1,3,4,6])

    def test_window_labels_and_real_executable_names(self):
        self.assertEqual(friendly_app_name('C:\\Program Files\\Brave\\brave.exe','Tab'), 'Brave Browser')
        window=TargetWindow(1,'Create Action Recorder - Brave',10,'C:/brave.exe','Brave Browser')
        self.assertIn('Create Action Recorder',window_menu_label(window))
        self.assertEqual(window_menu_label(TargetWindow(1,'Settings',1,'C:/SystemSettings.exe','Settings')),'Settings')


class ToolbarV8Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui=(ROOT/'action_studio/ui.py').read_text(encoding='utf-8')
        cls.targets=(ROOT/'action_studio/targets.py').read_text(encoding='utf-8')

    def test_grouped_toolbar_no_black_box_label_blocks(self):
        for literal in ("toolbar_group('TIMING  ·  GAP')", "toolbar_group('MOUSE PATH')",
                        "toolbar_group('TYPING STYLE')", "toolbar_group('CURSOR START')",
                        "toolbar_group('PLAYBACK SPEED')", "toolbar_group('ESTIMATED REPLAY')"):
            self.assertIn(literal,self.ui)
        self.assertNotIn("commands.addWidget(L('GLOBAL CURSOR','tiny'))",self.ui)
        self.assertIn("QFrame#replayToolbar",self.ui)
        self.assertIn("self.play_center.setCheckable(True)",self.ui)

    def test_footer_scrolls_only_when_narrow(self):
        self.assertIn("self.toolbar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)",self.ui)
        self.assertIn("self.toolbar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)",self.ui)
        self.assertIn("self.toolbar_scroll.setWidgetResizable(True)",self.ui)

    def test_global_playback_controls_still_wired(self):
        self.assertIn('self.uniform_all',self.ui)
        self.assertIn('self.set_cursor_mode(v.lower())',self.ui)
        self.assertIn('self.set_typing_mode(v.lower())',self.ui)
        self.assertIn("self.speed.currentTextChanged.connect(lambda _value:self._metrics())",self.ui)
        self.assertIn("self.play_center.isChecked()",self.ui)

    def test_picker_uses_native_icons_and_detected_process_names(self):
        self.assertIn('QFileIconProvider()',self.ui)
        self.assertIn('window_menu_label(item)',self.ui)
        self.assertIn('DwmGetWindowAttribute',self.targets)
        self.assertIn('GetClassNameW',self.targets)
        self.assertIn('QueryFullProcessImageNameW',self.targets)

if __name__=='__main__':unittest.main()
