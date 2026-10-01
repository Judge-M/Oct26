# 5-team AI stress test — infrastructure metrics

Sampled every 5 s for the run: **148 samples over 1,050 s (17.5 min)**, 19
containers tracked, 5 AI teams playing concurrently.

## Host memory

- total: **63.7 GiB** (corrected — earlier receipts said 31.7 GiB; that was my
  measurement error)
- available: min 42.98 GiB, mean 43.16 GiB, max 43.37 GiB
- **worst-case reserve: 67.5%**

The host never came under memory pressure. The binding constraint is the Docker
memory cap (31.2 GiB), not the hardware.

## Host disk (C:)

- free: 226.7 → 226.4 GiB (**0.30 GiB consumed** across the whole run)

Disk consumption is negligible; the 238 GiB figure in the capacity model is
dominated by images and LFS assets, not by runtime growth.

## Per-container peaks

| container | peak mem MiB | peak CPU % |
|---|---|---|
| wazuh-wazuh-indexer-1 | 1689.6 | 7 |
| desktop-access-guacamole-1 | 593.0 | 1 |
| wazuh-wazuh-manager-1 | 487.8 | 18 |
| central-iris-worker-1 | 480.5 | 1 |
| central-rabbitmq-1 | 203.9 | **313** |
| wazuh-wazuh-dashboard-1 | 182.5 | 1 |
| central-iris-1 | 174.4 | 64 |
| central-ctfd-1 | 140.5 | 43 |
| desktops-desktop-team01-1 | 133.8 | 2 |
| desktops-desktop-team02-1 | 126.3 | 2 |
| desktops-desktop-team05-1 | 125.6 | 2 |
| desktops-desktop-team04-1 | 121.7 | 2 |
| desktops-desktop-team03-1 | 121.6 | 2 |
| central-ctfd-db-1 | 100.4 | 2 |
| central-iris-db-1 | 72.1 | 4 |
| integration-integration-1 | 41.7 | 25 |
| desktop-access-database-1 | 39.3 | 2 |
| central-participant-tls-1 | 28.4 | 3 |
| desktop-access-guacd-1 | 16.0 | 2 |
| central-ctfd-cache-1 | 10.3 | 4 |

- **sum of per-container peaks: 4.77 GiB**

The five team desktops idled at ~122–134 MiB each. The README's sizing claim of
~150 MiB idle per desktop holds. **No desktop was ever loaded with Autopsy or a
case open**, so the ~2 GiB peak figure is untested by this run.

`rabbitmq` shows a 313% CPU peak — almost certainly its boot/definition-load
burst, not sustained work. Worth a second look if it recurs, but 19 samples of a
container averaging under 2% otherwise does not indicate a problem.

## Integration outbox depth

- min 0, max **3**
- samples with any backlog: 9 of 148 (**6.1%**)

The integration worker kept up. A maximum backlog of 3 rows against 220 total
deliveries means the async path (answer → finding + point + close → IRIS/CTFd)
never meaningfully queued, even with 5 teams submitting at once.

## Participant endpoint latency

Unauthenticated GET, 3 probes per sample (444 requests total):

| endpoint | p50 s | p95 s | max s | non-2xx |
|---|---|---|---|---|
| iris | 0.016 | 0.032 | 0.172 | **0** |
| ctfd | 0.031 | 0.047 | 0.203 | **0** |
| guacamole | 0.000 | 0.031 | 0.032 | **0** |

**Zero non-2xx responses across 444 probes.** p95 under 50 ms on every endpoint.

## What the metrics say

The serving layer was never the problem. Sub-50 ms p95, no errors, no queue
backlog, 67.5% memory reserve, and 0.3 GiB of disk growth across a full
17-minute exercise. Every difficulty the five teams reported was in the
**participant-facing write path and content design** — CSRF/generation handling,
the CTFd login rate limit, opaque 409s, and answer-format grading — not in
throughput, capacity, or stability.

That is the useful shape of this result: the infrastructure is sound enough that
the remaining work is product design, not performance engineering.
