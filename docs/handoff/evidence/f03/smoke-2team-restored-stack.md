# F03 load run — NON-CERTIFYING smoke run — host/team count below event profile

- teams/sessions: 2/6, duration 120.0s
- peak working set: 7.15 GiB of 20 GiB host (64.2% reserve)
- outbox depth min/max: [226, 226]

| endpoint | count | failures | p50 s | p95 s |
|---|---|---|---|---|
| ctfd:login | 6 | 0 | 0.297 | 0.313 |
| ctfd:login-page | 6 | 0 | 0.016 | 0.031 |
| ctfd:questions | 149 | 0 | 0.109 | 0.141 |
| ctfd:scoreboard | 38 | 0 | 0.016 | 0.032 |
| ctfd:status | 49 | 0 | 0.062 | 0.078 |
| iris:case | 24 | 0 | 0.031 | 0.032 |
| iris:dashboard | 51 | 0 | 0.031 | 0.047 |
| iris:login | 2 | 0 | 0.188 | 0.203 |
| iris:login-page | 2 | 0 | 0.016 | 0.016 |

| container | peak MiB |
|---|---|
| silent-ridge-n1-central-ctfd-1 | 243.0 |
| silent-ridge-n1-central-ctfd-cache-1 | 20.7 |
| silent-ridge-n1-central-ctfd-db-1 | 114.3 |
| silent-ridge-n1-central-iris-1 | 190.0 |
| silent-ridge-n1-central-iris-db-1 | 52.2 |
| silent-ridge-n1-central-iris-worker-1 | 1636.4 |
| silent-ridge-n1-central-rabbitmq-1 | 170.8 |
| silent-ridge-n1-desktop-access-database-1 | 38.6 |
| silent-ridge-n1-desktop-access-guacamole-1 | 720.3 |
| silent-ridge-n1-desktop-access-guacd-1 | 12.2 |
| silent-ridge-n1-desktops-desktop-team01-1 | 1668.1 |
| silent-ridge-n1-desktops-desktop-team02-1 | 145.5 |
| silent-ridge-n1-integration-integration-1 | 175.3 |
| silent-ridge-n1-wazuh-wazuh-dashboard-1 | 192.7 |
| silent-ridge-n1-wazuh-wazuh-indexer-1 | 1903.6 |
| silent-ridge-n1-wazuh-wazuh-manager-1 | 39.1 |
