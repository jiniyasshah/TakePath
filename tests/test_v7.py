"""V7 model and regression checks; no Windows input hooks necessary."""
import json
import tempfile
import unittest
from pathlib import Path
from action_studio.core import ActionBuilder, Action, Project, save_project, load_project, MODES, GLOBAL_TYPING_MODES
from action_studio.targets import open_windows, screen_entries

ROOT=Path(__file__).resolve().parents[1]

class VersionSevenTests(unittest.TestCase):
    def test_global_replay_presets_roundtrip(self):
        for mouse in sorted(MODES):
            for typing in sorted(GLOBAL_TYPING_MODES):
                p=Project(cursor_mode=mouse,global_typing_mode=typing,
                          actions=[Action(kind='type',text='Fixed',char_timings=[0,.1,.25,.3,.52])])
                restored=Project.from_dict(p.to_dict())
                self.assertEqual(restored.cursor_mode,mouse)
                self.assertEqual(restored.global_typing_mode,typing)
                self.assertEqual(restored.actions[0].char_timings,[0,.1,.25,.3,.52])

    def test_legacy_project_defaults_to_smooth_typing(self):
        data=Project().to_dict()
        data.pop('global_typing_mode')
        self.assertEqual(Project.from_dict(data).global_typing_mode,'smooth')
        data['global_typing_mode']='evil'
        self.assertEqual(Project.from_dict(data).global_typing_mode,'smooth')

    def test_original_typing_captures_and_edits_group(self):
        b=ActionBuilder()
        for stamp,c in [(1,'H'),(1.18,'e'),(1.38,'l'),(1.6,'l'),(1.8,'x')]:
            b.char(c,stamp)
        b.backspace(2.0)
        b.char('o',2.2)
        actions=b.finish()
        self.assertEqual(len(actions),1)
        self.assertEqual(actions[0].text,'Hello')
        self.assertEqual(len(actions[0].char_timings),5)
        self.assertAlmostEqual(actions[0].char_timings[-1],1.2)

    def test_secure_fields_never_keep_timing_fingerprint(self):
        obj=Action(kind='secure_input',text='password',char_timings=[0,.2,.5]).__dict__.copy()
        item=Action.from_dict(obj)
        self.assertEqual(item.char_timings,[])
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'test.vas.json'
            save_project(Project(actions=[item]),target)
            content=target.read_text()
            self.assertNotIn('password',content)
            self.assertEqual(load_project(target).actions[0].char_timings,[])

    def test_screen_menu_labels_and_window_filter_nonwindows(self):
        self.assertIsInstance(open_windows(), list)
        class Rect:
            def x(self):return -1920
            def y(self):return 0
            def width(self):return 1920
            def height(self):return 1080
        class Screen:
            def geometry(self):return Rect()
        # Linux fallback; on Windows native monitor API takes precedence.
        from sys import platform
        if platform!='win32':
            entries=screen_entries([Screen()])
            self.assertTrue(entries)
            self.assertTrue(entries[0][0].startswith('Screen 1'))
            self.assertEqual(len(entries[0][1]),4)

    def test_editor_layout_and_actual_targets(self):
        ui=(ROOT/'action_studio/ui.py').read_text()
        self.assertIn("self.target_chevron.setPixmap(vector_icon('chevron'",ui)
        self.assertIn('open_windows()',ui)
        self.assertIn("menu.addSection('SCREENS')",ui)
        self.assertIn("menu.addSection('APPLICATIONS')",ui)  # V8 simplifies picker label
        self.assertIn('main_row.addWidget(inspector)',ui)
        self.assertIn("self.preview_mode='hidden'",ui)
        self.assertIn("self.global_typing.addItems(['Original','Smooth','Instant'])",ui)
        playback=(ROOT/'action_studio/playback.py').read_text()
        for name in ('_straight_move','_gentle_move','_original_move','_recorded_type'):
            self.assertIn(f'def {name}',playback)

if __name__=='__main__': unittest.main()
