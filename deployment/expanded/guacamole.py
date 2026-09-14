"""Generate private PostgreSQL provisioning SQL from arbitrary team/VM mappings.

Apply only to a newly initialized Guacamole 1.5.5 database. The input credential
file maps teams to {username,password} and desktops to {password}. Do not commit
either this file's output or its credential input.
"""
import argparse
import hashlib
import json
from pathlib import Path


def quote(value):
    return "'"+str(value).replace("'","''")+"'"


def generate(config,credentials):
    desktops={d['id']:d for d in config['desktops']}
    if len(desktops)!=len(config['desktops']) or not desktops:
        raise ValueError('Unique configured desktops required')
    if len({t['id'] for t in config['teams']})!=len(config['teams']):
        raise ValueError('Duplicate team ID')
    sql=['BEGIN;']
    for id,d in desktops.items():
        if type(d['shared']) is not bool or not isinstance(d['max_connections'],int) or d['max_connections']<1:
            raise ValueError('Explicit desktop sharing and positive connection limit required')
        maximum=d['max_connections'] if d['shared'] else 1
        sql.append('INSERT INTO guacamole_connection(connection_name,protocol,max_connections,max_connections_per_user) VALUES ('+
                   ','.join([quote(id),quote('vnc'),str(maximum),str(maximum)])+');')
        for key,value in {'hostname':d['address'],'port':'5901','password':credentials['desktops'][id]['password'],
                          'read-only':'false','clipboard-encoding':'UTF-8'}.items():
            sql.append('INSERT INTO guacamole_connection_parameter(connection_id,parameter_name,parameter_value) SELECT connection_id,'+
                       quote(key)+','+quote(value)+' FROM guacamole_connection WHERE connection_name='+quote(id)+';')
    names=set()
    for team in config['teams']:
        if team['desktop'] not in desktops:raise ValueError('Team desktop missing')
        credential=credentials['teams'][team['id']]
        name=credential['username'];password=credential['password']
        if name in names or len(password)<20:raise ValueError('Unique usernames and strong generated passwords required')
        names.add(name)
        digest=hashlib.sha256(password.encode()).hexdigest()
        sql.append('INSERT INTO guacamole_entity(name,type) VALUES ('+quote(name)+",'USER');")
        sql.append("INSERT INTO guacamole_user(entity_id,password_hash,password_salt,password_date) SELECT entity_id,decode("+
                   quote(digest)+",'hex'),NULL,CURRENT_TIMESTAMP FROM guacamole_entity WHERE name="+quote(name)+" AND type='USER';")
        sql.append("INSERT INTO guacamole_connection_permission(entity_id,connection_id,permission) SELECT e.entity_id,c.connection_id,'READ' FROM guacamole_entity e,guacamole_connection c WHERE e.name="+
                   quote(name)+" AND e.type='USER' AND c.connection_name="+quote(team['desktop'])+';')
    sql.append('COMMIT;')
    return '\n'.join(sql)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('config',type=Path);p.add_argument('credentials',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args()
    with a.output.open('x',encoding='utf-8') as f:f.write(generate(json.loads(a.config.read_text()),json.loads(a.credentials.read_text())))
