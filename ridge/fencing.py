"""F01 - active-site fencing and recovery ownership.

One authoritative active-site generation lives in a durable authority outside any
disposable instance. A planned move disables the source before the destination
activates; a partitioned source must be fenced by an externally verifiable action, not
by a flag written only at the destination. Every mutation path checks the site and the
generation it was issued under.
"""
import json
import os
from dataclasses import dataclass, field, replace
from pathlib import Path


class FenceError(RuntimeError):
    """The requested activation is unsafe without fencing the current writer."""


@dataclass(frozen=True)
class Authority:
    generation: int = 0
    active_site: str | None = None
    fenced: tuple = ()
    receipts: dict = field(default_factory=dict)


class Fence:
    def __init__(self, path, revoke=None):
        self.path = Path(path)
        self.revoke = revoke

    def authority_location(self):
        return str(self.path.resolve())

    def _read(self):
        if not self.path.is_file():
            return Authority()
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if data.get('schema') != 1:
            raise FenceError('Unknown authority schema')
        return Authority(int(data['generation']), data.get('active_site'),
                         tuple(data.get('fenced', ())), dict(data.get('receipts', {})))

    def _write(self, authority):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + '.tmp')
        temporary.write_text(json.dumps(dict(schema=1, generation=authority.generation,
                                             active_site=authority.active_site,
                                             fenced=list(authority.fenced),
                                             receipts=authority.receipts), indent=2, sort_keys=True) + '\n',
                              encoding='utf-8')
        os.replace(temporary, self.path)

    def confirm_fence(self, site, receipt):
        if not receipt:
            raise FenceError('Fencing requires a verifiable receipt')
        authority = self._read()
        fenced = list(authority.fenced)
        if site not in fenced:
            fenced.append(site)
        self._write(replace(authority, fenced=tuple(fenced),
                            receipts=dict(authority.receipts, **{site: receipt})))
        return self._read()

    def activate(self, site, source_confirmed=False):
        if not site:
            raise FenceError('An active site is required')
        authority = self._read()
        previous = authority.active_site
        if previous and previous != site and previous not in authority.fenced:
            if source_confirmed:
                authority = self.confirm_fence(previous, 'operator-confirmed')
            elif self.revoke is not None:
                receipt = self.revoke(previous)
                if not receipt:
                    raise FenceError('External fencing did not return a receipt')
                authority = self.confirm_fence(previous, receipt)
            else:
                raise FenceError('Fence the source before activating the destination')
        fenced = tuple(entry for entry in authority.fenced if entry != site)
        self._write(replace(authority, generation=authority.generation + 1,
                            active_site=site, fenced=fenced))
        return self._read()

    def accepts(self, site, generation):
        authority = self._read()
        return (site == authority.active_site and site not in authority.fenced
                and generation == authority.generation)

    def owner(self):
        return self._read()
