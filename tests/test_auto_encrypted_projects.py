"""Regression coverage for zero-passphrase OS-protected TakePath Save/Export."""
import base64
import json
from pathlib import Path
import tempfile
import unittest

from action_studio.core import Action, Project
from action_studio.encrypted_projects import (
    FORMAT, KEY_REF, ProjectEncryptionError, decrypt_project, encrypt_project,
    load_encrypted_project, save_encrypted_project,
)

class MemoryVault:
    def __init__(self):
        self.data={}
        self.writes=0
    def get(self,ref):
        return self.data.get(ref)
    def set(self,ref,value):
        self.writes+=1
        self.data[ref]=value

class AutomaticEncryptionTests(unittest.TestCase):
    def setUp(self):
        self.vault=MemoryVault()
        self.action=Action(kind="secure_input",secure_mode="auto")
        self.project=Project(
            name="Sensitive workflow \u2013 example",
            actions=[Action(kind="type",text="private typed content"),self.action],
            target_title="Sensitive browser window")
        self.values={self.action.id:"dummy-test-credential"}
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/"workflow.vas.json"

    def test_save_encrypted_entire_project_not_just_passwords(self):
        save_encrypted_project(self.project,self.path,self.vault,self.values)
        content=self.path.read_text(encoding="utf-8")
        for forbidden in ("Sensitive workflow", "Sensitive browser",
                          "private typed content", "dummy-test-credential",
                          self.action.id, '"actions"', '"secure_values"'):
            self.assertNotIn(forbidden,content)
        payload=json.loads(content)
        self.assertEqual(payload["format"],FORMAT)
        self.assertEqual(payload["cipher"],"aes-256-gcm")
        self.assertNotIn("key",payload)
        self.assertNotIn("salt",payload)
        self.assertEqual(len(base64.b64decode(self.vault.data[KEY_REF])),32)

    def test_full_roundtrip_including_secret_after_reopening(self):
        save_encrypted_project(self.project,self.path,self.vault,self.values)
        loaded,secrets=load_encrypted_project(self.path,self.vault)
        self.assertEqual(loaded.name,self.project.name)
        self.assertEqual(loaded.actions[0].text,"private typed content")
        self.assertEqual(secrets,self.values)
        self.assertEqual(loaded.actions[1].text,"")

    def test_passwordless_project_is_still_fully_encrypted(self):
        blank=Project(name="My project",actions=[Action(kind="click",x=22,y=45)])
        save_encrypted_project(blank,self.path,self.vault)
        self.assertNotIn("My project",self.path.read_text(encoding="utf-8"))
        loaded,values=load_encrypted_project(self.path,self.vault)
        self.assertEqual(loaded.actions[0].x,22)
        self.assertEqual(values,{})

    def test_save_and_export_copy_same_key_and_independent_ciphertext(self):
        copy_path=Path(self.directory.name)/"export.vas.json"
        save_encrypted_project(self.project,self.path,self.vault,self.values)
        save_encrypted_project(self.project,copy_path,self.vault,self.values)
        self.assertEqual(self.vault.writes,1)
        self.assertNotEqual(self.path.read_bytes(),copy_path.read_bytes())
        self.assertEqual(load_encrypted_project(copy_path,self.vault)[1],self.values)

    def test_no_vault_fails_without_writing_plaintext_or_overwriting(self):
        self.path.write_bytes(b"existing file")
        with self.assertRaises(ProjectEncryptionError):
            save_encrypted_project(self.project,self.path,None,self.values)
        self.assertEqual(self.path.read_bytes(),b"existing file")
        with self.assertRaises(ProjectEncryptionError):
            decrypt_project(encrypt_project(self.project,self.vault),None)

    def test_wrong_account_missing_key_does_not_create_new_key(self):
        save_encrypted_project(self.project,self.path,self.vault,self.values)
        foreign=MemoryVault()
        with self.assertRaisesRegex(ProjectEncryptionError,"different"):
            load_encrypted_project(self.path,foreign)
        self.assertEqual(foreign.writes,0)

    def test_modified_ciphertext_and_nonce_fail_closed(self):
        data=json.loads(encrypt_project(self.project,self.vault,self.values))
        for field in ("data","nonce"):
            broken=data.copy()
            old=broken[field]
            # Flip a valid Base64 character, preserving shape.
            broken[field]=("B" if old[0]!="B" else "A")+old[1:]
            with self.subTest(field=field),self.assertRaises(ProjectEncryptionError):
                decrypt_project(json.dumps(broken).encode(),self.vault)

    def test_legacy_plaintext_import_and_encrypted_migration(self):
        self.path.write_text(json.dumps(self.project.to_dict()),encoding="utf-8")
        old,missing=load_encrypted_project(self.path,self.vault)
        self.assertEqual(old.name,self.project.name)
        self.assertEqual(missing,{})
        save_encrypted_project(old,self.path,self.vault)
        self.assertNotIn("Sensitive workflow",self.path.read_text(encoding="utf-8"))

    def test_failed_encrypt_does_not_overwrite_existing_saved_project(self):
        save_encrypted_project(self.project,self.path,self.vault,self.values)
        original=self.path.read_bytes()
        invalid={"bad-id":"secret"}
        with self.assertRaises(ProjectEncryptionError):
            save_encrypted_project(self.project,self.path,self.vault,invalid)
        self.assertEqual(self.path.read_bytes(),original)

if __name__=="__main__":
    unittest.main()
