"""Explicit, transactional upgrades. Stop old workers before migrating."""
VERSION = 3


def _v2(con):
    con.execute('ALTER TABLE tickets ADD COLUMN generation INTEGER NOT NULL DEFAULT 0')
    con.execute("ALTER TABLE tickets ADD COLUMN release_files TEXT NOT NULL DEFAULT '[]'")
    for definition in ('ticket TEXT', 'lease TEXT', 'lease_until REAL NOT NULL DEFAULT 0',
                       'retry_at REAL NOT NULL DEFAULT 0', 'created REAL NOT NULL DEFAULT 0'):
        con.execute('ALTER TABLE outbox ADD COLUMN '+definition)
    con.execute('''CREATE TABLE control(id INTEGER PRIMARY KEY CHECK(id=1),
                   provisioned INTEGER NOT NULL DEFAULT 0, export_token TEXT)''')
    con.execute('INSERT INTO control(id) VALUES (1)')
    con.execute('''CREATE TABLE delivery_dependencies(event TEXT REFERENCES outbox(id),
                   prerequisite TEXT REFERENCES outbox(id), PRIMARY KEY(event, prerequisite))''')
    # Preserve the old global delivery order during upgrade; new events use ticket chains.
    import json
    previous = None
    for row in con.execute('SELECT id,payload FROM outbox ORDER BY rowid').fetchall():
        con.execute('UPDATE outbox SET ticket=? WHERE id=?',
                    (json.loads(row['payload'])['ticket'], row['id']))
        if previous:
            con.execute('INSERT INTO delivery_dependencies VALUES (?,?)', (row['id'], previous))
        previous = row['id']
    con.execute('CREATE INDEX outbox_pending ON outbox(done,retry_at,lease_until)')
    con.execute('CREATE INDEX outbox_ticket ON outbox(ticket)')
    con.execute('CREATE INDEX audit_action ON audit(action,id)')
    con.execute('PRAGMA user_version=2')


def _v3(con):
    # Active-site fencing (F01): fenced=1 permanently disables mutations on this
    # site; site_generation orders activations across a local/AWS move.
    con.execute('ALTER TABLE control ADD COLUMN fenced INTEGER NOT NULL DEFAULT 0')
    con.execute('ALTER TABLE control ADD COLUMN site_generation INTEGER NOT NULL DEFAULT 1')
    con.execute('PRAGMA user_version=3')


def migrate(con):
    version = con.execute('PRAGMA user_version').fetchone()[0]
    if version > VERSION:
        raise ValueError('Database was created by a newer release')
    if version < 2:
        _v2(con)
    if version < 3:
        _v3(con)
