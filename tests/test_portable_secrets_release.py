"""AES-GCM portable export security and backward-compatible project checks."""
import json
import unittest
import uuid
from copy import deepcopy

from action_studio.core import Action, Project
from action_studio.portable_secrets import (
    PortableSecretError, decrypt_secret_bundle, encrypt_secret_bundle,
)

PASSPHRASE="a-long-unique-secret-phrase-for-export"
PASSWORD="example-dummy-password-never-reuse"


class PortableSecretTests(unittest.TestCase):
    def setUp(self):
        self.a=Action(kind="secure_input",secure_mode="auto")
        self.b=Action(kind="secure_input",secure_mode="auto")
        self.values={self.a.id:PASSWORD,self.b.id:PASSWORD}
        self.project=Project(actions=[self.a,self.b])

    def test_encryption_roundtrip_across_project_serialization(self):
        bundle=encrypt_secret_bundle(self.values,PASSPHRASE)
        self.project.encrypted_secrets=bundle
        payload=json.dumps(self.project.to_dict())
        self.assertNotIn(PASSWORD,payload)
        self.assertNotIn(PASSPHRASE,payload)
        restored=Project.from_dict(json.loads(payload))
        self.assertEqual(decrypt_secret_bundle(restored.encrypted_secrets,PASSPHRASE),
                         self.values)
        self.assertEqual(restored.actions[0].text,"")
        self.assertEqual(restored.actions[1].text,"")

    def test_wrong_passphrase_and_tampered_ciphertext_fail_closed(self):
        bundle=encrypt_secret_bundle(self.values,PASSPHRASE)
        with self.assertRaises(PortableSecretError):
            decrypt_secret_bundle(bundle,"wrong-but-12-chars")
        tampered=deepcopy(bundle)
        data=tampered["data"]
        tampered["data"]=("B" if data[0]!="B" else "A")+data[1:]
        with self.assertRaises(PortableSecretError):
            decrypt_secret_bundle(tampered,PASSPHRASE)

    def test_random_salt_nonce_and_minimum_passphrase_length(self):
        a=encrypt_secret_bundle(self.values,PASSPHRASE)
        b=encrypt_secret_bundle(self.values,PASSPHRASE)
        self.assertNotEqual(a["salt"],b["salt"])
        self.assertNotEqual(a["nonce"],b["nonce"])
        self.assertNotEqual(a["data"],b["data"])
        with self.assertRaises(PortableSecretError):
            encrypt_secret_bundle(self.values,"short")

    def test_nonsecret_normal_project_and_old_project_compatibility(self):
        old=self.project.to_dict()
        old.pop("encrypted_secrets",None)
        restored=Project.from_dict(old)
        self.assertEqual(restored.encrypted_secrets,{})
        self.assertNotIn(PASSWORD,json.dumps(restored.to_dict()))

    def test_corrupt_unknown_bundle_rejected(self):
        bundle=encrypt_secret_bundle(self.values,PASSPHRASE)
        for key,value in [("version",2),("salt","!!not-base64!!"),
                          ("nonce",""),("cipher","none")]:
            modified=dict(bundle)
            modified[key]=value
            with self.subTest(key=key),self.assertRaises(PortableSecretError):
                decrypt_secret_bundle(modified,PASSPHRASE)

    def test_invalid_value_or_id_rejected_before_encryption(self):
        for payload in [{uuid.uuid4().hex:""}, {"not-an-id":PASSWORD}]:
            with self.assertRaises((PortableSecretError,ValueError)):
                encrypt_secret_bundle(payload,PASSPHRASE)


if __name__=="__main__":
    unittest.main()
