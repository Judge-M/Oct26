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
        'First action: use CTFd seats 1-4, then open IRIS and assign three different ticket IDs to the investigators. Seat 5 is a spare recovery login.',
        'IRIS manages ticket ownership and shared verified findings; CTFd contains questions, hints, answers, and scoring.',
        'Scoring: each question starts at 4 points; Help 1 and 2 are free; Help 3 costs 3 points and leaves the answer worth 1 point.',
        '',
        'DIVIDE THE WORK BEFORE STARTING',
        'The captain is not a required technical role. Any teammate with this private handout can coordinate if the captain is unavailable.',
        'Keep this handout open on at least two team laptops and say assignments out loud.',
        'Person 1 - coordinator and CTFd recorder: keep IRIS and CTFd open, assign three ticket IDs, submit answers, confirm accepted findings, and assign replacement work.',
        'Person 2 - network/Wazuh analyst: take one desktop and handle Wireshark or Wazuh tickets.',
        'Person 3 - disk/endpoint analyst: take one desktop and handle Autopsy tickets.',
        'Person 4 - binary/file analyst: take the third desktop and handle Cutter or Evidence file manager tickets.',
        'Workflow: all tickets are already open to every team. Mark assigned tickets Working in IRIS and Needs review for coordinator handoff. The three analysts report the answer, source path, and limitation; the coordinator submits in CTFd, confirms the IRIS finding, and assigns the next ticket.',
        'If someone is stuck, rotate the ticket or desktop. If the captain leaves, another teammate continues the same coordinator checklist with this handout.',
    ])
    return '\n'.join(lines) + '\n'
