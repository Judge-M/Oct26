"""Versioned participant narrative shared by the queue, questions, and IRIS tasks."""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path


TICKET_ROUTES = {
    'T01': {'tools': ['Wireshark'], 'evidence': ['/evidence/network/sensor.pcap', '/evidence/endpoint/events.csv']},
    'T02': {'tools': ['Wireshark'], 'evidence': ['/evidence/network/dns.pcap']},
    'T03': {'tools': ['Autopsy'], 'evidence': ['/evidence/browser/downloads.csv']},
    'T04': {'tools': ['Autopsy'], 'evidence': ['/evidence/endpoint/events.csv']},
    'T05': {'tools': ['Autopsy'], 'evidence': ['/evidence/disk/WS17-fat16.img']},
    'T06': {'tools': ['Wazuh'], 'evidence': ['/evidence/wazuh/telemetry.jsonl']},
    'T07': {'tools': ['Wazuh'], 'evidence': ['/evidence/identity/late-auth.csv', '/evidence/identity/policy.txt', '/evidence/wazuh/telemetry.jsonl']},
    'T08': {'tools': ['Autopsy'], 'evidence': ['/evidence/server/access.csv']},
    'T09': {'tools': ['Evidence file manager'], 'evidence': ['/evidence/server/version-comparison.csv']},
    'T10': {'tools': ['Wazuh'], 'evidence': ['/evidence/wazuh/telemetry.jsonl']},
    'T11': {'tools': ['Wazuh'], 'evidence': ['/evidence/wazuh/telemetry.jsonl']},
    'T12': {'tools': ['Wazuh'], 'evidence': ['/evidence/server/collection.txt', '/evidence/wazuh/telemetry.jsonl']},
    'T13': {'tools': ['Autopsy'], 'evidence': ['/evidence/prepared/windows-process.json']},
    'T14': {'tools': ['Autopsy'], 'evidence': ['/evidence/prepared/windows-task.json']},
    'T15': {'tools': ['Autopsy'], 'evidence': ['/evidence/prepared/memory-processes.json']},
    'T16': {'tools': ['Autopsy'], 'evidence': ['/evidence/prepared/windows-connections.json']},
    'T17': {'tools': ['Cutter'], 'evidence': ['/evidence/binary/brief-viewer-training']},
    'T18': {'tools': ['Cutter'], 'evidence': ['/evidence/binary/brief-viewer-training']},
    'T19': {'tools': ['Evidence file manager'], 'evidence': ['/evidence/network/dlp-metadata.json']},
    'T20': {'tools': ['Wazuh'], 'evidence': ['/evidence/wazuh/telemetry.jsonl']},
}


@lru_cache(maxsize=1)
def contract():
    data=json.loads(Path(__file__).with_name('scenario_narrative_v1.json').read_text(encoding='utf-8'))
    required=('title','fiction_notice','premise','discovery','stakes','participant_role',
              'operating_rule','roles','tools','operational_update','timeline','phases',
              'completion','conclusion')
    missing=[field for field in required if not data.get(field)]
    if data.get('schema')!=1 or missing:
        raise ValueError('Invalid scenario narrative contract: '+', '.join(missing or ['schema']))
    expected={'T%02d' % number for number in range(1,21)}
    tickets=[ticket for phase in data['phases'] for ticket in phase.get('tickets',[])]
    if set(tickets)!=expected or len(tickets)!=len(set(tickets)):
        raise ValueError('Scenario narrative phases must cover T01 through T20 exactly once')
    update=data['operational_update']
    triggers=set(update.get('trigger_after') or ())
    update_required=('id','classification','title','sender','message','significance',
                     'available_now','decision_requirement','priorities','guardrail')
    if any(not update.get(field) for field in update_required) or not triggers <= expected:
        raise ValueError('Scenario narrative operational update is incomplete')
    timeline=data['timeline']
    if any(not row.get('time') or row.get('ticket') not in expected or
           not row.get('event') or not row.get('source') for row in timeline):
        raise ValueError('Scenario narrative timeline is incomplete')
    conclusion=data['conclusion']
    conclusion_required=('status','summary','confirmed','not_established','unresolved',
                         'actions','announcement')
    if any(not conclusion.get(field) for field in conclusion_required):
        raise ValueError('Scenario narrative conclusion is incomplete')
    return data


def final_assessment():
    """Return the canonical post-capstone assessment used by UI and IRIS."""
    return contract()['conclusion']


def ticket_context(ticket):
    for phase in contract()['phases']:
        if ticket in phase['tickets']:
            return {'phase':phase['id'],'phase_title':phase['title'],
                    'briefing':phase['briefing'],'stakes':phase['stakes'],
                    'handoff':phase['handoff']}
    return {'phase':'orientation','phase_title':'Investigation orientation',
            'briefing':contract()['participant_role'],'stakes':contract()['stakes'],
            'handoff':contract()['operating_rule']}


def ticket_delivery(ticket,title):
    context=ticket_context(ticket)
    description=(context['phase_title']+'\n'+context['briefing']+'\nWhy now: '+
                 context['stakes']+'\nHandoff: '+context['handoff']+
                 '\nClaim ownership through /silent-ridge. Correct answers publish cited findings automatically.')
    return {'ticket':ticket,'title':title,'description':description,'phase':context['phase']}


def participant_context(snapshot,questions=()):
    data=contract()
    mapping={ticket:ticket_context(ticket) for phase in data['phases'] for ticket in phase['tickets']}
    visible=list(snapshot.get('tickets',[]))
    complete_ids={t['id'] for t in visible if t.get('status')=='complete'}
    completed=len(complete_ids)
    total=sum(len(phase['tickets']) for phase in data['phases'])
    update=data['operational_update']
    update_ready=set(update['trigger_after']) <= complete_ids
    question_tickets={q.get('ticket') for q in questions or ()}
    elapsed=max(float(snapshot.get('elapsed_seconds') or 0),0)
    hours,rem=divmod(int(elapsed),3600)
    minutes,seconds=divmod(rem,60)
    return {'title':data['title'],'fiction_notice':data['fiction_notice'],
            'premise':data['premise'],'discovery':data['discovery'],'stakes':data['stakes'],
            'participant_role':data['participant_role'],'operating_rule':data['operating_rule'],
            'roles':data['roles'],'tools':data['tools'],'ticket_context':mapping,
            'ticket_routes':TICKET_ROUTES,
            'completion':data['completion'],'completed':completed,'total':total,
            'operational_update':update if update_ready and completed<total else None,
            'timeline':[row for row in data['timeline'] if row['ticket'] in complete_ids],
            'correlation_workspace':bool(question_tickets & {'T13','T14','T15','T16'}),
            'capstone_workspace':'T20' in question_tickets and completed<total,
            'elapsed_display':('%02d:%02d:%02d' % (hours,minutes,seconds)),
            'activity_complete':completed==total,
            # Do not ship the conclusion in pre-completion HTML. It is a reveal,
            # not a hidden client-side element that curious participants can read.
            'conclusion':data['conclusion'] if completed==total else None,
            'question_count':len(questions or ())}

