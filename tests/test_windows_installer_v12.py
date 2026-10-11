"""Build configuration checks for the optional Windows setup distribution."""
import re
import unittest
from pathlib import Path

from action_studio import __version__


ROOT = Path(__file__).resolve().parents[1]


class WindowsInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.iss = (ROOT / "installer" / "takepath.iss").read_text(encoding="utf-8")
        cls.builder = (ROOT / "scripts" / "build_windows_installer.ps1").read_text(encoding="utf-8")
        cls.release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        cls.smoke = (ROOT / ".github" / "workflows" / "windows-installer.yml").read_text(encoding="utf-8")

    def test_installer_has_per_user_install_and_uninstaller(self):
        self.assertIn("PrivilegesRequired=lowest", self.iss)
        self.assertIn("DefaultDirName={localappdata}\\Programs\\TakePath", self.iss)
        self.assertIn("AppId={{", self.iss)
        self.assertIn("UninstallDisplayIcon=", self.iss)
        self.assertIn("ArchitecturesAllowed=x64compatible", self.iss)

    def test_installer_uses_full_onedir_bundle(self):
        self.assertIn('Source: "..\\dist\\TakePath\\*"', self.iss)
        self.assertIn("recursesubdirs createallsubdirs", self.iss)
        self.assertIn("SetupIconFile=..\\assets\\takepath.ico", self.iss)

    def test_start_menu_optional_desktop_and_post_install_launch(self):
        self.assertIn('Name: "{autoprograms}\\TakePath"', self.iss)
        self.assertIn('Name: "{autodesktop}\\TakePath"', self.iss)
        self.assertIn("Flags: unchecked", self.iss)
        self.assertIn("postinstall skipifsilent", self.iss)

    def test_installer_and_package_versions_match(self):
        self.assertRegex(__version__, r"^1[.]2[.]0-beta[.]4$")
        self.assertIn('#define MyAppVersion "' + __version__ + '"', self.iss)
        self.assertIn("VersionInfoVersion={#MyAppNumericVersion}", self.iss)
        self.assertIn("MyAppNumericVersion=1.2.0.0", self.iss)

    def test_release_keeps_portable_and_adds_setup(self):
        self.assertIn("TakePath-windows-x64-portable.zip", self.release)
        self.assertIn("TakePath-windows-x64.exe", self.release)
        self.assertIn("./scripts/build_windows_installer.ps1", self.release)
        self.assertIn("path: release/*", self.release)
        self.assertIn("release/TakePath-*", self.release)

    def test_build_script_checks_compiler_version_and_output(self):
        self.assertIn("dist/TakePath/TakePath.exe", self.builder)
        self.assertIn("choco install innosetup", self.builder)
        self.assertIn("TakePath-windows-x64-setup.exe", self.builder)
        self.assertIn("/DMyAppVersion=", self.builder)
        self.assertIn("/DMyAppNumericVersion=", self.builder)
        self.assertIn("$LASTEXITCODE -ne 0", self.builder)

    def test_installer_smoke_build_runs_on_pull_requests(self):
        self.assertIn("pull_request:", self.smoke)
        self.assertIn("runs-on: windows-latest", self.smoke)
        self.assertIn("build_windows_installer.ps1", self.smoke)
        self.assertIn("windows-setup-smoke", self.smoke)


if __name__ == "__main__":
    unittest.main()
