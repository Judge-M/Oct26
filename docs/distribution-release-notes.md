This release distributes the custom integration, IRIS and CTFd container images
through GitHub Packages. `distribution.json` records their immutable digests,
source commit and the checksums of `source.zip` and `fixtures.zip`.

`source.zip` includes tracked files and materialized Git LFS exercise assets.
`fixtures.zip` includes generated fictional training evidence and authored tickets.
It contains exercise answers and facilitator-only release evidence: distribute it
to organizers, not as the participant evidence share.

This is a deployment candidate, not an event-ready or complete offline bundle.
The source includes a prepared Autopsy case with completed ingest and a saved
keyword index; see `assets/README.md` for its evidence mount and validation.
Upstream dependency containers, desktop images and native Windows captures
still need the compatibility and completeness checks documented
in `docs/expanded-deployment.md`. Application provisioning remains an operator
procedure. GitHub Packages may initially require authentication until package
visibility is configured.
