"""Regression tests for shorter active dock and context-sensitive speed overrides."""
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from action_studio.core import (
    Action, Project, ACTION_TYPING_SPEED_MODES, TYPING_SPEED_FACTORS,
    effective_typing_speed,
)
from action_studio.playback import Player

ROOT=Path(__file__).resolve().parents[1]


class TypingSpeedTests(unittest.TestCase):
    def test_old_type_actions_use_project_mode(self):
        old=Action(kind='type',text='abc').__dict__.copy()
        old.pop('typing_speed_override',None)
        restored=Action.from_dict(old)
        self.assertEqual(restored.typing_speed_override,'inherit')
        self.assertEqual(effective_typing_speed(restored,'smooth'),'smooth')
        self.assertEqual(effective_typing_speed(restored,'original'),'original')
        self.assertEqual(effective_typing_speed(restored,'instant'),'instant')

    def test_typing_override_modes_roundtrip_with_actions(self):
        for mode in ACTION_TYPING_SPEED_MODES:
            with self.subTest(mode=mode):
                original=Project(actions=[Action(kind='type',text='hello',
                    typing_speed_override=mode)],global_typing_mode='smooth')
                restored=Project.from_dict(original.to_dict()).actions[0]
                self.assertEqual(restored.typing_speed_override,mode)
        for invalid in ('not-a-mode',None,11):
            action=Action.from_dict({'kind':'type','typing_speed_override':invalid})
            self.assertEqual(action.typing_speed_override,'inherit')

    def test_per_action_fast_slow_normal_and_instant(self):
        for mode,expected in [('normal',.1),('fast',.045),('slow',.18),('instant',0)]:
            with self.subTest(mode=mode):
                action=Action(kind='type',text='abcdef',char_delay=.1,
                              typing_speed_override=mode)
                player=Player([action],0,typing_mode='smooth')
                delays=[]
                player._wait=lambda *args,**kwargs:None
                player._guard=lambda *args,**kwargs:None
                player._unicode_type=lambda text,seconds,**kwargs:delays.append(seconds)
                with patch.dict('sys.modules', {'pyautogui': MagicMock()}):
                    player._action(action)
                self.assertEqual(len(delays),1)
                self.assertAlmostEqual(delays[0],expected)

    def test_per_type_original_restores_recorded_rhythm(self):
        action=Action(kind='type',text='abc',char_delay=.09,
                      typing_speed_override='original')
        player=Player([action],0,typing_mode='instant')
        samples=[]
        player._wait=lambda *args,**kwargs:None
        player._guard=lambda *args,**kwargs:None
        player._recorded_type=lambda *args:samples.append(args)
        with patch.dict('sys.modules', {'pyautogui': MagicMock()}):
            player._action(action)
        self.assertEqual(samples[0][0],'abc')

    def test_keyboard_and_secure_input_not_affected(self):
        for kind in ('key','secure_input','wait','click'):
            action=Action(kind=kind,typing_speed_override='fast')
            self.assertEqual(effective_typing_speed(action,'smooth'),'smooth')
        self.assertEqual(TYPING_SPEED_FACTORS['fast'],.45)

    def test_user_ui_integrated(self):
        source=(ROOT/'action_studio'/'ui.py').read_text(encoding='utf-8')
        self.assertIn("menu.addMenu('Typing speed')",source)
        self.assertIn("menu.addMenu('Wait duration')",source)
        self.assertIn("if mouse_actions:",source)
        self.assertIn("if typed:",source)
        self.assertIn("if timed:",source)
        self.assertIn("def _close_irrelevant_submenus(menu, hovered_action):",source)
        self.assertIn("class ActionContextMenu(QMenu)",source)
        self.assertIn("typing_speed_override",source)

    def test_active_dock_defaults_short_and_has_sidecar(self):
        source=(ROOT/'action_studio'/'ui.py').read_text(encoding='utf-8')
        self.assertIn("'dock_short_while_active','true'",source)
        self.assertIn('desired_width=(332 if playing else 238)',source)
        self.assertIn('self.x()+self.width()-8',source)
        self.assertIn('visual_width=self.width()+extra',source)
        self.assertIn('self.clock.setVisible(not (island_active and playing and self.compact_active))',source)


if __name__=='__main__':
    unittest.main()
