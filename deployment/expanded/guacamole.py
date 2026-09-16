"""Generate idempotent private Guacamole 1.5.5 provisioning SQL.

Apply only to a newly initialized official Guacamole 1.5.5 schema. The input
credential file maps teams to {username,password} and desktops to {password}.
Do not commit this file's output or its credential input.

``reconcile`` emits upserts so a repeated run creates no duplicate connection,
entity, user or permission rows and never silently rotates an existing login.
The upstream default administrator account is disabled.

LIVE ACCEPTANCE BLOCKED: no Docker/Linux host is available, so the SQL has not
been applied to a real Guacamole database; session isolation needs a live test.
"""
import argparse
import hashlib
import json
from pathlib import Path


def quote(value):
    return "'"+str(value).replace("'","''")+"'"


def _desktops(config):
    desktops={d['id']:d for d in config['desktops']}
    if len(desktops)!=len(config['desktops']) or not desktops:
        raise ValueError('Unique configured desktops required')
    for id,d in desktops.items():
        if type(d['shared']) is not bool or not isinstance(d['max_connections'],int) or d['max_connections']<1:
            raise ValueError('Explicit desktop sharing and positive connection limit required')
        if not d.get('address'):
            raise ValueError('Desktop address required for '+id)
    return desktops


def _teams(config, desktops):
    if len({t['id'] for t in config['teams']})!=len(config['teams']) or not config['teams']:
        raise ValueError('At least one unique team required')
    for team in config['teams']:
        if team['desktop'] not in desktops:
            raise ValueError('Team desktop missing')
    return config['teams']


def reconcile(config,credentials):
    """Return idempotent SQL. Re-running converges without duplicate rows."""
    desktops=_desktops(config)
    teams=_teams(config,desktops)
    sql=['BEGIN;']
    for id,d in desktops.items():
        maximum=d['max_connections'] if d['shared'] else 1
        vnc=credentials['desktops'][id]['password']
        if not vnc:
            raise ValueError('Desktop VNC password required for '+id)
        sql.append('INSERT INTO guacamole_connection(connection_name,protocol,max_connections,max_connections_per_user) VALUES ('+
                   ','.join([quote(id),quote('vnc'),str(maximum),str(maximum)])+
                   ') ON CONFLICT (connection_name) DO UPDATE SET protocol=EXCLUDED.protocol,'+
                   'max_connections=EXCLUDED.max_connections,max_connections_per_user=EXCLUDED.max_connections_per_user;')
        for key,value in {'hostname':d['address'],'port':'5901','password':vnc,
                          'read-only':'false','clipboard-encoding':'UTF-8'}.items():
            sql.append('INSERT INTO guacamole_connection_parameter(connection_id,parameter_name,parameter_value) SELECT connection_id,'+
                       quote(key)+','+quote(value)+' FROM guacamole_connection WHERE connection_name='+quote(id)+
                       ' ON CONFLICT (connection_id,parameter_name) DO UPDATE SET parameter_value=EXCLUDED.parameter_value;')
    names=set()
    for team in teams:
        credential=credentials['teams'][team['id']]
        name=credential['username'];password=credential['password']
        if name in names or len(password)<20:raise ValueError('Unique usernames and strong generated passwords required')
        names.add(name)
        digest=hashlib.sha256(password.encode()).hexdigest()
        sql.append('INSERT INTO guacamole_entity(name,type) VALUES ('+quote(name)+",'USER') ON CONFLICT (name,type) DO NOTHING;")
        sql.append("INSERT INTO guacamole_user(entity_id,password_hash,password_salt,password_date) SELECT entity_id,decode("+
                   quote(digest)+",'hex'),NULL,CURRENT_TIMESTAMP FROM guacamole_entity WHERE name="+quote(name)+
                   " AND type='USER' ON CONFLICT (entity_id) DO NOTHING;")
        sql.append("INSERT INTO guacamole_connection_permission(entity_id,connection_id,permission) SELECT e.entity_id,c.connection_id,'READ' FROM guacamole_entity e,guacamole_connection c WHERE e.name="+
                   quote(name)+" AND e.type='USER' AND c.connection_name="+quote(team['desktop'])+" ON CONFLICT DO NOTHING;")
    # Remove upstream default administrator access.
    sql.append("UPDATE guacamole_user SET disabled=TRUE WHERE entity_id IN "+
               "(SELECT entity_id FROM guacamole_entity WHERE name='guacadmin' AND type='USER');")
    sql.append('COMMIT;')
    return '\n'.join(sql)+'\n'


def generate(config,credentials):
    return reconcile(config,credentials)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('config',type=Path);p.add_argument('credentials',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args()
    with a.output.open('x',encoding='utf-8') as f:f.write(reconcile(json.loads(a.config.read_text()),json.loads(a.credentials.read_text())))
