"""Participant-safe rendering for the private dynamic-team credential handout."""
from __future__ import annotations

from typing import Any, Mapping


def credential_handout_text(
        registration: Mapping[str, Any], credentials: Mapping[str, Any], *,
        retrieval_url: str, ctfd_url: str, iris_url: str, wazuh_url: str,
        guac_url: str) -> str:
    """Return a labelled text handout without exposing operator-only secrets.

    The CTFd team password and direct VNC passwords are deliberately omitted:
    participants are pre-assigned to their CTFd team and reach desktops through
    their isolated Guacamole account.
    """
    lines = [
        'OPERATION SILENT RIDGE - PRIVATE TEAM HANDOUT',
        'Team: %s' % registration['team_name'],
        'Return to this handout: %s' % retrieval_url,
        '',
        'Keep this file private. It contains your team credentials.',
        '',
        'CTFd - questions, answers, and help',
        'URL: %s' % ctfd_url,
        'Team ID: %s' % credentials['ctfd']['team'],
        'Team access: these member seats are already assigned; no team join password is required.',
    ]
    for index, member in enumerate(credentials['ctfd']['members'], 1):
        lines.extend([
            'Seat %d username: %s' % (index, member['username']),
            'Seat %d password: %s' % (index, member['password']),
        ])
    lines.extend([
        '',
        'IRIS - incident queue and shared findings',
        'URL: %s' % iris_url,
        'Username: %s' % credentials['iris']['username'],
        'Password: %s' % credentials['iris']['password'],
        '',
        'Wazuh Discover - prepared telemetry view',
        'URL: %s' % wazuh_url,
        'Username: %s' % credentials['wazuh']['username'],
        'Password: %s' % credentials['wazuh']['password'],
        '',
        'Guacamole - three investigation desktops',
        'URL: %s' % guac_url,
        'Username: %s' % credentials['guacamole']['username'],
        'Password: %s' % credentials['guacamole']['password'],
        'Desktop/VNC access: use Guacamole; no separate direct VNC password is participant-facing.',
        'Connections:',
    ])
    for desktop in (registration.get('result') or {}).get('desktop_urls', []):
        lines.append('- %s: %s - %s' % (
            desktop['connection_name'], desktop['name'], desktop['guidance']))
    lines.extend([
        '',
        'First action: choose one CTFd seat per participant, then open IRIS and claim one available ticket.',
    ])
    return '\n'.join(lines) + '\n'
