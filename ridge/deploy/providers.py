"""Provider contract and a deterministic in-memory fake for tests.

A provider returns handles, but a handle is not acceptance. The deployment
orchestrator only marks a step verified after :func:`probe` confirms the resource
exists. Real providers (Hyper-V, AWS, remote KVM) implement this contract in later
waves; :class:`FakeProvider` exists only for deterministic tests.
"""
import time
from typing import Protocol


class ProviderError(RuntimeError):
    pass


class Provider(Protocol):
    def create(self, kind: str, name: str, spec: dict) -> str: ...

    def probe(self, kind: str, name: str) -> str | None: ...

    def resume(self, kind: str, name: str, provider_id: str) -> bool: ...

    def stop(self, kind: str, name: str, provider_id: str) -> bool: ...

    def inventory(self) -> list[dict]: ...


class FakeProvider:
    """In-memory provider for deterministic tests. Never used for a real event."""

    def __init__(self, delay=0.0):
        self._resources = {}
        self.calls = []
        self.delay = delay
        self.fail_after_create = False
        self.fake_receipts = False

    def create(self, kind, name, spec=None):
        self.calls.append(('create', kind, name))
        if self.delay:
            time.sleep(self.delay)
        if self.fake_receipts:
            return 'receipt-' + name
        provider_id = '%s-%s' % (kind, name)
        self._resources[(kind, name)] = provider_id
        if self.fail_after_create:
            raise ProviderError('acknowledgment lost after create')
        return provider_id

    def probe(self, kind, name):
        self.calls.append(('probe', kind, name))
        return self._resources.get((kind, name))

    def resume(self, kind, name, provider_id):
        self.calls.append(('resume', kind, name, provider_id))
        return self._resources.get((kind, name)) == provider_id

    def stop(self, kind, name, provider_id):
        self.calls.append(('stop', kind, name, provider_id))
        if self._resources.get((kind, name)) != provider_id:
            return False
        del self._resources[(kind, name)]
        return True

    def inventory(self):
        return [{'kind': kind, 'name': name, 'provider_id': provider_id}
                for (kind, name), provider_id in sorted(self._resources.items())]
