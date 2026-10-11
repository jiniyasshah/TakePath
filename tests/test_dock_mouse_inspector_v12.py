"""Regression tests: safe click-through overlay, mouse travel presets, and responsive inspector."""
import unittest
from pathlib import Path
from action_studio.core import Action, Project, MOUSE_SPEED_FACTORS
from action_studio.playback import Player

ROOT=Path(__file__).resolve().parents[1]


class MouseSpeedTests(unittest.TestCase):
    def test_project_defaults_to_normal_and_roundtrips(self):
        p=Project()
        self.assertEqual(p.mouse_speed_mode,'normal')
        for mode in ('normal','fast','slow','instant'):
            p.mouse_speed_mode=mode
            self.assertEqual(Project.from_dict(p.to_dict()).mouse_speed_mode,mode)

    def test_old_projects_remain_normal_speed(self):
        old=Project().to_dict()
        old.pop('mouse_speed_mode',None)
        self.assertEqual(Project.from_dict(old).mouse_speed_mode,'normal')
        old['mouse_speed_mode']='invalid'
        self.assertEqual(Project.from_dict(old).mouse_speed_mode,'normal')

    def test_normal_fast_slow_instant_scale_mouse_only(self):
        times={}
        for mode in ('normal','fast','slow','instant'):
            player=Player([],0,mouse_speed_mode=mode)
            times[mode]=player._mouse_duration(1.5)
        self.assertEqual(times['normal'],1.5)
        self.assertLess(times['fast'], times['normal'])
        self.assertGreater(times['slow'],times['normal'])
        self.assertEqual(times['instant'],0)
        self.assertEqual(MOUSE_SPEED_FACTORS['normal'],1.0)

    def test_instant_drag_keeps_small_real_duration(self):
        player=Player([],0,mouse_speed_mode='instant')
        self.assertGreaterEqual(player._mouse_duration(1,dragging=True),.05)
        self.assertLess(player._mouse_duration(1,dragging=True),.15)

    def test_instant_click_moves_directly_without_path(self):
        player=Player([],0,mouse_speed_mode='instant')
        moves=[]
        player._move=lambda x,y:moves.append((x,y))
        player._smooth_move=lambda *args: self.fail('instant click must not traverse slow path')
        player._cursor(Action(kind='click',path_duration=10),123,456)
        self.assertEqual(moves,[(123,456)])

    def test_other_speed_values_fall_back(self):
        self.assertEqual(Player([],0,mouse_speed_mode='racing').mouse_speed_mode,'normal')


class SourceGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui=(ROOT/'action_studio'/'ui.py').read_text(encoding='utf-8')
        cls.playback=(ROOT/'action_studio'/'playback.py').read_text(encoding='utf-8')

    def test_windows_active_overlay_passes_clicks_through(self):
        self.assertIn('pointer_passthrough=recording or playing',self.ui)
        self.assertIn('transparent=0x00000020',self.ui)
        self.assertIn('layered=0x00080000',self.ui)
        self.assertIn('updated &= ~transparent',self.ui)
        self.assertIn('user32.SetWindowPos(',self.ui)

    def test_editor_speed_control_is_wired_through_replay(self):
        self.assertIn("mouse_speed_group=toolbar_group('MOUSE SPEED')",self.ui)
        self.assertIn('mouse_speed_mode=self.project.mouse_speed_mode',self.ui)
        self.assertIn('def set_mouse_speed(self,mode):',self.ui)
        self.assertIn('self._mouse_duration(a.path_duration',self.playback)

    def test_secure_input_inspector_no_horizontal_scroll_or_two_button_clipping(self):
        self.assertIn('scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)',self.ui)
        self.assertIn('controls=V(spacing=5)',self.ui)
        self.assertIn("review=B('Review value'",self.ui)
        self.assertIn('secret_help.setWordWrap(True)',self.ui)
        self.assertIn("a.kind.replace('_',' ').title()",self.ui)


if __name__=='__main__':
    unittest.main()
