# F03 load run — NON-CERTIFYING smoke run — host/team count below event profile

- teams/sessions: 2/6, duration 180.0s
- peak working set: 6.36 GiB of 20 GiB host (68.2% reserve)
- outbox depth min/max: [15, 15]

| endpoint | count | failures | p50 s | p95 s |
|---|---|---|---|---|
| ctfd:login | 6 | 0 | 0.281 | 0.375 |
| ctfd:login-page | 6 | 0 | 0.016 | 0.031 |
| ctfd:questions | 218 | 0 | 0.109 | 0.125 |
| ctfd:scoreboard | 53 | 0 | 0.016 | 0.032 |
| ctfd:status | 67 | 0 | 0.062 | 0.063 |
| iris:case | 35 | 0 | 0.016 | 0.032 |
| iris:dashboard | 72 | 0 | 0.031 | 0.047 |
| iris:login | 2 | 0 | 0.187 | 0.203 |
| iris:login-page | 2 | 0 | 0.0 | 0.016 |

| container | peak MiB |
|---|---|
| silent-ridge-dress-central-ctfd-1 | 213.1 |
| silent-ridge-dress-central-ctfd-cache-1 | 11.9 |
| silent-ridge-dress-central-ctfd-db-1 | 133.8 |
| silent-ridge-dress-central-iris-1 | 172.2 |
| silent-ridge-dress-central-iris-db-1 | 39.4 |
| silent-ridge-dress-central-iris-worker-1 | 2562.0 |
| silent-ridge-dress-central-rabbitmq-1 | 239.4 |
| silent-ridge-dress-desktop-access-database-1 | 61.5 |
| silent-ridge-dress-desktop-access-guacamole-1 | 534.8 |
| silent-ridge-dress-desktop-access-guacd-1 | 12.3 |
| silent-ridge-dress-desktops-desktop-team01-1 | 130.9 |
| silent-ridge-dress-desktops-desktop-team02-1 | 171.1 |
| silent-ridge-dress-integration-integration-1 | 41.7 |
| silent-ridge-dress-wazuh-wazuh-dashboard-1 | 270.5 |
| silent-ridge-dress-wazuh-wazuh-indexer-1 | 1774.6 |
| silent-ridge-dress-wazuh-wazuh-manager-1 | 143.6 |
