import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from ridge.desktop_image import assemble

REPO = Path(__file__).resolve().parents[1]
DESKTOP = REPO / 'deployment/expanded/desktop'


class DesktopImageTests(unittest.TestCase):
    def test_integrity_order_and_existing_disk_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parts = []
            for name, data in [('part1', b'first'), ('part2', b'second')]:
                (root / name).write_bytes(data)
                parts.append(dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
            manifest = dict(schema=1, format='qcow2', parts=parts, bytes=11,
                            sha256=hashlib.sha256(b'firstsecond').hexdigest())
            output = root / 'disk.qcow2'
            assemble(root, manifest, output)
            self.assertEqual(output.read_bytes(), b'firstsecond')
            with self.assertRaises(ValueError):
                assemble(root, manifest, output)
            manifest['parts'] = list(reversed(parts))
            with self.assertRaisesRegex(ValueError, 'Reassembled'):
                assemble(root, manifest, root / 'wrong-order')
            self.assertFalse((root / 'wrong-order').exists())
            (root / 'part1').write_bytes(b'broken')
            with self.assertRaisesRegex(ValueError, 'Corrupt'):
                assemble(root, manifest, root / 'corrupt')
            self.assertFalse(list(root.glob('.desktop-*')))


class DesktopContainerTests(unittest.TestCase):
    """Static validation of the additive container desktop. No image is built."""

    @classmethod
    def setUpClass(cls):
        cls.dockerfile = (DESKTOP / 'Dockerfile').read_text(encoding='utf-8')
        cls.entrypoint = (DESKTOP / 'entrypoint.sh').read_text(encoding='utf-8')
        cls.configure = (DESKTOP / 'configure-desktop.sh').read_text(encoding='utf-8')
        cls.manifest = json.loads((REPO / 'assets/desktop-container.json').read_text(encoding='utf-8'))
        cls.vm = json.loads((REPO / 'assets/desktop-v1.json').read_text(encoding='utf-8'))

    def test_dockerfile_installs_required_packages(self):
        required = ('xfce4', 'xfce4-terminal', 'tigervnc-standalone-server', 'dbus-x11',
                    'thunar', 'wireshark', 'zenity', 'openjdk-21-jre', 'libopenjfx-java',
                    'fonts-dejavu', 'fonts-noto-color-emoji', 'adwaita-icon-theme', 'tini',
                    'ca-certificates', 'curl', 'xz-utils', 'python3')
        for package in required:
            self.assertIn(package, self.dockerfile, package)
        self.assertRegex(self.dockerfile, r'(?m)^FROM\s+ubuntu:24\.04')
        self.assertIn('EXPOSE 5901', self.dockerfile)
        self.assertIn('useradd', self.dockerfile)
        self.assertIn('participant', self.dockerfile)

    def test_dockerfile_stages_tools_and_entrypoint(self):
        self.assertIn('/opt/autopsy', self.dockerfile)
        self.assertIn('/opt/cutter/Cutter.AppImage', self.dockerfile)
        self.assertIn('/opt/firefox', self.dockerfile)
        for version in ('4.22.0', '4.13.0', '2.5.0', '140.16.0esr'):
            self.assertIn(version, self.dockerfile, version)
        self.assertIn('unix_setup.sh', self.dockerfile)
        self.assertIn('--enable-java', self.dockerfile)
        self.assertIn('CUTTER_SHA256=b8ad215d7a9e2af9e1f463511229f16e1f4745a0fb541413e5f4787f949ac0cf',
                      self.dockerfile)
        self.assertIn('FIREFOX_SHA256=a90174f8fecfb1767371015a625a2f7ffc1edafd9110717348e797a46a066edf',
                      self.dockerfile)
        self.assertIn('ENTRYPOINT ["/usr/bin/tini", "--"]', self.dockerfile)
        self.assertIn('CMD ["/usr/local/bin/silent-ridge-entrypoint"]', self.dockerfile)

    def test_entrypoint_fails_fast_without_a_password(self):
        self.assertIn('/run/secrets/vnc_password', self.entrypoint)
        self.assertIn('/etc/silent-ridge/vnc-password', self.entrypoint)
        self.assertIn('install -m 600', self.entrypoint)
        self.assertIn('exit 1', self.entrypoint)
        secret_check = self.entrypoint.index('VNC password secret')
        launch = self.entrypoint.index('Xtigervnc :1')
        self.assertLess(secret_check, launch, 'password must be required before VNC starts')

    def test_entrypoint_writes_endpoints_from_environment(self):
        self.assertIn('endpoints.json', self.entrypoint)
        self.assertIn('IRIS_URL', self.entrypoint)
        self.assertIn('CTFD_URL', self.entrypoint)
        self.assertIn('WAZUH_URL', self.entrypoint)
        self.assertIn('if [ ! -f "$ENDPOINTS_FILE" ]', self.entrypoint)

    def test_entrypoint_starts_vnc_and_session(self):
        self.assertIn('Xtigervnc :1 -geometry 1440x900 -depth 24 -SecurityTypes VncAuth',
                      self.entrypoint)
        self.assertIn('-PasswordFile "$VNC_PASSWORD_FILE"', self.entrypoint)
        self.assertIn('-AlwaysShared', self.entrypoint)
        self.assertIn('-localhost no', self.entrypoint)
        self.assertRegex(self.entrypoint, r'exec\s+runuser\s+-u\s+participant')
        self.assertIn('dbus-run-session -- startxfce4', self.entrypoint)

    def test_desktop_shortcuts_and_helpers_mirror_vm(self):
        for title in ('Incident queue', 'Questions and help', 'Wazuh', 'Evidence',
                      'How-to guides', 'Autopsy', 'Wireshark', 'Cutter'):
            self.assertIn(title, self.configure, title)
        for command in ('/opt/silent-ridge/open-service.py iris',
                        '/opt/silent-ridge/open-service.py ctfd',
                        '/opt/silent-ridge/open-service.py wazuh',
                        'thunar /evidence', 'thunar /evidence/guides',
                        '/opt/silent-ridge/open-autopsy.sh', 'wireshark',
                        '/opt/cutter/Cutter.AppImage --appimage-extract-and-run'):
            self.assertIn(command, self.configure, command)
        service = (DESKTOP / 'helpers/open-service.py').read_text(encoding='utf-8')
        self.assertIn('/etc/silent-ridge/endpoints.json', service)
        self.assertIn('/usr/local/bin/firefox', service)
        self.assertIn('zenity', service)
        autopsy = (DESKTOP / 'helpers/open-autopsy.sh').read_text(encoding='utf-8')
        for token in ('SOLR_LOGS_DIR', 'SOLR_PID_DIR', '/opt/autopsy/bin/autopsy',
                      '-J--module-path=/usr/share/openjfx/lib'):
            self.assertIn(token, autopsy, token)

    def test_manifest_matches_desktop_v1_pins(self):
        self.assertEqual(self.manifest['base_image']['reference'], 'ubuntu:24.04')
        vm_base = self.vm['base_image']
        self.assertEqual(self.manifest['base_image']['vm_base_image']['url'], vm_base['url'])
        self.assertEqual(self.manifest['base_image']['vm_base_image']['sha256'], vm_base['sha256'])
        inputs = {entry['name']: entry for entry in self.manifest['build_inputs']}
        for name in ('cutter', 'firefox'):
            self.assertEqual(inputs[name]['url'], self.vm['tools'][name]['url'])
            self.assertEqual(inputs[name]['sha256'], self.vm['tools'][name]['sha256'])
            self.assertEqual(inputs[name]['version'], self.vm['tools'][name]['version'])
        self.assertEqual(self.manifest['tools']['autopsy'], self.vm['tools']['autopsy'])
        self.assertEqual(self.manifest['tools']['sleuthkit'], self.vm['tools']['sleuthkit'])
        known = {(vm_base['url'], vm_base['sha256']),
                 (self.vm['tools']['cutter']['url'], self.vm['tools']['cutter']['sha256']),
                 (self.vm['tools']['firefox']['url'], self.vm['tools']['firefox']['sha256'])}
        for entry in self.manifest['build_inputs']:
            if entry.get('url') and entry.get('sha256'):
                self.assertIn((entry['url'], entry['sha256']), known)

    def test_manifest_does_not_claim_a_build(self):
        self.assertIs(self.manifest['event_ready'], False)
        self.assertIs(self.manifest['image_built'], False)
        self.assertIs(self.manifest['build_validated'], False)
        contract = self.manifest['runtime_contract']
        self.assertEqual(contract['vnc_port'], 5901)
        self.assertIs(contract['vnc_published_to_host'], False)
        self.assertEqual(contract['vnc_network'], 'desktop')
        for variable in ('VNC_PASSWORD_FILE', 'IRIS_URL', 'CTFD_URL', 'WAZUH_URL'):
            self.assertIn(variable, contract['env'])
        mounts = {(mount['path'], mount['mode']) for mount in contract['mounts']}
        self.assertIn(('/evidence', 'ro'), mounts)
        self.assertIn(('/originals', 'ro'), mounts)
        for path in ('/home/participant/Cases', '/home/participant/Workspace',
                     '/home/participant/Scratch'):
            self.assertIn((path, 'rw'), mounts)

    def test_build_context_and_readme_are_present(self):
        self.assertIn('!deployment/expanded/desktop/',
                      (REPO / '.dockerignore').read_text(encoding='utf-8'))
        readme = (DESKTOP / 'README.md').read_text(encoding='utf-8')
        self.assertIn('docker build -f deployment/expanded/desktop/Dockerfile', readme)


if __name__ == '__main__':
    unittest.main()
