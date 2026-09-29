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
The commands below use Git Bash `\` line continuations. In PowerShell, put
each `docker` command on one line without the backslashes.

1. Identify the current indexer endpoint from the runtime's `local.json` and
   generated `wazuh.env`, and verify the old `admin` credential against the
   indexer over HTTPS using `runtime/wazuh-certs/root-ca.pem`. The dashboard
   URL and the Wazuh **server** API are different services.
2. Export the **live** security configuration before touching its users. Run
   the pinned indexer's `securityadmin.sh` with its generated admin certificate:

   ```text
   docker exec -e JAVA_HOME=/usr/share/wazuh-indexer/jdk <INDEXER_CONTAINER> \
     bash /usr/share/wazuh-indexer/plugins/opensearch-security/tools/securityadmin.sh \
     -backup /tmp/rotation-backup -icl -nhnv \
     -cacert /usr/share/wazuh-indexer/certs/root-ca.pem \
     -cert /usr/share/wazuh-indexer/certs/admin.pem \
     -key /usr/share/wazuh-indexer/certs/admin-key.pem -h localhost -p 9200
   docker cp <INDEXER_CONTAINER>:/tmp/rotation-backup <PRIVATE_BACKUP_DIR>
   ```

   Protect this export like the recovery set: it contains password hashes.
   Confirm its `internal_users.yml` includes every current exercise user,
   especially the participant reader and writer. The generated `admin` user
   is **reserved** in the pinned image. A live `PUT
   /_plugins/_security/api/account` returned HTTP 403, `Resource 'admin' is
   reserved`, in the Windows rehearsal. [OpenSearch reserves such users from
   REST modification](https://docs.opensearch.org/latest/security/access-control/api/).
3. Generate a new strong password privately. Use the pinned 4.9.2 indexer's
   `hash.sh` with password input on stdin, and on Windows send **bytes with LF**;
   text-mode `subprocess` input can append CR and hash the wrong password.
   Starting from the **live export**, replace only the `admin.hash` line in a
   separate copy of `internal_users.yml`. Verify that the file retains all
   exported users and that exactly one line changed. Do not put the plaintext
   password in a shell command, ticket, or log.
4. Copy the prepared full user file into the indexer container. Apply only the
   `internalusers` configuration type using the same generated admin certificate:

   ```text
   docker cp <PREPARED_INTERNAL_USERS_YML> <INDEXER_CONTAINER>:/tmp/rotation-users.yml
   docker exec -e JAVA_HOME=/usr/share/wazuh-indexer/jdk <INDEXER_CONTAINER> \
     bash /usr/share/wazuh-indexer/plugins/opensearch-security/tools/securityadmin.sh \
     -f /tmp/rotation-users.yml -t internalusers -icl -nhnv \
     -cacert /usr/share/wazuh-indexer/certs/root-ca.pem \
     -cert /usr/share/wazuh-indexer/certs/admin.pem \
     -key /usr/share/wazuh-indexer/certs/admin-key.pem -h localhost -p 9200
   ```

   [OpenSearch documents](https://docs.opensearch.org/latest/security/configuration/security-admin/)
   that even a single-file `internalusers` reload replaces that entire user
   section. Using the live export preserves users created later through the
   API; a stale vendored file would delete them.
5. Before updating any local secret, verify the new credential can query the
   indexer, the old credential returns HTTP 401, the participant reader and
   writer still authenticate, and the exercise document count is unchanged.
   If this check fails, stop and recover from the private export and verified
   recovery set. A container restart alone will not repair the security index.
6. Update only the `admin.hash` entry in the private runtime bootstrap
   `runtime/wazuh-config/internal_users.yml` with the same new hash, then
   atomically update `runtime/secrets/wazuh_admin` to `admin:<new password>`.
   Check generated dashboard, manager, and Filebeat settings for any additional
   use of this account and update them if present. Keep the config, secret,
   live security index, and the pre-rotation backup together.
7. Reconcile the stack with `ridge.deploy up` from the matching release source,
   then verify indexer access, dashboard login, Filebeat ingestion, and
   participant read-only access. Record only status codes and timestamps in
   the event log.

Do **not** apply an entire stale `internal_users.yml` with
`securityadmin.sh -cd` as a shortcut. Wazuh's
[Docker guidance](https://documentation.wazuh.com/current/deployment-options/docker/changing-default-password.html)
warns that users missing from the file are deleted by a full reload; this
exercise creates participant users through the security API after bootstrap.
If the live rotation succeeds but a later step fails, recover from the private
backup or repair the remaining settings with the new live password. Do not
silently restore only the old file or only the old secret.
