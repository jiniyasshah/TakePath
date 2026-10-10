"""V6: secrets must stay out of portable projects, with secure replay choices."""
import json
import tempfile
import unittest
from pathlib import Path
from action_studio.core import Action, Project, save_project, load_project
from action_studio.secure_store import valid_reference, validate_password

ROOT=Path(__file__).resolve().parents[1]


class SecureInputV6Tests(unittest.TestCase):
    def test_secure_behavior_roundtrip(self):
        ref='8b9efdf58d8b46cf96e6399603229a13'
        actions=[Action(kind='secure_input',secure_mode='auto',secure_ref=ref),
                 Action(kind='secure_input',secure_mode='manual'),
                 Action(kind='secure_input',secure_mode='skip')]
        result=Project.from_dict(Project(actions=actions).to_dict())
        self.assertEqual([a.secure_mode for a in result.actions],['auto','manual','skip'])
        self.assertEqual(result.actions[0].secure_ref,ref)
        self.assertTrue(all(not a.text for a in result.actions))

    def test_password_never_in_project_even_if_manually_injected(self):
        password='secret-SHOULD-NOT-APPEAR-7726'
        project=Project(actions=[Action(kind='secure_input',text=password,key=password,
                                       secure_mode='auto')])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.vas.json'
            save_project(project,path)
            self.assertNotIn(password,path.read_text())
            self.assertEqual(load_project(path).actions[0].text,'')
            self.assertEqual(load_project(path).actions[0].key,'enter')

    def test_untrusted_import_cannot_write_raw_password_in_secure_action(self):
        item=Action(kind='secure_input').__dict__.copy()
        item.update({'text':'leak-me','key':'leak-me','secure_mode':[],
                     'secure_ref':'../../hacked'})
        recovered=Action.from_dict(item)
        self.assertEqual(recovered.secure_mode,'auto')
        self.assertEqual(recovered.secure_ref,'')
        self.assertNotIn('leak-me',json.dumps(Project(actions=[recovered]).to_dict()))

    def test_v5_markers_default_to_automatic(self):
        raw=Action(kind='secure_input').__dict__.copy()
        raw.pop('secure_mode');raw.pop('secure_ref')
        restored=Action.from_dict(raw)
        self.assertEqual(restored.secure_mode,'auto')
        self.assertEqual(restored.secure_ref,'')

    def test_reference_validation_and_password_limits(self):
        self.assertTrue(valid_reference('a'*32))
        self.assertFalse(valid_reference('secret'))
        self.assertFalse(valid_reference('../'*11))
        with self.assertRaises(ValueError):validate_password('')
        with self.assertRaises(ValueError):validate_password('A'*513)
        self.assertEqual(validate_password('long and complex 🍉'),'long and complex 🍉')

    def test_editor_has_secure_input_modes_and_preflight(self):
        ui=(ROOT/'action_studio/ui.py').read_text()
        self.assertIn("addItem('Auto-fill', 'auto')",ui)
        self.assertIn("addItem('Manual in target app', 'manual')",ui)
        self.assertIn("addItem('Skip', 'skip')",ui)
        self.assertIn('def _prepare_secure_values(self):',ui)
        self.assertIn('if not self._prepare_secure_values():',ui)
        self.assertIn('secure_values=self.prepared_secure',ui)
        self.assertIn('Windows Credential Manager',ui)
        self.assertIn('Convert to secure input',ui)

    def test_only_explicit_manual_secure_steps_pause_player(self):
        playback=(ROOT/'action_studio/playback.py').read_text()
        self.assertIn("if a.secure_mode == 'manual':",playback)
        self.assertIn("elif a.secure_mode == 'auto':",playback)
        self.assertIn('self.secure_values.pop(a.id, None)',playback)
        self.assertIn("self._unicode_type(secret",playback)
        self.assertIn('self.secure_values.clear()',playback)


if __name__=='__main__': unittest.main()
