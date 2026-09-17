"""Pinned IRIS 2.4.20 ORM adapter for ridge.iris_bootstrap.

Loaded inside the extended IRIS image only (see deployment/expanded/Dockerfile.iris).
It performs the case/service-user/team-user bootstrap in a single explicit
transaction and discovers live task status IDs. Numeric IDs are never assumed.

LIVE VALIDATION BLOCKED: no Docker/Linux host is available in the wave-1/2 lane,
so this adapter has not been exercised against a real IRIS 2.4.20 database. The
pure planner/verifier in ridge.iris_bootstrap is covered by deterministic tests.
"""
import click
import json
import os
from pathlib import Path

from ridge.iris_bootstrap import BootstrapSpec, IdentitySpec, bootstrap, preflight

SCHEMA = 'iris-2.4.20'


class OrmAdmin:
    """Implements ridge.iris_bootstrap.Admin against the pinned IRIS ORM."""

    def __init__(self, service_login):
        from app import db
        self.db = db
        self.service_login = service_login

    def schema_version(self):
        return SCHEMA

    def ensure_receipt_table(self):
        from iris_silent_ridge import RidgeReceipt
        RidgeReceipt.__table__.create(self.db.engine, checkfirst=True)

    def list_task_statuses(self):
        from app.models.models import TaskStatus
        rows = self.db.session.query(TaskStatus).all()
        result = []
        for row in rows:
            name = getattr(row, 'status_name', None) or getattr(row, 'name', None)
            if name is None:
                raise ValueError('TaskStatus row has no name column')
            result.append({'id': int(row.id), 'name': str(name)})
        return result

    def find_case(self, name):
        from app.models.cases import Cases
        row = self.db.session.query(Cases).filter_by(name=name).one_or_none()
        return None if row is None else {'id': int(row.case_id), 'name': row.name}

    def create_case(self, name, description):
        from app.models.cases import Cases
        from app.models.models import Client
        from app.models.authorization import User
        customer = self.db.session.query(Client).filter_by(name=name).one_or_none()
        if customer is None:
            customer = Client(name=name)
            self.db.session.add(customer)
            self.db.session.flush()
        service = self.db.session.query(User).filter_by(user=self.service_login).one()
        row = Cases(name=name, description=description, client_id=customer.client_id,
                    user=service, custom_attributes={})
        self.db.session.add(row)
        self.db.session.flush()
        return {'id': int(row.case_id), 'name': row.name}

    def find_user(self, login):
        from app.models.authorization import User
        row = self.db.session.query(User).filter_by(user=login).one_or_none()
        return None if row is None else {'id': int(row.id), 'user': row.user}

    def create_user(self, login, name, password):
        from app.models.authorization import User
        from app import bc
        row = User(user=login, name=name, email=login+'@silent-ridge.invalid',
                   password=bc.generate_password_hash(password).decode('utf-8'), active=True)
        self.db.session.add(row)
        self.db.session.flush()
        return {'id': int(row.id), 'user': row.user}

    def set_case_access(self, user_id, case_id, level):
        from app.models.authorization import UserCaseAccess, UserCaseEffectiveAccess, CaseAccessLevel
        if level != 'read_only':
            raise ValueError('Participant case access must be read_only')
        # Persist both the source grant and its effective projection.
        for model in (UserCaseAccess, UserCaseEffectiveAccess):
            access = self.db.session.query(model).filter_by(user_id=user_id, case_id=case_id).one_or_none()
            if access is None:
                self.db.session.add(model(user_id=user_id, case_id=case_id,
                                          access_level=CaseAccessLevel.read_only.value))
            else:
                access.access_level = CaseAccessLevel.read_only.value

    def case_access(self, user_id, case_id):
        from app.models.authorization import UserCaseEffectiveAccess, CaseAccessLevel
        access = self.db.session.query(UserCaseEffectiveAccess).filter_by(
            user_id=user_id, case_id=case_id).one_or_none()
        if access is None:
            return None
        return CaseAccessLevel(access.access_level).name

    def user_active(self, user_id):
        from app.models.authorization import User
        row = self.db.session.get(User, user_id)
        return bool(row is not None and row.active)

    def create_task(self, case_id, ticket, title, open_status_id, service_user_id):
        from app.models.models import CaseTasks
        from datetime import datetime, timezone
        stamp = datetime.now(timezone.utc).replace(tzinfo=None)
        row = CaseTasks(task_title=ticket+' · '+title,
                        task_description='Choose ownership through /silent-ridge. Correct answers add findings automatically.',
                        task_tags='Silent Ridge', task_case_id=case_id, task_status_id=open_status_id,
                        task_open_date=stamp, task_last_update=stamp, task_userid_open=service_user_id,
                        task_userid_update=service_user_id, custom_attributes={}, modification_history={})
        self.db.session.add(row)
        self.db.session.flush()
        return int(row.id)

    def create_finding(self, case_id, iris_id, service_user_id, finding):
        from app.models.models import CaseTasks, Comments, TaskComments
        from datetime import datetime, timezone
        task = self.db.session.query(CaseTasks).filter_by(id=iris_id, task_case_id=case_id).one()
        stamp = datetime.now(timezone.utc).replace(tzinfo=None)
        task.task_last_update = stamp
        task.task_userid_update = service_user_id
        text = ('Finding: '+str(finding['text'])+'\nEvidence: '+', '.join(finding['evidence']) +
                '\nLimitation: '+str(finding.get('limitation', '')))
        comment = Comments(comment_text=text, comment_date=stamp, comment_update_date=stamp,
                           comment_user_id=service_user_id, comment_case_id=case_id)
        self.db.session.add(comment)
        self.db.session.flush()
        self.db.session.add(TaskComments(comment_id=comment.comment_id, comment_task_id=task.id))
        return int(comment.comment_id)


def _spec_from_json(document):
    return BootstrapSpec(
        case_name=document['case_name'], case_description=document['case_description'],
        service_login=document['service_login'], service_name=document['service_name'],
        service_password=document['service_password'], open_status=document['open_status'],
        closed_status=document['closed_status'], schema=document.get('schema', SCHEMA),
        identities=tuple(IdentitySpec(team=i['team'], login=i['login'], name=i['name'],
                                      password=i['password']) for i in document['identities']))


def register(app):
    @app.cli.command('silent-ridge-bootstrap')
    @click.option('--spec', 'spec_path', required=True, type=click.Path(exists=True, path_type=Path))
    @click.option('--inventory', required=True, type=click.Path(path_type=Path))
    def silent_ridge_bootstrap(spec_path, inventory):
        from sqlalchemy import text
        spec = _spec_from_json(json.loads(spec_path.read_text(encoding='utf-8')))
        admin = OrmAdmin(spec.service_login)
        try:
            # Serialize lookup/create even if two organizers retry concurrently.
            admin.db.session.execute(text("SELECT pg_advisory_xact_lock(742601)"))
            result = bootstrap(admin, spec)
            ready = preflight(admin, spec, result)
            admin.db.session.commit()
        except Exception:
            admin.db.session.rollback()
            raise
        inventory.write_text(json.dumps({'inventory': result, 'preflight': ready}, indent=2))
        print(json.dumps(ready))
