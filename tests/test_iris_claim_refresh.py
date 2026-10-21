"""Regression coverage for the IRIS queue's claim POST/Redirect/GET flow."""
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class _Response:
    def __init__(self, status_code, location=None):
        self.status_code = status_code
        self.headers = {} if location is None else {'Location': location}


class _Request:
    method = 'GET'
    form = {}


class _CurrentUser:
    is_authenticated = True
    id = 'team-07'


class _FakeApp:
    class _CLI:
        @staticmethod
        def command(_name):
            return lambda function: function

    def __init__(self):
        self.cli = self._CLI()
        self.extensions = {}
        self.routes = {}

    def route(self, path, methods=None):
        def decorator(function):
            self.routes[path] = function
            return function
        return decorator


def _load_iris_module():
    """Load the integration with tiny stand-ins for IRIS-only dependencies."""
    class Model:
        pass

    db = types.SimpleNamespace(
        Model=Model,
        Column=lambda *args, **kwargs: None,
        String=lambda *args, **kwargs: object(),
        BigInteger=lambda *args, **kwargs: object(),
    )
    flask = types.ModuleType('flask')
    flask.abort = lambda code: (_ for _ in ()).throw(RuntimeError(code))
    flask.jsonify = lambda **payload: payload
    flask.redirect = lambda location, code=302: _Response(code, location)
    flask.render_template_string = lambda *args, **kwargs: 'rendered queue'
    flask.request = _Request()

    flask_login = types.ModuleType('flask_login')
    flask_login.current_user = _CurrentUser()
    flask_login.login_required = lambda function: function

    csrf = types.ModuleType('flask_wtf.csrf')
    csrf.generate_csrf = lambda: 'csrf-token'
    csrf.validate_csrf = lambda value: None

    validators = types.ModuleType('wtforms.validators')
    validators.ValidationError = type('ValidationError', (Exception,), {})
    sqlalchemy_exc = types.ModuleType('sqlalchemy.exc')
    sqlalchemy_exc.IntegrityError = type('IntegrityError', (Exception,), {})

    modules = {
        'flask': flask,
        'flask_login': flask_login,
        'flask_wtf': types.ModuleType('flask_wtf'),
        'flask_wtf.csrf': csrf,
        'wtforms': types.ModuleType('wtforms'),
        'wtforms.validators': validators,
        'sqlalchemy': types.ModuleType('sqlalchemy'),
        'sqlalchemy.exc': sqlalchemy_exc,
        'app': types.SimpleNamespace(db=db),
        'app.models': types.ModuleType('app.models'),
        'app.models.models': types.SimpleNamespace(CaseTasks=object, Comments=object,
                                                    TaskComments=object),
        'ridge.transport': types.SimpleNamespace(bridge=None, secret=None,
                                                 TRANSPORT_ERRORS=()),
        'ridge.narrative': types.SimpleNamespace(participant_context=lambda snapshot: {}),
        'ridge.web': types.SimpleNamespace(PAGE='page', queue_state=lambda snapshot: {}),
    }
    saved = {name: sys.modules.get(name) for name in modules}
    sys.modules.update(modules)
    try:
        path = Path(__file__).parents[1] / 'integrations' / 'iris_silent_ridge.py'
        spec = importlib.util.spec_from_file_location('_iris_silent_ridge_test_module', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


class IrisClaimRefreshTests(unittest.TestCase):
    def test_claim_redirects_before_refresh_can_replay_the_post(self):
        module = _load_iris_module()
        app = _FakeApp()
        module.install(app)
        request = module.request
        calls = []
        claimed = False

        def fake_bridge(application, identity, action, **payload):
            nonlocal claimed
            calls.append((application, identity, action, payload))
            if action == 'claim':
                if claimed:
                    self.fail('refresh replayed the claim POST')
                claimed = True
                return {'ok': True}
            if action == 'snapshot':
                return {'team': 'team-07', 'tickets': [], 'mode': 'running'}
            self.fail('unexpected bridge action: %s' % action)

        module.bridge = fake_bridge
        request.method = 'POST'
        request.form = {'csrf_token': 'csrf-token', 'action': 'claim',
                        'ticket': 'T07', 'generation': '0'}

        posted = app.routes['/silent-ridge']()

        self.assertEqual(posted.status_code, 303)
        self.assertEqual(posted.headers['Location'], '/silent-ridge')
        self.assertEqual([call[2] for call in calls], ['claim'])

        request.method = 'GET'
        request.form = {}
        with patch.dict(os.environ, {'IRIS_PUBLIC_URL': 'http://iris.test',
                                     'CTFD_PUBLIC_URL': 'http://ctfd.test',
                                     'RIDGE_IRIS_CASE': '1'}):
            refreshed = app.routes['/silent-ridge']()

        self.assertEqual(refreshed, 'rendered queue')
        self.assertEqual([call[2] for call in calls], ['claim', 'snapshot'])


if __name__ == '__main__':
    unittest.main()
