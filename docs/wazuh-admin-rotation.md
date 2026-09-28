# Wazuh indexer admin password rotation

The `admin` hash in `wazuh_config/wazuh_indexer/internal_users.yml` is a
**bootstrap copy**. After the indexer initializes, the live credential is in
its security index. Editing the file and restarting the container does not
rotate the active password. If the runtime's `secrets/wazuh_admin` is then
changed, controller requests fail with HTTP 401 while the old password still
works.

Schedule this as maintenance with the exercise paused. Take a verified private
backup of the runtime and indexer data first. Keep the old password available
until the new password has been tested; do not publish either password or its
hash in a ticket or log.

1. Identify the current indexer endpoint from the runtime's `local.json` and
   generated `wazuh.env`, and verify the old `admin` credential against the
   indexer over HTTPS using `runtime/wazuh-certs/root-ca.pem`. The dashboard
   URL and the Wazuh **server** API are different services and are not the
   indexer security API.
2. Change the **live** indexer account through Wazuh's supported
   `PUT /_plugins/_security/api/account` endpoint using the old password and
   the new password. Supply the new password in the JSON body and authenticate
   as `admin`. Use a private TLS client that verifies the local CA and does not
   put either password in a shell command line. Follow Wazuh's
   [indexer API password procedure](https://documentation.wazuh.com/current/user-manual/indexer-api/securing-indexer-api.html).
3. Before updating any local secret, verify the new credential can query the
   indexer and the old credential is rejected. If this check fails, stop: the
   security index has not been rotated. A container restart will not fix it.
4. Generate the matching password hash with the **pinned 4.9.2 indexer**
   `hash.sh` tool and update only the `admin.hash` entry in the private
   `wazuh_config/wazuh_indexer/internal_users.yml`. Update
   `runtime/secrets/wazuh_admin` to `admin:<new password>` and any generated
   dashboard, manager, or Filebeat credential settings that use this account.
   Keep the config, secret, and running security index together in the backup.
5. Reconcile the stack with `ridge.deploy up`, then verify authenticated
   indexer access, dashboard login, Filebeat ingestion, and participant
   read-only access. Record only status codes and timestamps in the event log.

Do **not** apply an entire stale `internal_users.yml` with
`securityadmin.sh -cd` as a shortcut. Wazuh's
[Docker guidance](https://documentation.wazuh.com/current/deployment-options/docker/changing-default-password.html)
warns that users missing from the file are deleted by a full reload; this
exercise creates participant users through the security API after bootstrap.
If the live rotation succeeds but a later step fails, recover from the private
backup or repair the remaining settings with the new live password. Do not
silently restore only the old file or only the old secret.
