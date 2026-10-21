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
        for text in ('id="queue-status"','{{queue.status}}','queue.notes.get',
                     'Claim ticket — start working</button></form>{% else %}',
                     "'Choose up to three available tickets' if queue.claimable"):
            self.assertIn(text,PAGE)

    def test_page_explains_native_iris_status_is_read_only(self):
        self.assertIn('How to start work',PAGE)
        self.assertIn('up to three tickets at the same time',PAGE)
        self.assertIn('native IRIS task view is read-only for participants',PAGE)
        self.assertIn('View read-only IRIS tasks and shared findings',PAGE)
        self.assertIn('<strong>Start here</strong>',PAGE)
        self.assertIn('for step in route.directions',PAGE)
        self.assertIn('What each app is for',PAGE)
        self.assertIn('IRIS — choose and coordinate work',PAGE)
        self.assertIn('CTFd — do the questions and earn points',PAGE)
        self.assertIn('Open {{t.id}} questions, hints &amp; scoring in CTFd',PAGE)
        self.assertIn('class="primary-action"',PAGE)


if __name__=='__main__':unittest.main()

