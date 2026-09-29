import unittest
from expanded.author import build
from ridge.narrative import contract,participant_context,ticket_context,ticket_delivery
from ridge.web import PAGE


class NarrativeTests(unittest.TestCase):
    def test_contract_covers_every_ticket_once(self):
        data=contract()
        tickets=[ticket for phase in data['phases'] for ticket in phase['tickets']]
        self.assertEqual(tickets,["T%02d" % number for number in range(1,21)])
        self.assertEqual(len(data['roles']),3)
        self.assertIn('fictional',data['fiction_notice'].lower())
        self.assertIn('LANTERN',data['premise'])

    def test_authored_content_uses_the_shared_contract(self):
        for ticket in build():
            context=ticket_context(ticket['id'])
            for field in ('phase','briefing','stakes','handoff'):
                self.assertEqual(ticket[field],context[field])
            delivery=ticket_delivery(ticket['id'],ticket['title'])
            self.assertIn(context['phase_title'],delivery['description'])
            self.assertIn('Handoff:',delivery['description'])

    def test_participant_context_reports_progress_without_answers(self):
        snapshot={'tickets':[{'id':'T01','status':'complete'},{'id':'T02','status':'available'}]}
        story=participant_context(snapshot,[{'id':'T01-Q1'}])
        self.assertEqual(story['completed'],1)
        self.assertEqual(story['total'],20)
        self.assertEqual(story['question_count'],1)
        self.assertNotIn('answer',story)

    def test_page_renders_mission_phase_and_handoff_contract(self):
        for text in ('story.fiction_notice','story.participant_role','Why this question matters',
                     'story.tools.items()','context.handoff','Shared progress'):
            self.assertIn(text,PAGE)


if __name__=='__main__':unittest.main()
