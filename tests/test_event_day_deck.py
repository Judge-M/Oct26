import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DECK_DIR = ROOT / 'docs' / 'event-day-deck'
REGISTRATION_URL = 'https://ctfd.cyberexperts.org/silent-ridge/register'
ENROLLMENT_CODE = 'SILENT-RIDGE'


class EventDayDeckTests(unittest.TestCase):
    def test_opening_powerpoint_projects_registration_url_and_code(self):
        with zipfile.ZipFile(DECK_DIR / 'opening-brief.pptx') as deck:
            slide = deck.read('ppt/slides/slide5.xml').decode('utf-8')
            self.assertIn(REGISTRATION_URL, slide)
            self.assertIn(ENROLLMENT_CODE, slide)

    def test_opening_powerpoint_keeps_embedded_autoplay_video(self):
        with zipfile.ZipFile(DECK_DIR / 'opening-brief.pptx') as deck:
            names = set(deck.namelist())
            slide = deck.read('ppt/slides/slide4.xml').decode('utf-8')
            relationships = deck.read(
                'ppt/slides/_rels/slide4.xml.rels').decode('utf-8')
            self.assertIn('ppt/media/media1.mp4', names)
            self.assertIn('action="ppaction://media"', slide)
            self.assertIn('cmd="playFrom(0.0)"', slide)
            self.assertIn('Target="../media/media1.mp4"', relationships)
            self.assertNotIn('r:id=""', slide)

    def test_opening_libreoffice_copy_contains_same_check_in_details_and_video(self):
        with zipfile.ZipFile(DECK_DIR / 'opening-brief.odp') as deck:
            content = deck.read('content.xml').decode('utf-8')
            self.assertIn(REGISTRATION_URL, content)
            self.assertIn(ENROLLMENT_CODE, content)
            self.assertTrue(any(name.endswith('.mp4') for name in deck.namelist()))


if __name__ == '__main__':
    unittest.main()
