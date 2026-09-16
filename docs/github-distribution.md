# GitHub distribution

GitHub is the distribution home: ordinary Git for source and small assets, Git
LFS for curated large assets, Packages for containers, and Releases for downloadable
source and generated fixtures. Secrets and live event progress are generated or
restored at deployment time; they never belong in the published source.

## Download one version

With Python 3.12+, this repository and GitHub CLI installed:

```text
python -m ridge.distribution fetch --release v0.1.0-rc.1 --destination work/download
```

Use an actually published tag. Authenticate with `gh auth login` if repository
access requires it. The command downloads the release inventory and assets to temporary
storage, verifies version, image references, sizes and checksums, and only then
publishes the destination directory. Existing destinations are never overwritten.
An interrupted or corrupt download cannot masquerade as a complete distribution.
Checksums rely on a trusted GitHub release manifest; they are not signatures.

Extract `source.zip` and `fixtures.zip` into separate directories. Copy each
`asset-*.bin` file to its relative source-tree path in the manifest's `assets`
mapping (creating parent directories). These files retain their original bytes;
the `.bin` release name is only a transport name. Read
`distribution.json` for the exact three custom image references and pull each
with `docker pull REFERENCE`. Set the corresponding `RIDGE_IMAGE`, `IRIS_IMAGE`
and `CTFD_IMAGE` values to those digest references. Other upstream containers and
configuration still follow [the deployment procedure](expanded-deployment.md).
The fetch command retrieves assets; it does not create AWS resources, initialize
accounts or start an event. Full local/AWS one-command deployment remains separate
work. The same release can be used on either Linux amd64 host.

## Publish

After merging and validating a release commit, a maintainer pushes a new `vX.Y.Z`
or `vX.Y.Z-rc.N` tag. `publish.yml` checks main ancestry and version format, runs
unit tests and the actual CTFd adapter smoke, publishes three images, then packages
source and fixtures. The release is always a prerelease while integration and
artifact acceptance remain incomplete. No `latest` image is published. Do not move
or reuse version tags; a correction receives a new version. Partial image builds
may exist in Packages after failure, but no release manifest is published until
all three image jobs and bundle verification succeed.

Expected package names:

- `ghcr.io/judge-m/oct26-integration`
- `ghcr.io/judge-m/oct26-iris`
- `ghcr.io/judge-m/oct26-ctfd`

OCI source labels connect these packages to the repository. GitHub initially
creates packages privately; configure visibility/access in package settings as
appropriate. Workflow permissions grant `packages: write` only to image publishing
and `contents: write` only to release publication. Ordinary PR validation does not
publish. Builds currently use the existing candidate base-image tags; the output
digest pins a release, but rebuilding a tag is not a reproducible base-image lock.

Large LFS assets are materialized by release checkout and published individually,
outside `source.zip`, with their original paths in the schema-two asset inventory.
Schema-one distributions remain readable. Every output file is limited to 1 GiB;
larger disk images must be stored as ordered parts before packaging.
Unresolved LFS pointers and symlinks fail packaging. Source packaging includes only
tracked paths, so ignored caches/secrets/runtime files cannot slip in through a
recursive directory copy. Maintainers must still review tracked content for secrets.
GitHub upload and LFS object size limits apply; split oversized distribution assets
before attempting a release that exceeds those limits.

See [asset policy](../assets/README.md). Complete offline distributions still use
`ridge.bundle` and `ridge.artifacts`; this workflow does not bypass their required
categories or claim that missing desktop/case files exist.

References: [GHCR](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry),
[Git LFS limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage).
