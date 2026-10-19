"""CTFd 3.7.7 ORM adapter for ridge.ctfd_provision.

Loaded only inside the extended CTFd image. It applies settings, creates or
finds teams/users, assigns memberships and commits once. Existing awards and
passwords are never modified.

The pinned CTFd image smoke tests this adapter against a disposable SQLite
database, including the facilitator's real login and administrator page.
"""
import click
import json
import os
from pathlib import Path

from ridge.ctfd_provision import (FacilitatorSpec, ProvisionSpec, TeamSpec, UserSpec,
                                  preflight, provision)
from ridge.registration import RegistrationConfig, RegistrationStore

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

    def create_admin(self, name, email, password):
        from CTFd.models import Users, db
        row = Users(name=name, email=email, password=password, type='admin')
        db.session.add(row)
        db.session.flush()
        return {'id': int(row.id), 'name': row.name}

    def admin_login_valid(self, name, password):
        from CTFd.models import Users
        from CTFd.utils.crypto import verify_password
        row = Users.query.filter_by(name=name).first()
        return bool(row is not None and row.type == 'admin' and row.team_id is None
                    and verify_password(password, row.password))

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
                    for u in document['users']),
        facilitator=FacilitatorSpec(**document['facilitator'])
        if document.get('facilitator') else None)


def register(app):
    @app.cli.command('silent-ridge-provision')
    @click.option('--spec', 'spec_path', required=True, type=click.Path(exists=True, path_type=Path))
    @click.option('--inventory', required=True, type=click.Path(path_type=Path))
    def silent_ridge_provision(spec_path, inventory):
        # Older click ignores path_type and may hand back bytes.
        spec_path = Path(spec_path if isinstance(spec_path, (str, Path)) else __import__('os').fsdecode(spec_path))
        inventory = Path(inventory if isinstance(inventory, (str, Path)) else __import__('os').fsdecode(inventory))
        spec = _spec_from_json(json.loads(spec_path.read_text(encoding='utf-8')))
        admin = OrmAdmin()
        from CTFd.models import db
        try:
            result = provision(admin, spec)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        ready = preflight(admin, spec, result)
        inventory.write_text(json.dumps({'inventory': result, 'preflight': ready}, indent=2), encoding='utf-8')
        print(json.dumps(ready))

    @app.cli.command('silent-ridge-register')
    @click.option('--registration-id', required=True, type=int)
    def silent_ridge_register(registration_id):
        """Create one CTFd team and its five memberships from the allocator."""
        store = RegistrationStore(
            os.environ.get('RIDGE_REGISTRATION_DB', '/registration/registrations.sqlite'),
            RegistrationConfig(
                max_teams=int(os.environ.get('RIDGE_REGISTRATION_MAX_TEAMS', '10')),
                members_per_team=int(os.environ.get('RIDGE_REGISTRATION_MEMBERS', '5'))))
        registration = store.get_by_id(registration_id, include_private=True)
        if registration['status'] not in ('provisioning', 'ready'):
            raise click.ClickException('registration is not being provisioned')
        credentials = registration['credentials']['ctfd']
        admin = OrmAdmin()
        from CTFd.models import db
        try:
            team = admin.find_team(registration['team_name'])
            if team is None:
                team = admin.create_team(registration['team_name'], credentials['password'])
            team_id = int(team['id'])
            users = []
            for member in credentials['members']:
                user = _find_or_create_user_for_registration(admin, member, team_id)
                users.append({'id': int(user['id']), 'name': user['name']})
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        print(json.dumps({'team_id': team_id, 'team_name': registration['team_name'],
                          'users': users}))


def _find_or_create_user_for_registration(admin, member, team_id):
    """Idempotent helper used by the host registration worker."""
    existing = admin.find_user(member['username'])
    if existing is not None:
        if admin.user_team(int(existing['id'])) != team_id:
            raise click.ClickException('participant login belongs to another team')
        return existing
    created = admin.create_user(member['username'],
                                member['username'] + '@silent-ridge.invalid',
                                member['password'])
    admin.set_user_team(int(created['id']), team_id)
    return created
