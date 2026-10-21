"""Explicit, transactional upgrades. Stop old workers before migrating."""
VERSION = 6


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


def _v4(con):
    """Team-local clocks and durable paid-walkthrough accounting.

    Existing answer rows keep their historical one-point value.  New runs use
    four-point questions so a walkthrough can have an exact 75% cost while
    remaining compatible with CTFd's integer score model.
    """
    tables = {row[0] for row in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if 'teams' in tables:
        columns = {row[1] for row in con.execute('PRAGMA table_info(teams)')}
        if 'started_at' not in columns:
            con.execute('ALTER TABLE teams ADD COLUMN started_at TEXT')
        if 'audit' in tables:
            # Dynamic teams already have a precise registration audit event.
            # The original roster starts at the first run event, preserving
            # old runs.  Minimal/partial databases simply remain unstarted.
            con.execute('''UPDATE teams SET started_at=(
                SELECT timestamp FROM audit
                WHERE actor=teams.id AND action='register_team'
                ORDER BY id LIMIT 1) WHERE started_at IS NULL AND EXISTS (
                SELECT 1 FROM audit WHERE actor=teams.id AND action='register_team')''')
            con.execute("""UPDATE teams SET started_at=(
                SELECT timestamp FROM audit WHERE action='running' ORDER BY id LIMIT 1)
                WHERE started_at IS NULL""")
    if 'answers' in tables:
        columns = {row[1] for row in con.execute('PRAGMA table_info(answers)')}
        if 'value' not in columns:
            con.execute('ALTER TABLE answers ADD COLUMN value INTEGER NOT NULL DEFAULT 1')
    con.execute('''CREATE TABLE IF NOT EXISTS hint_usage(
        team TEXT NOT NULL REFERENCES teams(id),
        question TEXT NOT NULL REFERENCES questions(id),
        unlocked_at TEXT NOT NULL,
        PRIMARY KEY(team, question))''')
    con.execute('PRAGMA user_version=4')


def _v5(con):
    """Completion-assessment release marker.

    The assessment itself lives in the versioned narrative contract and uses
    the existing audit/outbox tables. State.migrate performs the idempotent
    backfill after this transactional version step so completed live runs gain
    the new ending without rewriting participant answers or scores.
    """
    con.execute('PRAGMA user_version=5')


def _v6(con):
    """Independent per-team ticket progression and answer credit.

    ``tickets`` and ``questions`` remain immutable shared content.  Mutable
    claim/completion state moves to ``team_tickets`` and answers are keyed by
    both team and question.  Existing runs are preserved: the former global
    state is copied to every existing team, which is exact for the one-team
    rehearsals that predate this schema and fail-safe for an already-shared run.
    """
    tables = {row[0] for row in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if {'teams', 'tickets'} <= tables:
        con.execute('''CREATE TABLE IF NOT EXISTS team_tickets(
            team TEXT NOT NULL REFERENCES teams(id),
            ticket TEXT NOT NULL REFERENCES tickets(id),
            status TEXT NOT NULL CHECK(status IN ('locked','available','active','complete')),
            generation INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(team,ticket))''')
        ticket_columns = {row[1] for row in con.execute('PRAGMA table_info(tickets)')}
        if {'status', 'owner', 'generation'} <= ticket_columns:
            con.execute('''INSERT OR IGNORE INTO team_tickets(team,ticket,status,generation)
                SELECT teams.id,tickets.id,
                  CASE WHEN tickets.status='active' AND tickets.owner<>teams.id THEN 'available'
                       ELSE tickets.status END,
                  tickets.generation
                FROM teams CROSS JOIN tickets''')
    answer_columns = [row[1] for row in con.execute('PRAGMA table_info(answers)')]
    if answer_columns:
        pk = {row[1]: row[5] for row in con.execute('PRAGMA table_info(answers)')}
        if pk.get('team', 0) == 0:
            con.execute('ALTER TABLE answers RENAME TO answers_global_v5')
            con.execute('''CREATE TABLE answers(
                team TEXT NOT NULL REFERENCES teams(id),
                question TEXT NOT NULL REFERENCES questions(id),
                timestamp TEXT NOT NULL,
                event TEXT UNIQUE NOT NULL,
                value INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY(team,question))''')
            con.execute('''INSERT INTO answers(team,question,timestamp,event,value)
                SELECT team,question,timestamp,event,value FROM answers_global_v5''')
            con.execute('DROP TABLE answers_global_v5')
    outbox_columns = {row[1] for row in con.execute('PRAGMA table_info(outbox)')}
    if 'team' not in outbox_columns:
        con.execute('ALTER TABLE outbox ADD COLUMN team TEXT')
    if 'team_tickets' in {row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}:
        con.execute('CREATE INDEX IF NOT EXISTS team_tickets_status ON team_tickets(team,status)')
    if 'answers' in {row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}:
        con.execute('CREATE INDEX IF NOT EXISTS answers_question ON answers(question)')
    con.execute('PRAGMA user_version=6')


def migrate(con):
    version = con.execute('PRAGMA user_version').fetchone()[0]
    if version > VERSION:
        raise ValueError('Database was created by a newer release')
    if version < 2:
        _v2(con)
    if version < 3:
        _v3(con)
    if version < 4:
        _v4(con)
    if version < 5:
        _v5(con)
    if version < 6:
        _v6(con)
