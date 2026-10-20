import unittest
from expanded.author import build
from ridge.narrative import contract,final_assessment,participant_context,ticket_context,ticket_delivery
from ridge.web import PAGE


class NarrativeTests(unittest.TestCase):
    def test_contract_covers_every_ticket_once(self):
        data=contract()
        tickets=[ticket for phase in data['phases'] for ticket in phase['tickets']]
        self.assertEqual(tickets,["T%02d" % number for number in range(1,21)])
        self.assertEqual(len(data['roles']),3)
        self.assertIn('fictional',data['fiction_notice'].lower())
        self.assertIn('LANTERN',data['premise'])
        self.assertEqual(data['operational_update']['trigger_after'],
                         ['T%02d' % number for number in range(1,11)])
        self.assertTrue(all(row['ticket'].startswith('T') for row in data['timeline']))
        self.assertIn('LIMITED DISCLOSURE CONFIRMED',final_assessment()['status'])
        self.assertIn('CEDAR',final_assessment()['summary'])

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
        self.assertIsNone(story['conclusion'])
        self.assertIsNone(story['operational_update'])
        self.assertEqual(story['elapsed_display'],'00:00:00')

    def test_midpoint_update_and_verified_timeline_are_completion_gated(self):
        story=participant_context({'team':'team-01','elapsed_seconds':3661,'tickets':[
            {'id':'T%02d' % number,'status':'complete'} for number in range(1,11)]})
        self.assertEqual(story['operational_update']['id'],'scope-expansion')
        self.assertEqual(story['elapsed_display'],'01:01:01')
        self.assertTrue(story['timeline'])
        self.assertTrue(all(row['ticket'] in {'T%02d' % number for number in range(1,11)}
                            for row in story['timeline']))
        self.assertFalse(any(row['ticket']=='T11' for row in story['timeline']))

    def test_question_sets_activate_local_analysis_workspaces(self):
        snapshot={'tickets':[{'id':'T13','status':'active'},{'id':'T20','status':'active'}]}
        story=participant_context(snapshot,[{'ticket':'T13'},{'ticket':'T20'}])
        self.assertTrue(story['correlation_workspace'])
        self.assertTrue(story['capstone_workspace'])

    def test_conclusion_is_revealed_only_after_all_twenty_stages_complete(self):
        before=participant_context({'tickets':[{'id':'T%02d' % number,'status':'complete'}
                                                       for number in range(1,20)]})
        after=participant_context({'tickets':[{'id':'T%02d' % number,'status':'complete'}
                                                      for number in range(1,21)]})
        self.assertIsNone(before['conclusion'])
        self.assertEqual(after['conclusion']['status'],final_assessment()['status'])
        self.assertIn('198.51.100.77',after['conclusion']['summary'])

    def test_page_renders_mission_phase_and_handoff_contract(self):
        for text in ('story.fiction_notice','story.participant_role','Why this question matters',
                     'story.tools.items()','context.handoff','Shared progress',
                     'final-assessment','story.conclusion.actions','Room-wide closing brief ready',
                     'operational-update','Verified incident chronology','correlation-workspace',
                      'capstone-workspace','formatElapsed','localStorage','current-questions',
                      'completed-history','NEW EVIDENCE RELEASED','acknowledgeUpdate'):
            self.assertIn(text,PAGE)


if __name__=='__main__':unittest.main()
