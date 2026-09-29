"""Versioned participant narrative shared by the queue, questions, and IRIS tasks."""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def contract():
    data=json.loads(Path(__file__).with_name('scenario_narrative_v1.json').read_text(encoding='utf-8'))
    required=('title','fiction_notice','premise','discovery','stakes','participant_role',
              'operating_rule','roles','tools','phases','completion')
    missing=[field for field in required if not data.get(field)]
    if data.get('schema')!=1 or missing:
        raise ValueError('Invalid scenario narrative contract: '+', '.join(missing or ['schema']))
    expected={'T%02d' % number for number in range(1,21)}
    tickets=[ticket for phase in data['phases'] for ticket in phase.get('tickets',[])]
    if set(tickets)!=expected or len(tickets)!=len(set(tickets)):
        raise ValueError('Scenario narrative phases must cover T01 through T20 exactly once')
    return data


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
    return {'title':data['title'],'fiction_notice':data['fiction_notice'],
            'premise':data['premise'],'discovery':data['discovery'],'stakes':data['stakes'],
            'participant_role':data['participant_role'],'operating_rule':data['operating_rule'],
            'roles':data['roles'],'tools':data['tools'],'ticket_context':mapping,
            'completion':data['completion'],'completed':sum(t.get('status')=='complete' for t in visible),
            'total':sum(len(phase['tickets']) for phase in data['phases']),
            'question_count':len(questions or ())}
