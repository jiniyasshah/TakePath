import json
import tempfile
import unittest
from pathlib import Path
from action_studio.core import (Action, ActionBuilder, Project, load_project,
                                save_project, simplified_path, interpolate_path)

class ModelTests(unittest.TestCase):
    def test_round_trip(self):
        p = Project(name='Video intro 🎬', screen_bounds=[-1920, 0, 3840, 1080], actions=[Action(kind='type', text='Hello 世界!',
                    delay=1.25), Action(kind='click', x=510, y=220,
                    raw_path=[[0,0,0],[510,220,.4]],path_mode='original')])
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'recording.vas.json'
            save_project(p,target)
            loaded=load_project(target)
            self.assertEqual(loaded.name,p.name)
            self.assertEqual(loaded.screen_bounds, [-1920,0,3840,1080])
            self.assertEqual(loaded.actions[0].text,'Hello 世界!')
            self.assertEqual(loaded.actions[1].raw_path,p.actions[1].raw_path)

    def test_invalid_and_unsafe_data(self):
        with self.assertRaises(ValueError):
            Project.from_dict({'schema':1, 'actions':[{'kind':'shell','text':'bad'}]})
        with self.assertRaises(ValueError):
            Action.from_dict({'kind':'click','delay':float('nan')})
        self.assertEqual(Action.from_dict({'kind':'click','path_mode':'bogus'}).path_mode,'smooth')

    def test_typing_correction(self):
        b=ActionBuilder()
        for i,c in enumerate('hellp'):
            b.char(c,i*.08+.1)
        b.backspace(.52)
        b.char('o',.58)
        b.key('enter',.8)
        acts=b.finish()
        self.assertEqual([a.kind for a in acts],['type','key'])
        self.assertEqual(acts[0].text,'hello')
        self.assertEqual(acts[1].key,'enter')
        self.assertGreaterEqual(acts[1].delay,0)

    def test_click_path(self):
        b=ActionBuilder()
        for i in range(30):
            b.move(50 + i*10,100 + i*2,i*.025+.1)
        b.mouse_down(340,158,1.0)
        b.mouse_up(340,158,'left',1.1)
        acts=b.finish()
        self.assertEqual(len(acts),1)
        self.assertEqual(acts[0].kind,'click')
        self.assertGreaterEqual(len(acts[0].raw_path),2)
        self.assertEqual(acts[0].x,340)

    def test_drag(self):
        b=ActionBuilder()
        b.mouse_down(20,20,.2)
        for i in range(1,20):b.move(20+i*8,20+i*4,.2+i*.02)
        b.mouse_up(180,100,'left',.65)
        a=b.finish()[0]
        self.assertEqual(a.kind,'drag')
        self.assertEqual(a.end_x,180)

    def test_scroll_grouping(self):
        b=ActionBuilder()
        b.scroll(200,200,0,-1,.1)
        b.scroll(200,200,0,-1,.2)
        b.scroll(200,200,0,1,.25)
        self.assertEqual(len(b.finish()),2)
        self.assertEqual(b.actions[0].dy,-2)

    def test_motion_endpoints(self):
        path=list(interpolate_path((5,10),(350,290),14))
        self.assertEqual(path[-1],(350,290))
        self.assertLessEqual(len(simplified_path([[0,0,0],[1,1,.5],[2,2,1]])),2)

if __name__=='__main__':unittest.main()
