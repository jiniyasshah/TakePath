"""Regression tests for per-action mouse speed and bulk selection."""
import unittest
from pathlib import Path
from action_studio.core import (
    Action, Project, MOUSE_SPEED_FACTORS, ACTION_MOUSE_SPEED_MODES,
    effective_mouse_speed,
)
from action_studio.playback import Player

ROOT=Path(__file__).resolve().parents[1]


class PerActionMouseSpeedTests(unittest.TestCase):
    def test_old_actions_inherit_project_speed(self):
        data=Action(kind='click',x=100,y=200).__dict__.copy()
        data.pop('mouse_speed_override',None)
        old=Action.from_dict(data)
        self.assertEqual(old.mouse_speed_override,'inherit')
        self.assertEqual(effective_mouse_speed(old,'fast'),'fast')
        self.assertEqual(effective_mouse_speed(old,'slow'),'slow')

    def test_specific_action_override_wins(self):
        actions=[
            Action(kind='click',path_duration=2,mouse_speed_override='fast'),
            Action(kind='click',path_duration=2,mouse_speed_override='slow'),
            Action(kind='drag',path_duration=2,mouse_speed_override='instant'),
            Action(kind='scroll',path_duration=2,mouse_speed_override='normal'),
            Action(kind='click',path_duration=2),
        ]
        p=Player(actions,0,mouse_speed_mode='normal')
        self.assertAlmostEqual(p._mouse_duration(2,action=actions[0]),.6)
        self.assertAlmostEqual(p._mouse_duration(2,action=actions[1]),3.6)
        self.assertEqual(p._mouse_duration(2,action=actions[2]),0)
        self.assertEqual(p._mouse_duration(2,action=actions[2],dragging=True),.06)
        self.assertEqual(p._mouse_duration(2,action=actions[3]),2)
        self.assertEqual(p._mouse_duration(2,action=actions[4]),2)

    def test_global_changes_only_inherited_actions(self):
        override=Action(kind='click',mouse_speed_override='slow')
        inherit=Action(kind='click')
        self.assertEqual(effective_mouse_speed(override,'fast'),'slow')
        self.assertEqual(effective_mouse_speed(inherit,'fast'),'fast')

    def test_nonmouse_actions_do_not_use_override(self):
        for kind in ('type','wait','secure_input','key'):
            with self.subTest(kind=kind):
                action=Action(kind=kind,mouse_speed_override='instant')
                self.assertEqual(effective_mouse_speed(action,'slow'),'slow')

    def test_round_trip_per_action_overrides_and_original_fields(self):
        actions=[Action(kind='click',delay=.3,x=45,mouse_speed_override='fast'),
                 Action(kind='drag',delay=.8,raw_path=[[0,0,0],[10,10,.5]],
                        mouse_speed_override='slow'),
                 Action(kind='scroll',dx=1,dy=2,mouse_speed_override='instant')]
        project=Project(actions=actions,mouse_speed_mode='normal')
        reloaded=Project.from_dict(project.to_dict())
        self.assertEqual([a.mouse_speed_override for a in reloaded.actions],
                         ['fast','slow','instant'])
        self.assertEqual([a.delay for a in reloaded.actions],[.3,.8,.5])
        self.assertEqual([a.id for a in reloaded.actions],[a.id for a in actions])
        self.assertEqual(reloaded.actions[1].raw_path,actions[1].raw_path)

    def test_unknown_speed_defaults_to_inherit(self):
        for value in ('superfast',42,None):
            with self.subTest(value=value):
                a=Action.from_dict({'kind':'click','mouse_speed_override':value})
                self.assertEqual(a.mouse_speed_override,'inherit')
        self.assertIn('inherit',ACTION_MOUSE_SPEED_MODES)
        self.assertEqual(len(MOUSE_SPEED_FACTORS),4)

    def test_replay_calls_per_action_for_click_drag_scroll(self):
        source=(ROOT/'action_studio/playback.py').read_text(encoding='utf-8')
        self.assertIn('effective_mouse_speed(action, self.mouse_speed_mode)',source)
        self.assertIn('self._mouse_duration(a.path_duration, dragging=dragging, action=a)',source)
        self.assertIn('self._mouse_duration(0.18, action=a)',source)
        self.assertIn('self._mouse_duration(0.15, action=a)',source)
        self.assertIn('self._mouse_duration(a.path_duration, dragging=True, action=a)',source)


if __name__=='__main__':
    unittest.main()
