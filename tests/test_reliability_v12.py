"""Regression coverage for TakePath 1.2 recording reliability."""
import unittest
from pathlib import Path
from action_studio.core import ActionBuilder, is_repeatable_key

class CaptureReliabilityTests(unittest.TestCase):
    def test_overlapping_mouse_buttons_keep_button_identity(self):
        b = ActionBuilder()
        b.mouse_down(100,100,0.1,'left')
        b.mouse_down(100,100,0.2,'right')
        b.mouse_up(100,100,'left',0.3)
        b.mouse_up(100,100,'right',0.4)
        self.assertEqual([(a.kind,a.button) for a in b.finish()],
                         [('click','left'),('click','right')])

    def test_releases_in_reverse_order_are_not_misassociated(self):
        b = ActionBuilder()
        b.mouse_down(100,100,0.1,'left')
        b.mouse_down(200,200,0.2,'right')
        b.mouse_up(200,200,'right',0.3)
        b.mouse_up(100,100,'left',0.4)
        self.assertEqual([(a.button,a.x) for a in b.finish()],
                         [('right',200),('left',100)])

    def test_two_held_buttons_record_distinct_drags(self):
        b = ActionBuilder()
        b.mouse_down(10,20,0.1,'left')
        b.mouse_down(15,25,0.2,'right')
        b.move(80,90,0.3)
        b.mouse_up(80,90,'right',0.4)
        b.move(120,130,0.5)
        b.mouse_up(120,130,'left',0.6)
        actions=b.finish()
        self.assertEqual([(a.kind,a.button) for a in actions],
                         [('drag','right'),('drag','left')])
        self.assertEqual((actions[0].x,actions[0].y),(15,25))
        self.assertEqual((actions[1].end_x,actions[1].end_y),(120,130))
        self.assertGreater(len(actions[1].raw_path),1)

    def test_cancel_one_button_does_not_cancel_another(self):
        b=ActionBuilder()
        b.mouse_down(10,10,0.1,'left')
        b.mouse_down(20,20,0.2,'right')
        b.cancel_button('right')
        b.mouse_up(20,20,'right',0.3)
        b.mouse_up(10,10,'left',0.4)
        self.assertEqual([a.button for a in b.finish()],['left'])

    def test_duplicate_down_is_ignored(self):
        b=ActionBuilder()
        b.mouse_down(10,10,0.1,'left')
        b.mouse_down(200,200,0.2,'left')
        b.mouse_up(10,10,'left',0.3)
        self.assertEqual(b.finish()[0].x,10)

    def test_held_typing_and_backspace_repeat_but_shortcuts_do_not(self):
        self.assertTrue(is_repeatable_key('backspace',None,set()))
        self.assertTrue(is_repeatable_key('left',None,set()))
        self.assertTrue(is_repeatable_key('','a',set()))
        self.assertTrue(is_repeatable_key('','A',{'shift'}))
        self.assertFalse(is_repeatable_key('','v',{'ctrl'}))
        self.assertFalse(is_repeatable_key('f7',None,set()))
        self.assertFalse(is_repeatable_key('f8',None,set()))

    def test_recorder_uses_button_specific_capture(self):
        source=(Path(__file__).resolve().parents[1]/'action_studio'/'recorder.py').read_text(encoding='utf-8')
        self.assertIn('self.builder.mouse_down(round(x), round(y), self._stamp(), value)',source)
        self.assertIn('self.builder.cancel_button(value)',source)
        self.assertIn('is_repeatable_key(name, char, self.modifiers)',source)

if __name__ == '__main__':
    unittest.main()
