"""V2 serialization, global motion, multi-select deletion, and legacy compatibility."""
import tempfile
import unittest
from pathlib import Path
from action_studio.core import Action, Project, remove_actions, load_project, save_project


class VersionTwoTests(unittest.TestCase):
    def test_global_cursor_setting_keeps_original_paths(self):
        action = Action(kind='click', x=500, y=500, path_mode='original',
                        raw_path=[[100,100,0],[300,300,.4],[500,500,.8]])
        project = Project(actions=[action], cursor_mode='smooth')
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / 'project.vas.json'
            save_project(project, dest)
            result = load_project(dest)
            self.assertEqual(result.cursor_mode,'smooth')
            self.assertEqual(result.actions[0].raw_path, action.raw_path)
            self.assertEqual(result.actions[0].path_mode,'original')
            result.cursor_mode = 'original'
            save_project(result, dest)
            self.assertEqual(load_project(dest).cursor_mode,'original')

    def test_legacy_project_v1_opens(self):
        data = Project(actions=[Action(kind='type', text='Correct me')]).to_dict()
        data['schema'] = 1
        del data['cursor_mode']
        del data['preview_jpeg']
        del data['preview_bounds']
        result = Project.from_dict(data)
        self.assertEqual(result.actions[0].text, 'Correct me')
        self.assertEqual(result.cursor_mode,'smooth')

    def test_screen_still_is_portable(self):
        project=Project(preview_jpeg='abc123', preview_bounds=[-1200,30,1120,820])
        result=Project.from_dict(project.to_dict())
        self.assertEqual(result.preview_jpeg,'abc123')
        self.assertEqual(result.preview_bounds,[-1200,30,1120,820])

    def test_bulk_delete_preserves_order(self):
        actions=[Action(kind='click',x=i) for i in range(8)]
        selected={actions[i].id for i in (0,3,4,7)}
        remaining=remove_actions(actions,selected)
        self.assertEqual([a.x for a in remaining],[1,2,5,6])
        self.assertEqual(len(actions),8)

if __name__ == '__main__':unittest.main()
