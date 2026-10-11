"""Source and behavior regressions for the V10.2 polish pass (Qt-independent)."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / 'action_studio' / 'ui.py').read_text(encoding='utf-8')


def method(name):
    return UI.split(f'    def {name}(',1)[1].split('\n    def ',1)[0]


class V102Polish(unittest.TestCase):
    def test_python_ui_code_is_syntactically_valid(self):
        ast.parse(UI)

    def test_finished_replay_stays_in_play_and_retake_mode(self):
        done = method('_play_thread_done')
        self.assertIn('self.replay_ready=bool(self.project.actions)', done)
        self.assertIn('self.playback_completed=success', done)
        self.assertNotIn('self.replay_ready=not success', done)
        self.assertNotIn('self.show_editor()', done)
        sync = method('sync')
        self.assertIn('self.primary_stack.setCurrentIndex(1 if ready else 0)', sync)
        self.assertIn('self.retake_button.setVisible(bool(self.owner.project.actions) and not busy)', sync)
        self.assertIn('self.owner.replay_ready and not busy', sync)

    def test_password_reveals_are_explicit_only(self):
        helper = UI.split('def password_reveal_button(',1)[1].split('\ndef ',1)[0]
        self.assertIn('button.setCheckable(True)',helper)
        self.assertIn('QLineEdit.Normal if visible else QLineEdit.Password',helper)
        self.assertIn('update(False)',helper)
        self.assertIn("button.setAccessibleName('Hide password' if visible else 'Show password')",helper)
        self.assertIn('password_reveal_button(edit)',UI)
        self.assertIn('self.secret_reveal=password_reveal_button(self.secret_edit)',UI)

    def test_stored_secret_requires_explicit_review(self):
        selected = method('selection_changed')
        self.assertIn('self.secret_edit.clear()',selected)
        self.assertIn('self.secret_reveal.setChecked(False)',selected)
        review = method('review_secure_value')
        self.assertIn('self._read_saved_secret(a)',review)
        self.assertIn('self.credential_store.get(ref)',method('_read_saved_secret'))
        self.assertIn('self.session_secrets.get(key)',review)
        self.assertIn('self.secret_edit.setText(secret)',review)
        self.assertIn('self.secret_reveal.setChecked(False)',review)
        self.assertIn('self.secret_edit.clear()',method('set_secure_value'))

    def test_prompts_are_centered_and_foregrounded(self):
        center = UI.split('def _center_dialog_on_screen(',1)[1].split('\ndef ',1)[0]
        self.assertIn('screen.availableGeometry()',center)
        self.assertIn('dialog.move(x,y)',center)
        foreground = UI.split('def _foreground_dialog(',1)[1].split('\ndef ',1)[0]
        self.assertIn('Qt.WindowStaysOnTopHint',foreground)
        self.assertIn('_center_dialog_on_screen(dialog)',foreground)
        self.assertIn('QTimer.singleShot(0, bring_forward)',foreground)
        self.assertIn('QTimer.singleShot(120, bring_forward)',foreground)
        self.assertIn('_ask_in_front(self._visible_dialog_parent()',method('_discard_ok'))
        self.assertIn('_foreground_dialog(dlg).exec()',method('_prepare_secure_values'))


if __name__ == '__main__':
    unittest.main()
