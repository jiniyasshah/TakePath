"""V9 UI regressions; pure-Python source checks don't require Windows/Qt."""
import ast
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/'action_studio'/'ui.py').read_text(encoding='utf-8')

class FinalPolishV9Tests(unittest.TestCase):
    def test_no_header_edit_status(self):
        self.assertNotIn('READY TO EDIT',UI)
        self.assertNotIn('self.capture_badge',UI)
        self.assertIn("hb.addWidget(B('Save',self.save,'outline'",UI)
        self.assertIn("hb.addWidget(B('▶  Replay',self.prepare_replay,'primary'",UI)

    def test_gap_has_visible_text_and_separate_seconds_unit(self):
        tree=ast.parse(UI)
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='GapInput')
        methods={n.name for n in cls.body if isinstance(n,ast.FunctionDef)}
        for name in ('setValue','value','_commit','nudge'):
            self.assertIn(name,methods)
        self.assertIn("self.field.setText(f'{self._value:.2f}')",UI)
        self.assertIn("unit=L('s','gapUnit')",UI)
        self.assertIn('QDoubleValidator(self._minimum,self._maximum,2,self.field)',UI)
        self.assertIn('self.uniform=GapInput(value=0.80, minimum=0, maximum=3600, step=0.10)',UI)
        self.assertIn('QLineEdit#gapText',UI)
        self.assertNotIn('self.uniform.setButtonSymbols(QDoubleSpinBox.NoButtons)',UI)

    def test_gap_rejects_unusable_values_and_keeps_keyboard_controls(self):
        self.assertIn('if not self._minimum <= raw <= self._maximum:',UI)
        self.assertIn('except (TypeError,ValueError):',UI)
        self.assertIn('self.field.editingFinished.connect(self._commit)',UI)
        self.assertIn('Qt.Key_Up, Qt.Key_Down',UI)
        self.assertIn('self.hasFocus()',UI)

    def test_darker_surfaces_and_consistent_labels(self):
        for literal in ('QWidget { background: #0B0D12;',
                        'QFrame#dockBody { background: #12141C;',
                        'QFrame#topBar { background: #10131A;',
                        'QFrame#replayToolbar { background: #151A24;',
                        'QLabel { background: transparent; }'):
            self.assertIn(literal,UI)
        self.assertIn("self.setWindowTitle(f'TakePath {__version__}')",UI)

    def test_existing_actions_and_replay_still_connected(self):
        for literal in ('self.uniform_all','self.set_cursor_mode(v.lower())',
                        'self.set_typing_mode(v.lower())','self.prepare_replay',
                        "self.play_center.isChecked()",'owner.start_recording',
                        'owner.start_playback'):
            self.assertIn(literal,UI)

if __name__=='__main__':
    unittest.main()
