"""CTFd 3.7.7 ORM adapter for ridge.ctfd_provision.

Loaded only inside the extended CTFd image. It applies settings, creates or
finds teams/users, assigns memberships and commits once. Existing awards and
passwords are never modified.

LIVE VALIDATION BLOCKED: no Docker/Linux host is available in the wave-1/2 lane,
so this adapter has not been exercised against a real CTFd 3.7.7 database. The
pure planner/verifier in ridge.ctfd_provision is covered by deterministic tests.
"""
import argparse
import json
from pathlib import Path

from ridge.ctfd_provision import ProvisionSpec, TeamSpec, UserSpec, preflight, provision

SCHEMA = 'ctfd-3.7.7'


class OrmAdmin:
    def get_config(self, key, default=None):
        from CTFd.utils import get_config
        return get_config(key) if get_config(key) is not None else default

    def set_config(self, key, value):
        from CTFd.utils import set_config
        set_config(key, value)

    def find_team(self, name):
        from CTFd.models import Teams
        row = Teams.query.filter_by(name=name).first()
        if row is None:
            return None
        return {'id': int(row.id), 'name': row.name, 'banned': bool(row.banned), 'hidden': bool(row.hidden)}

    def create_team(self, name, password):
        from CTFd.models import Teams, db
        row = Teams(name=name, password=password)
        db.session.add(row)
        db.session.flush()
        return {'id': int(row.id), 'name': row.name, 'banned': False, 'hidden': False}

    def find_user(self, name):
        from CTFd.models import Users
        row = Users.query.filter_by(name=name).first()
        return None if row is None else {'id': int(row.id), 'name': row.name}

    def create_user(self, name, email, password):
        from CTFd.models import Users, db
        row = Users(name=name, email=email, password=password, type='user')
        db.session.add(row)
        db.session.flush()
        return {'id': int(row.id), 'name': row.name}

    def set_user_team(self, user_id, team_id):
        from CTFd.models import Users, db
        row = db.session.get(Users, user_id)
        if row is None:
            raise ValueError('User does not exist')
        row.team_id = team_id

    def user_team(self, user_id):
        from CTFd.models import Users, db
        row = db.session.get(Users, user_id)
        return None if row is None or row.team_id is None else int(row.team_id)

    def count_awards(self):
        from CTFd.models import Awards
        return int(Awards.query.count())


def _spec_from_json(document):
    return ProvisionSpec(
        schema=document.get('schema', SCHEMA),
        user_mode=document.get('user_mode', 'teams'),
        registration_visible=document.get('registration_visible', False),
        teams=tuple(TeamSpec(team=t['team'], name=t['name'], password=t['password'])
                    for t in document['teams']),
        users=tuple(UserSpec(name=u['name'], email=u['email'], team=u['team'], password=u['password'])
                    for u in document['users']))


def register(app):
    @app.cli.command('silent-ridge-provision')
    def silent_ridge_provision():
        parser = argparse.ArgumentParser(prog='flask silent-ridge-provision')
        parser.add_argument('--spec', type=Path, required=True,
                            help='Private provisioning spec JSON (contains credentials).')
        parser.add_argument('--inventory', type=Path, required=True)
        args = parser.parse_args()
        spec = _spec_from_json(json.loads(args.spec.read_text(encoding='utf-8')))
        admin = OrmAdmin()
        from CTFd.models import db
        try:
            inventory = provision(admin, spec)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        ready = preflight(admin, spec, inventory)
        args.inventory.write_text(json.dumps({'inventory': inventory, 'preflight': ready}, indent=2), encoding='utf-8')
        print(json.dumps(ready))
