"""Issue #184 regression coverage: early failure on an overwritten base tag.

A previous build that saved its finished image over a base tag (for example
``docker tag silent-ridge-desktop:dev ubuntu:24.04``) made ``build
--pull=false`` start from a polluted base. The real cause only surfaced
hundreds of build steps later as a misleading Dockerfile error
(``useradd: user 'participant' already exists``). build() must now refuse
before invoking docker build, naming the tag, the cached image id, and the
``docker rmi`` remedy.
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ridge.deploy.__main__ import (_registry_repository, build,
                                   registry_digest_for, verify_base_cache)

CLEAN_CTFD = json.dumps([{
    'Id': 'sha256:008173c23f95aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'RepoDigests': ['docker.io/ctfd/ctfd@sha256:1111111111111111111111111111111111111111111111111111111111111111'],
}])
# The incident shape: the desktop build re-tagged over the base. A locally
# built image carries no RepoDigests at all.
CLOBBERED = json.dumps([{
    'Id': 'sha256:6ae4ae95788c2222222222222222222222222222222222222222222222222222',
    'RepoDigests': [],
}])
FOREIGN = json.dumps([{
    'Id': 'sha256:008173c23f95aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'RepoDigests': ['evil.example.com/ctfd/ctfd@sha256:2222222222222222222222222222222222222222222222222222222222222222'],
}])
# The Docker Desktop 29.8.0 shape observed on the event host after an
# authenticated `docker pull docker.io/ctfd/ctfd:3.7.7`: an authentic digest
# reported under the short Docker Hub spelling, not the canonical
# docker.io/ctfd/ctfd. The guard must accept it as the same repository.
SHORT_SPELLING_CTFD = json.dumps([{
    'Id': 'sha256:008173c23f95aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'RepoDigests': ['ctfd/ctfd@sha256:9847758' + '0' * 57],
}])
# Fresh `docker pull ubuntu:24.04` on a Docker/containerd that records Docker
# Hub official images under their short repository: the RepoDigest carries
# ``ubuntu@sha256:...``, not ``docker.io/library/ubuntu@sha256:...``. This is a
# genuine registry pull; the preflight must accept it (issue #184 follow-up:
# the short form was falsely reported as an overwritten tag).
SHORT_HUB_UBUNTU = json.dumps([{
    'Id': 'sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55',
    'RepoDigests': ['ubuntu@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55'],
}])


def docker_returning(responses, default='ok'):
    """Fake docker() answering `image inspect <name>` from {name: stdout}."""
    def fake(*args, capture=False):
        argv = list(args)
        if argv[:2] == ['image', 'inspect'] and len(argv) == 3:
            if argv[2] in responses:
                value = responses[argv[2]]
                if isinstance(value, Exception):
                    raise value
                return value
            raise subprocess.CalledProcessError(1, 'docker')
        return default
    return fake


class RegistryRepositoryTests(unittest.TestCase):
    def test_normalizes_to_dockers_canonical_form(self):
        # RepoDigests are only ever reported in canonical form, so the FROM
        # spelling must be normalized the same way Docker does.
        self.assertEqual(_registry_repository('ubuntu:24.04'),
                         'docker.io/library/ubuntu')
        self.assertEqual(_registry_repository('ctfd/ctfd:3.7.7'),
                         'docker.io/ctfd/ctfd')
        self.assertEqual(_registry_repository('ghcr.io/dfir-iris/iriswebapp_app:v2.4.20'),
                         'ghcr.io/dfir-iris/iriswebapp_app')
        self.assertEqual(_registry_repository('localhost:5000/team/base:1'),
                         'localhost:5000/team/base')
        self.assertEqual(_registry_repository('python'), 'docker.io/library/python')


class RegistryDigestTests(unittest.TestCase):
    def test_digest_found_only_for_the_exact_repository(self):
        clean = json.loads(CLEAN_CTFD)[0]
        self.assertTrue(registry_digest_for('ctfd/ctfd:3.7.7', clean))
        # A different tag of the same repository still matches the repository.
        self.assertTrue(registry_digest_for('ctfd/ctfd:3.7.6', clean))
        # A foreign repository does not prove this tag's provenance.
        self.assertIsNone(registry_digest_for('ctfd/ctfd:3.7.7', json.loads(FOREIGN)[0]))
        # A locally built image has no provenance at all.
        self.assertIsNone(registry_digest_for('ctfd/ctfd:3.7.7', json.loads(CLOBBERED)[0]))

    def test_digest_pinned_reference_is_exempt(self):
        # `docker tag` refuses digest targets, so a digest-pinned FROM cannot
        # be overwritten the way issue #184's tag was.
        details = {'Id': 'sha256:abc', 'RepoDigests': []}
        self.assertIsNotNone(
            registry_digest_for('ubuntu@sha256:3333333333333333333333333333333333333333333333333333333333333333',
                                details))


class DockerDesktopShortSpellingTests(unittest.TestCase):
    """Equivalent Docker Hub spellings denote the same repository.

    Docker Desktop 29.8.0 reports RepoDigests for an authentic
    ``docker pull docker.io/ctfd/ctfd:3.7.7`` as ``ctfd/ctfd@sha256:...``.
    The issue #184 guard must treat the short, ``library/`` and canonical
    ``docker.io`` spellings as one repository — while still rejecting
    digests from any genuinely different repository.
    """

    def test_short_hub_spelling_digest_proves_the_pull(self):
        details = json.loads(SHORT_SPELLING_CTFD)[0]
        self.assertTrue(registry_digest_for('ctfd/ctfd:3.7.7', details))
        # The FROM spelled canonically is the same repository too.
        self.assertTrue(registry_digest_for('docker.io/ctfd/ctfd:3.7.7', details))

    def test_canonical_digest_still_matches_when_either_side_is_short(self):
        clean = json.loads(CLEAN_CTFD)[0]
        self.assertTrue(registry_digest_for('docker.io/ctfd/ctfd:3.7.7', clean))

    def test_library_alias_spellings_are_equivalent(self):
        # Official images: ubuntu == library/ubuntu == docker.io/library/ubuntu.
        digest = 'sha256:' + '3' * 64
        for spelling in ('library/ubuntu@' + digest,
                         'docker.io/library/ubuntu@' + digest):
            with self.subTest(digest=spelling):
                details = {'RepoDigests': [spelling]}
                self.assertTrue(registry_digest_for('ubuntu:24.04', details))
                self.assertTrue(registry_digest_for('library/ubuntu:24.04', details))
                self.assertTrue(registry_digest_for('docker.io/library/ubuntu:24.04', details))

    def test_short_spelling_does_not_widen_trust_to_other_repositories(self):
        # Normalization must not let a retagged image from a different Hub
        # repository (or another registry) pass as ctfd/ctfd.
        for digests in (['evil/ctfd@sha256:' + '2' * 64],
                        ['ctfd/ctfd-not@sha256:' + '2' * 64],
                        ['ctfd/library/ctfd@sha256:' + '2' * 64],
                        ['evil.example.com/ctfd/ctfd@sha256:' + '2' * 64]):
            with self.subTest(digests=digests):
                self.assertIsNone(
                    registry_digest_for('ctfd/ctfd:3.7.7', {'RepoDigests': digests}))

    def test_verify_base_cache_accepts_the_docker_desktop_shape(self):
        with patch('ridge.deploy.__main__.docker',
                   docker_returning({'ctfd/ctfd:3.7.7': SHORT_SPELLING_CTFD})):
            problems, uncached = verify_base_cache(['ctfd/ctfd:3.7.7'])
        self.assertEqual((problems, uncached), ([], []))

    def test_short_docker_hub_repodigest_proves_the_tag(self):
        # `docker pull ubuntu:24.04` can record the RepoDigest in short form
        # (``ubuntu@sha256:...``, no docker.io/library prefix). The FROM
        # reference and the digest's repository are the same Docker Hub
        # repository, so the preflight must accept it, not report #184.
        short = json.loads(SHORT_HUB_UBUNTU)[0]
        self.assertTrue(registry_digest_for('ubuntu:24.04', short))
        with patch('ridge.deploy.__main__.docker',
                   docker_returning({'ubuntu:24.04': SHORT_HUB_UBUNTU})):
            problems, uncached = verify_base_cache(['ubuntu:24.04'])
        self.assertEqual((problems, uncached), ([], []))


class VerifyBaseCacheTests(unittest.TestCase):
    def test_clobbered_tag_is_a_problem_naming_id_and_remedy(self):
        with patch('ridge.deploy.__main__.docker', docker_returning({'ctfd/ctfd:3.7.7': CLOBBERED})):
            problems, uncached = verify_base_cache(['ctfd/ctfd:3.7.7'])
        self.assertEqual(uncached, [])
        self.assertEqual(len(problems), 1)
        self.assertIn('ctfd/ctfd:3.7.7', problems[0])
        self.assertIn('not a registry pull', problems[0])
        self.assertIn('sha256:6ae4ae95788c', problems[0])
        self.assertIn('docker rmi ctfd/ctfd:3.7.7', problems[0])
        self.assertIn('Dockerfile is not at fault', problems[0])

    def test_clean_cached_base_is_accepted(self):
        with patch('ridge.deploy.__main__.docker', docker_returning({'ctfd/ctfd:3.7.7': CLEAN_CTFD})):
            problems, uncached = verify_base_cache(['ctfd/ctfd:3.7.7'])
        self.assertEqual((problems, uncached), ([], []))

    def test_foreign_repository_digest_does_not_prove_the_tag(self):
        with patch('ridge.deploy.__main__.docker', docker_returning({'ctfd/ctfd:3.7.7': FOREIGN})):
            problems, _ = verify_base_cache(['ctfd/ctfd:3.7.7'])
        self.assertEqual(len(problems), 1)
        self.assertIn('evil.example.com/ctfd/ctfd@sha256:222', problems[0])

    def test_uncached_base_is_reported_not_a_problem(self):
        # A cold preparation host legitimately has nothing cached; the build
        # must still proceed (see the first-build CI contract).
        with patch('ridge.deploy.__main__.docker', docker_returning({})):
            problems, uncached = verify_base_cache(['ctfd/ctfd:3.7.7'])
        self.assertEqual(problems, [])
        self.assertEqual(uncached, ['ctfd/ctfd:3.7.7'])

    def test_unreadable_inspect_output_warns_and_proceeds(self):
        notes = []
        with patch('ridge.deploy.__main__.docker', return_value='sha256:not-json'), \
                patch('builtins.print', side_effect=notes.append):
            problems, uncached = verify_base_cache(['ctfd/ctfd:3.7.7'])
        self.assertEqual((problems, uncached), ([], []))
        self.assertTrue(any('could not verify cache provenance' in note for note in notes),
                        notes)

    def test_digest_pinned_from_needs_no_provenance(self):
        pinned = 'ubuntu@sha256:4444444444444444444444444444444444444444444444444444444444444444'
        with patch('ridge.deploy.__main__.docker',
                   docker_returning({pinned: json.dumps([{'Id': 'sha256:x', 'RepoDigests': []}])})):
            problems, uncached = verify_base_cache([pinned])
        self.assertEqual((problems, uncached), ([], []))


class BuildRefusesClobberedBaseTests(unittest.TestCase):
    def test_build_fails_before_docker_build_and_writes_no_receipt(self):
        calls = []

        def recorder(*args, capture=False):
            calls.append(list(args))
            if list(args)[:2] == ['image', 'inspect'] and list(args)[2] == 'ctfd/ctfd:3.7.7':
                return CLOBBERED
            return 'ok'

        with tempfile.TemporaryDirectory() as temp:
            with patch('ridge.deploy.__main__.docker', side_effect=recorder), \
                    patch('ridge.deploy.__main__.fingerprint', return_value='fp'):
                with self.assertRaises(ValueError) as caught:
                    build('ctfd', Path(temp))
            self.assertFalse((Path(temp) / 'ctfd.json').exists(),
                             'a refused build must not leave a receipt')
        self.assertFalse([c for c in calls if c[0] == 'build'],
                         'docker build must never start from a polluted base')
        message = str(caught.exception)
        self.assertIn('ctfd/ctfd:3.7.7', message)
        self.assertIn('docker rmi ctfd/ctfd:3.7.7', message)

    def test_build_proceeds_with_a_verified_cached_base(self):
        def recorder(*args, capture=False):
            argv = list(args)
            if argv[:2] == ['image', 'inspect'] and len(argv) == 3:
                return CLEAN_CTFD
            return 'sha256:built'

        with tempfile.TemporaryDirectory() as temp:
            with patch('ridge.deploy.__main__.docker', side_effect=recorder), \
                    patch('ridge.deploy.__main__.fingerprint', return_value='fp'):
                result = build('ctfd', Path(temp))
            self.assertEqual(result['image_id'], 'sha256:built')
            self.assertTrue((Path(temp) / 'ctfd.json').is_file())


if __name__ == '__main__':
    unittest.main()
