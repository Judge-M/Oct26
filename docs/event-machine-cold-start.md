# Event machine cold start — one copy-paste sheet

For the **event hardware** (or any second machine) starting from nothing.
This is Phase 0 of `docs/dress-rehearsal-plan.md`, fully spelled out for
release **`v0.10.0-rehearsal`**. It ends with the event **up and paused**,
ready for the F03/F06 rehearsal phases or event day.

Works on Windows (Git Bash) or Linux. Requirements first:

- Docker Desktop / Docker Engine **running** (verify: `docker version`)
- Python 3.11+ (`python --version`), Git, and [GitHub CLI](https://cli.github.com/) (`gh auth login` if the repo is private)
- 32 GB RAM / 16 cores for 10 teams (64 GB comfortable), ~60 GB free disk
- No internet needed after the download step

Everything below runs in **Git Bash** (Windows) or any shell (Linux),
from a working directory of your choice. Time budget: download 13 GB
(connection-dependent), then ~20–40 minutes.

## 1. Get the tooling source (2 min)

```bash
git clone --depth 1 --branch v0.10.0-rehearsal https://github.com/Judge-M/Oct26.git oct26
cd oct26
```

## 2. Download the bundle assets (~13 GB)

```bash
mkdir -p work/dl
gh release download v0.10.0-rehearsal --repo Judge-M/Oct26 \
  --pattern "bundle-*" --pattern "validated-images.tar.part-*" --dir work/dl
ls work/dl | wc -l   # expect 26
```

## 3. Assemble the bundle directory

The release stores big files as 800 MB parts; the installer expects the
exact original files, so reassemble them byte-for-byte.

```bash
mkdir -p work/bundle/{autopsy,dependencies,disk,evidence,guides,memory}
cd work/dl

cat bundle-source.zip.part-* > ../bundle/source.zip
cat validated-images.tar.part-* > validated-images.tar

# re-split the image tar into the original 2 GiB parts the manifest expects
python - <<'EOF'
from pathlib import Path
src = Path('validated-images.tar')
part, out = 1, None
with src.open('rb') as f:
    while True:
        chunk = f.read(64*1024*1024)
        if not chunk:
            break
        if out is None:
            out = open(f'../bundle/validated-images.tar.part-{part:03d}', 'wb')
        out.write(chunk)
        if out.tell() >= 2147483648:
            out.close(); out = None; part += 1
if out:
    out.close()
print('parts written:', part)
EOF
rm validated-images.tar

cp bundle-autopsy-WS17-prepared-case-v2.tar.gz       ../bundle/autopsy/WS17-prepared-case-v2.tar.gz
cp bundle-dependencies-case-and-wazuh-config.tar.gz  ../bundle/dependencies/case-and-wazuh-config.tar.gz
cp bundle-dependencies-release-vault.tar.gz          ../bundle/dependencies/release-vault.tar.gz
cp bundle-disk-WS17-fat16.img                        ../bundle/disk/WS17-fat16.img
cp bundle-evidence-public.tar.gz                     ../bundle/evidence/evidence-public.tar.gz
cp bundle-guides.tar.gz                              ../bundle/guides/guides.tar.gz
cp bundle-memory-WS17-native-v1.tar.gz               ../bundle/memory/WS17-native-v1.tar.gz
cp bundle-release-manifest.json                      ../bundle/release-manifest.json
cp bundle-SHA256SUMS.json                            ../bundle/SHA256SUMS.json
cp bundle-source-image-checks.json                   ../bundle/source-image-checks.json
cd ../..
ls work/bundle work/bundle/* | wc -l   # expect 18 lines (12 files + 6 dir headers)
```

## 4. Install (hash-verify + docker load, 15–30 min)

```bash
time python -m ridge.offline_install work/bundle work/install
```

This verifies every hash, loads all 13 images into Docker, extracts the
source to `work/install`, and prints a receipt. Any corruption fails here,
before anything is half-installed — re-running is always safe.

## 5. Extract the content assets (2 min)

```bash
cd work/install && mkdir assets && cd assets
tar -xzf ../../bundle/evidence/evidence-public.tar.gz
tar -xzf ../../bundle/dependencies/case-and-wazuh-config.tar.gz
tar -xzf ../../bundle/dependencies/release-vault.tar.gz
mkdir originals && tar -xzf ../../bundle/memory/WS17-native-v1.tar.gz -C originals
cd ../../..
```

You now have `work/install/assets/{evidence-public,case-template,wazuh-config,release-vault,originals}`.

## 6. Profile + runtime config (5 min)

Get the machine's LAN IP (`ipconfig` / `ip addr` — the address participant
laptops will reach). Then, still in the `oct26` checkout:

```bash
cp deployment/profiles/example-two-team.json event-profile.json
```

Edit `event-profile.json` — **only** these fields:

- `event.event_start`, `event.duration_minutes`
- `addresses.central_bind_ip` → the LAN IP
- the three `*_public_url` values → `http://<LAN-IP>:8081`, `:8083`, `:8082`

Create `work/runtime/local.json` (replace `<ABS>` with the absolute path to
`work/install`, e.g. `C:/Users/you/oct26/work/install`):

```json
{
  "assets": {
    "evidence_public": "<ABS>/assets/evidence-public",
    "release_vault": "<ABS>/assets/release-vault",
    "case_template": "<ABS>/assets/case-template",
    "originals": "<ABS>/assets/originals",
    "wazuh_config": "<ABS>/assets/wazuh-config"
  },
  "ports": {"iris": 8081, "ctfd": 8083, "guac": 8082,
            "wazuh_dashboard": 8443, "wazuh_indexer": 9200},
  "index_name": "silent-ridge-oct26"
}
```

## 7. Bring the stack up (10–20 min)

```bash
python -m ridge.deploy doctor
python -m ridge.deploy up --teams 10 --profile event-profile.json --runtime work/runtime
# "services not ready"? just re-run the same up command — it reconciles (guacd needs ~5 min)
python -m ridge.deploy status --profile event-profile.json --runtime work/runtime
# expect: event_ready: true
```

`up` stops at a verified, **paused** state — participants see nothing until
`python -m ridge.deploy start --profile event-profile.json --runtime work/runtime`.

## Done — record these for the rehearsal evidence

- [ ] wall-clock time for step 4 (download → receipt) and step 7
- [ ] any step where this sheet was ambiguous — that is a doc bug, file it
- [ ] `status` output showing `event_ready: true`

Next: continue with `docs/dress-rehearsal-plan.md` Phase 1 (F03 certifying
run), or if this IS event day, `docs/event-day-commands.md` §3–§7.
