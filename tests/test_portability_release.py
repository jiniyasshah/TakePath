"""Release pipeline, safety gates, and portable asset smoke tests."""
import os
import sys
import unittest
from unittest import mock
from pathlib import Path
from PIL import Image
from action_studio import platform_api as api
from action_studio.secure_store import valid_reference, credential_store

ROOT = Path(__file__).resolve().parents[1]

class PortabilityTests(unittest.TestCase):
    def test_wayland_fails_closed(self):
        with mock.patch.object(sys, 'platform', 'linux'), mock.patch.dict(os.environ, {'XDG_SESSION_TYPE': 'wayland', 'DISPLAY': ':1'}):
            self.assertFalse(api.supported()[0])
            self.assertIn('Wayland', api.supported()[1])

    def test_x11_missing_display(self):
        env = dict(os.environ)
        env.pop('DISPLAY', None)
        env['XDG_SESSION_TYPE'] = 'x11'
        with mock.patch.object(sys, 'platform', 'linux'), mock.patch.dict(os.environ, env, clear=True):
            self.assertFalse(api.supported()[0])

    def test_credentials_never_accept_raw_strings_as_refs(self):
        self.assertFalse(valid_reference('my real password'))
        self.assertTrue(valid_reference('ab'*16))

    def test_icon_has_valid_multi_res_artifacts(self):
        with Image.open(ROOT/'assets/takepath.ico') as ico:
            self.assertGreaterEqual(len(ico.info.get('sizes', [])), 5)
        with Image.open(ROOT/'assets/takepath-icon.png') as png:
            self.assertEqual(png.size, (1024,1024))
        self.assertGreater((ROOT/'assets/takepath.icns').stat().st_size, 1000)

    def test_release_workflow_builds_on_each_os(self):
        workflow=(ROOT/'.github/workflows/release.yml').read_text(encoding="utf-8")
        for expected in ('windows-latest','macos-15','ubuntu-22.04',
                         'TakePath-linux-x64.AppImage','TakePath-windows-x64.exe',
                         'TakePath-macos-${{ matrix.arch }}.dmg','softprops/action-gh-release',
                         'SHA256SUMS.txt'):
            self.assertIn(expected,workflow)

    def test_no_secrets_in_project_file_support(self):
        from action_studio.core import Action, Project
        raw=Project(actions=[Action(kind='secure_input',text='sampleSecret123!')]).to_dict()
        self.assertNotIn('sampleSecret123!',str(raw))

if __name__=='__main__': unittest.main()
