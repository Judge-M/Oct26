"""Issue #194: the queue must explain why the claim form is absent in every gate-off state."""
import unittest
from ridge.web import PAGE,queue_state


def snapshot(mode='running',team='team-01',tickets=()):
    return {'mode':mode,'team':team,'tickets':list(tickets)}


def ticket(ticket_id,status='available',owner=None,iris_id=100):
    return {'id':ticket_id,'title':ticket_id,'subject':'svc','owner':owner,
            'status':status,'iris_id':iris_id,'generation':1}


class QueueStateTests(unittest.TestCase):
    def test_claimable_ticket_has_no_note_and_is_named_as_available(self):
        state=queue_state(snapshot(tickets=[ticket('T01')]))
        self.assertEqual(state['claimable'],['T01'])
        self.assertEqual(state['notes'],{})
        self.assertIn('Available to claim: T01',state['status'])

    def test_paused_exercise_explains_closed_claiming(self):
        state=queue_state(snapshot(mode='paused',tickets=[ticket('T01')]))
        self.assertTrue(state['paused'])
        self.assertEqual(state['claimable'],[])
        self.assertIn('paused',state['status'])
        self.assertIn('paused',state['notes']['T01'])

    def test_ticket_claimed_by_another_team_names_the_owner(self):
        state=queue_state(snapshot(tickets=[ticket('T02','active','team-02')]))
        self.assertIn('team-02',state['notes']['T02'])
        self.assertIn('T02 (team-02)',state['status'])
        self.assertIn('normal queue state',state['status'])

    def test_held_ticket_is_explained_and_not_offered_as_claimable(self):
        state=queue_state(snapshot(tickets=[ticket('T03','active','team-01')]))
        self.assertEqual(state['held'],['T03'])
        self.assertEqual(state['claimable'],[])
        self.assertIn('You hold',state['notes']['T03'])
        self.assertIn('You hold: T03',state['status'])

    def test_preparing_ticket_explains_pending_iris_delivery(self):
        state=queue_state(snapshot(tickets=[ticket('T04',iris_id=None)]))
        self.assertEqual(state['preparing'],['T04'])
        self.assertIn('IRIS',state['notes']['T04'])
        self.assertIn('preparing in IRIS: T04',state['status'])

    def test_all_complete_says_the_exercise_is_over_not_broken(self):
        state=queue_state(snapshot(tickets=[ticket('T01','complete'),ticket('T02','complete','team-02')]))
        self.assertTrue(state['complete'])
        self.assertIn('Assessment complete',state['status'])
        self.assertIn('LIMITED DISCLOSURE CONFIRMED',state['status'])
        self.assertIn('not an outage',state['status'])
        self.assertIn('Complete',state['notes']['T01'])

    def test_empty_queue_names_why_nothing_can_be_claimed(self):
        state=queue_state(snapshot(team='team-09',tickets=[ticket('T01','active','team-02'),
                                                           ticket('T02',iris_id=None),
                                                           ticket('T03','complete')]))
        self.assertIn('You hold no ticket',state['status'])
        for fragment in ('T01 (team-02)','preparing in IRIS: T02','complete: T03'):
            self.assertIn(fragment,state['status'])

    def test_page_template_renders_the_explanations(self):
        for text in ('id="queue-status"','Progress: %s of %s questions answered',
                     'All tickets for your team',
                     'All unfinished tickets are open to your team'):
            self.assertIn(text,PAGE)

    def test_page_provides_team_local_iris_status_controls(self):
        self.assertIn('Four-person team workflow',PAGE)
        self.assertIn('name="action" value="work_status"',PAGE)
        self.assertIn("('working','Working')",PAGE)
        self.assertIn("('needs_review','Needs review')",PAGE)
        self.assertIn('never hide questions or limit parallel work',PAGE)
        self.assertNotIn('/case/tasks?cid=',PAGE)
        self.assertIn('IRIS incident queue',PAGE)
        self.assertIn("Your team's status:",PAGE)
        self.assertIn('Live scoreboard display',PAGE)
        self.assertIn('{{ctfd}}/scoreboard',PAGE)
        self.assertIn('<strong>Start here</strong>',PAGE)
        self.assertIn('for step in route.directions',PAGE)
        self.assertIn('How these tools fit together',PAGE)
        self.assertIn('Follow this loop for every ticket',PAGE)
        self.assertIn('choose work from the full IRIS queue',PAGE)
        self.assertIn('return to IRIS to see the verified finding',PAGE)
        self.assertNotIn('<details><summary>How the tools fit together</summary>',PAGE)
        self.assertIn('IRIS — choose and coordinate work',PAGE)
        self.assertIn('CTFd — do the questions and earn points',PAGE)
        self.assertIn('Open {{t.id}} questions, hints &amp; scoring in CTFd',PAGE)
        self.assertIn('class="primary-action"',PAGE)

    def test_correlation_and_capstone_workspaces_are_in_question_sequence(self):
        current=PAGE.index('<section id="current-questions">')
        self.assertGreater(PAGE.index('{{correlation_workspace()}}'),current)
        self.assertGreater(PAGE.index('{{capstone_workspace()}}'),current)
        self.assertIn("q.ticket > 'T16'",PAGE)
        self.assertIn("q.ticket == 'T20'",PAGE)

    def test_feedback_banners_have_a_dismiss_button(self):
        self.assertIn('id="dismiss-answer-result"',PAGE)
        self.assertIn('aria-label="Dismiss message"',PAGE)
        self.assertIn("message_kind=='hint' else 'Try again'",PAGE)
        self.assertIn("dismissAnswerResult.addEventListener('click'",PAGE)
        self.assertIn('aria-label="Dismiss operational update"',PAGE)
        self.assertIn("dismissUpdateX.addEventListener('click'",PAGE)


if __name__=='__main__':unittest.main()
