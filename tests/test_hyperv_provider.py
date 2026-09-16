"""Deterministic tests for the Hyper-V desktop provider (C01).

Hyper-V is unavailable on this Windows host (LIVE ACCEPTANCE BLOCKED). These
tests use a fake command runner and a temporary filesystem; no guest boots.
"""
import json
import tempfile
import unittest
from pathlib import Path

from ridge.hyperv_provider import (
    HyperVProfile, ProviderError, TeamDesktop, cache_path, clone_commands, convert, probe, provision,
    require_capacity, seed_files, sha256_file, user_data,
)


class FakeRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, command):
        self.calls.append(command)
        if command[0] == 'qemu-img' and command[1] == 'convert':
            Path(command[-1]).write_bytes(b'vhdx')
        elif command[0] == 'qemu-img' and command[1] == 'create':
            Path(command[-1]).write_bytes(b'disk')
        elif command[0] == 'cloud-localds':
            Path(command[1]).write_bytes(b'iso')


def make_source(root, data=b'qcow2-payload'):
    source = root / 'silent-ridge-desktop.qcow2'
    source.write_bytes(data)
    return source, sha256_file(source)


def team(name, password):
    return TeamDesktop(team=name, hostname=name + '.silent-ridge.test', admin_user='ridgeadmin',
                       admin_ssh_public_key='ssh-ed25519 AAAAC3Nz fixture', vnc_password=password,
                       endpoints={'iris': 'https://iris.test', 'ctfd': 'https://ctfd.test',
                                  'wazuh': 'https://wazuh.test'})


class HyperVProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def profile(self, digest):
        return HyperVProfile(base_sha256=digest, virtual_bytes=1024, disk_headroom_bytes=1024,
                             vcpus=2, memory_mib=4096)

    def test_wrong_hash_fails_before_conversion(self):
        source, digest = make_source(self.root)
        runner = FakeRunner()
        with self.assertRaisesRegex(ProviderError, 'base_sha256'):
            convert(source, self.profile('0' * 64), self.root / 'cache', runner, free_bytes=10 ** 12)
        self.assertEqual(runner.calls, [])
        self.assertFalse((self.root / 'cache').exists())

    def test_insufficient_disk_fails_before_conversion(self):
        source, digest = make_source(self.root)
        runner = FakeRunner()
        with self.assertRaisesRegex(ProviderError, 'free_bytes'):
            convert(source, self.profile(digest), self.root / 'cache', runner, free_bytes=10)
        self.assertEqual(runner.calls, [])

    def test_conversion_cached_by_hash_not_filename(self):
        source, digest = make_source(self.root)
        profile = self.profile(digest)
        runner = FakeRunner()
        first = convert(source, profile, self.root / 'cache', runner, free_bytes=10 ** 12)
        self.assertEqual(len(runner.calls), 1)
        copy = self.root / 'renamed-qcow2.bin'
        copy.write_bytes(source.read_bytes())
        second = convert(copy, profile, self.root / 'cache', runner, free_bytes=10 ** 12)
        self.assertEqual(first, second)
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(cache_path(self.root / 'cache', profile).name, 'silent-ridge-desktop-' + digest[:16] + '.vhdx')

    def test_capacity_requires_positive_clones(self):
        with self.assertRaisesRegex(ProviderError, 'clones'):
            require_capacity(10 ** 12, self.profile('a' * 64), 0)

    def test_two_clones_have_distinct_identity_and_credentials(self):
        source, digest = make_source(self.root)
        profile = self.profile(digest)
        runner = FakeRunner()
        inventory = provision(profile, source, self.root / 'cache',
                              [team('team-01', 'password-one'), team('team-02', 'password-two')],
                              self.root / 'work', runner, free_bytes=10 ** 12)
        self.assertEqual(set(inventory['clones']), {'team-01', 'team-02'})
        first = seed_files(team('team-01', 'password-one'))
        second = seed_files(team('team-02', 'password-two'))
        self.assertIn('instance-id: silent-ridge-team-01', first['meta-data'])
        self.assertIn('instance-id: silent-ridge-team-02', second['meta-data'])
        self.assertNotEqual(first['user-data'], second['user-data'])
        self.assertIn('password-one', first['user-data'])
        self.assertNotIn('password-two', first['user-data'])
        self.assertIn(json.dumps({'ctfd': 'https://ctfd.test', 'iris': 'https://iris.test',
                                  'wazuh': 'https://wazuh.test'}, sort_keys=True), first['user-data'])

    def test_seed_rejects_weak_password_and_bad_key(self):
        weak = TeamDesktop(team='t', hostname='t', admin_user='a', admin_ssh_public_key='ssh-ed25519 x',
                           vnc_password='short')
        with self.assertRaisesRegex(ProviderError, 'vnc_password'):
            user_data(weak)
        bad_key = TeamDesktop(team='t', hostname='t', admin_user='a', admin_ssh_public_key='not-a-key',
                              vnc_password='long-enough-password')
        with self.assertRaisesRegex(ProviderError, 'admin_ssh_public_key'):
            user_data(bad_key)

    def test_clone_commands_use_differencing_disk(self):
        commands = clone_commands(self.profile('a' * 64), Path('/base/base.vhdx'),
                                  team('team-01', 'password-one'), Path('/work/team-01'))
        create = commands[0]
        self.assertEqual(create[:2], ['qemu-img', 'create'])
        self.assertIn('-b', create)
        self.assertIn(str(Path('/base/base.vhdx')), create)
        self.assertTrue(create[-1].endswith('team-01.vhdx'))
        self.assertEqual(commands[1][0], 'cloud-localds')

    def test_probe_detects_missing_clone(self):
        source, digest = make_source(self.root)
        profile = self.profile(digest)
        runner = FakeRunner()
        inventory = provision(profile, source, self.root / 'cache',
                              [team('team-01', 'password-one')], self.root / 'work', runner,
                              free_bytes=10 ** 12)
        self.assertTrue(probe(profile, source, inventory)['ready'])
        Path(inventory['clones']['team-01']['disk']).unlink()
        with self.assertRaisesRegex(ProviderError, 'missing desktop artifacts'):
            probe(profile, source, inventory)


if __name__ == '__main__':
    unittest.main()
