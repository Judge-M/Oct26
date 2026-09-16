"""Pinned IRIS 2.4.20 ORM adapter for ridge.iris_bootstrap.

Loaded inside the extended IRIS image only (see deployment/expanded/Dockerfile.iris).
It performs the case/service-user/team-user bootstrap in a single explicit
transaction and discovers live task status IDs. Numeric IDs are never assumed.

LIVE VALIDATION BLOCKED: no Docker/Linux host is available in the wave-1/2 lane,
so this adapter has not been exercised against a real IRIS 2.4.20 database. The
pure planner/verifier in ridge.iris_bootstrap is covered by deterministic tests.
"""
import argparse
import json
import os
from pathlib import Path

from ridge.iris_bootstrap import BootstrapSpec, IdentitySpec, bootstrap, preflight

SCHEMA = 'iris-2.4.20'


class OrmAdmin:
    """Implements ridge.iris_bootstrap.Admin against the pinned IRIS ORM."""

    def __init__(self):
        from app import db
        self.db = db

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
        return None if row is None else {'id': int(row.id), 'name': row.name}

    def create_case(self, name, description):
        from app.models.cases import Cases
        from app.models.models import CaseStatus
        from datetime import datetime, timezone
        customer = os.environ.get('IRIS_BOOTSTRAP_CUSTOMER_ID')
        status_name = os.environ.get('IRIS_BOOTSTRAP_CASE_STATUS', 'Open')
        if not customer:
            raise ValueError('IRIS_BOOTSTRAP_CUSTOMER_ID must be supplied; do not guess a customer')
        status = self.db.session.query(CaseStatus).filter(
            CaseStatus.status_name == status_name).one_or_none()
        if status is None:
            raise ValueError('Case status %r is not available in IRIS' % status_name)
        row = Cases(name=name, description=description, case_customer=int(customer),
                    case_status_id=int(status.id), open_date=datetime.now(timezone.utc).replace(tzinfo=None),
                    case_soc_id='')
        self.db.session.add(row)
        self.db.session.flush()
        return {'id': int(row.id), 'name': row.name}

    def find_user(self, login):
        from app.models.authorization import User
        row = self.db.session.query(User).filter_by(user=login).one_or_none()
        return None if row is None else {'id': int(row.id), 'user': row.user}

    def create_user(self, login, name, password):
        from app.models.authorization import User
        row = User(user=login, name=name, password=password, active=True)
        self.db.session.add(row)
        self.db.session.flush()
        return {'id': int(row.id), 'user': row.user}

    def set_case_access(self, user_id, case_id, level):
        from app.models.authorization import UserCaseEffectiveAccess, CaseAccessLevel
        from app.models.cases import Cases
        if self.db.session.get(Cases, case_id) is None:
            raise ValueError('Case does not exist')
        access = self.db.session.query(UserCaseEffectiveAccess).filter_by(
            user_id=user_id, case_id=case_id).one_or_none()
        value = CaseAccessLevel.read_only.value
        if access is None:
            self.db.session.add(UserCaseEffectiveAccess(user_id=user_id, case_id=case_id, access_level=value))
        elif access.access_level != value:
            access.access_level = value

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
    """Register the bootstrap CLI inside the IRIS application."""
    @app.cli.command('silent-ridge-bootstrap')
    def silent_ridge_bootstrap():
        parser = argparse.ArgumentParser(prog='flask silent-ridge-bootstrap')
        parser.add_argument('--spec', type=Path, required=True,
                            help='Private bootstrap spec JSON (contains credentials).')
        parser.add_argument('--inventory', type=Path, required=True,
                            help='Destination for the sanitized runtime inventory JSON.')
        args = parser.parse_args()
        spec = _spec_from_json(json.loads(args.spec.read_text(encoding='utf-8')))
        admin = OrmAdmin()
        try:
            inventory = bootstrap(admin, spec)
            admin.db.session.commit()
        except Exception:
            admin.db.session.rollback()
            raise
        ready = preflight(admin, spec, inventory)
        args.inventory.write_text(json.dumps({'inventory': inventory, 'preflight': ready}, indent=2), encoding='utf-8')
        # Inventory deliberately excludes passwords and secrets.
        print(json.dumps(ready))

    @app.cli.command('silent-ridge-verify')
    def silent_ridge_verify():
        parser = argparse.ArgumentParser(prog='flask silent-ridge-verify')
        parser.add_argument('--spec', type=Path, required=True)
        parser.add_argument('--inventory', type=Path, required=True)
        args = parser.parse_args()
        spec = _spec_from_json(json.loads(args.spec.read_text(encoding='utf-8')))
        inventory = json.loads(args.inventory.read_text(encoding='utf-8'))['inventory']
        print(json.dumps(preflight(OrmAdmin(), spec, inventory)))
