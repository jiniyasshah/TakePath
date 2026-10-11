"""Action editor drag/reorder regressions with no native GUI dependency."""
import unittest
from pathlib import Path
from action_studio.core import Action, reorder_actions, Project

ROOT=Path(__file__).resolve().parents[1]


class ReorderActionsTests(unittest.TestCase):
    def setUp(self):
        self.actions=[Action(kind='click', x=i, delay=i+0.25) for i in range(6)]
        self.ids=[a.id for a in self.actions]

    def assert_order(self,result,indices):
        self.assertEqual([a.id for a in result], [self.ids[i] for i in indices])
        self.assertEqual([a.x for a in result],indices)
        self.assertEqual([a.delay for a in result], [i+0.25 for i in indices])
        self.assertEqual([a.id for a in self.actions],self.ids)

    def test_move_last_above_first(self):
        self.assert_order(reorder_actions(self.actions,[5],0),[5,0,1,2,3,4])

    def test_move_first_after_last(self):
        self.assert_order(reorder_actions(self.actions,[0],6),[1,2,3,4,5,0])

    def test_drag_custom_wait_before_first_action(self):
        self.actions[4]=Action(kind='wait',delay=3.0,wait_mode='duration')
        self.ids[4]=self.actions[4].id
        moved=reorder_actions(self.actions,[4],0)
        self.assertEqual(moved[0].kind,'wait')
        self.assertEqual(moved[0].delay,3)
        self.assertEqual([a.id for a in moved], [self.ids[i] for i in [4,0,1,2,3,5]])
        self.assertIs(moved[0],self.actions[4])
        self.assertEqual([a.x for a in moved[1:]],[0,1,2,3,5])

    def test_multi_selected_action_drag_preserves_relative_order(self):
        self.assert_order(reorder_actions(self.actions,[1,3],6),[0,2,4,5,1,3])
        self.assert_order(reorder_actions(self.actions,[2,3,4],0),[2,3,4,0,1,5])

    def test_drop_within_selection_is_no_op(self):
        self.assert_order(reorder_actions(self.actions,[2,3],3),[0,1,2,3,4,5])

    def test_invalid_drag_does_not_edit_project(self):
        for rows,target in [([],0),([-1],0),([99],0),([0],-1),([0],99)]:
            with self.subTest(rows=rows, target=target):
                with self.assertRaises(ValueError):
                    reorder_actions(self.actions,rows,target)
        self.assertEqual([a.id for a in self.actions],self.ids)

    def test_reordered_actions_can_roundtrip_without_identity_changes(self):
        result=reorder_actions(self.actions,[4],0)
        p=Project(actions=result)
        self.assertEqual([a.id for a in Project.from_dict(p.to_dict()).actions],
                         [a.id for a in result])

    def test_editor_has_row_drag_mode_and_preserves_selection(self):
        src=(ROOT/'action_studio/ui.py').read_text(encoding='utf-8')
        self.assertIn('class ActionTable(QTableWidget)',src)
        self.assertIn('self.setDragDropMode(QAbstractItemView.InternalMove)',src)
        self.assertIn('def dropEvent(self, event):',src)
        self.assertIn('self.table.actionsDropped.connect(self.reorder_dragged_actions)',src)
        self.assertIn('self.refresh(selected_ids)',src)

    def test_editor_requires_blank_click_to_clear_selection(self):
        src=(ROOT/'action_studio/ui.py').read_text(encoding='utf-8')
        self.assertIn('def _inspector_field_hit(self, obj, event):',src)
        self.assertIn('if not self._inspector_field_hit(obj, event):',src)
        self.assertIn('self.inspector_panel.childAt(inside)',src)


if __name__=='__main__':
    unittest.main()
