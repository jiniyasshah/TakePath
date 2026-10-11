"""Native editor smoke checks for Wait insertion and selection on Windows.

Run with QT_QPA_PLATFORM=offscreen. Windows GitHub CI can exercise widgets
without opening a real desktop; manual screen tests are still needed.
"""
import os
import sys
import unittest
from unittest.mock import patch

@unittest.skipUnless(sys.platform == 'win32', 'Qt desktop behavior checked on Windows CI')
class EditorWaitSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['QT_QPA_PLATFORM']='offscreen'
        from PySide6.QtWidgets import QApplication
        cls.qt=QApplication.instance() or QApplication([])
        from action_studio.ui import MainWindow
        from action_studio.core import Action
        cls.MainWindow=MainWindow
        cls.Action=Action

    def setUp(self):
        self.editor=self.MainWindow()
        self.editor.project.actions=[
            self.Action(kind='click',x=100,y=100),
            self.Action(kind='type',text='example'),
        ]
        self.editor.refresh(set())
        self.editor.show()
        self.qt.processEvents()

    def tearDown(self):
        self.editor.is_dirty=False
        self.editor.close()
        self.qt.processEvents()

    def test_insert_wait_before_first_row(self):
        self.editor.table.selectRow(0)
        with patch('PySide6.QtWidgets.QInputDialog.getItem', return_value=('wait',True)):
            self.editor.add_action(before=True)
        self.assertEqual(self.editor.project.actions[0].kind,'wait')
        self.assertEqual(self.editor.project.actions[0].wait_mode,'duration')
        self.assertEqual(self.editor.project.actions[0].delay,3.0)
        self.assertEqual(self.editor.project.actions[1].kind,'click')

    def test_insert_before_no_selection_goes_to_start(self):
        self.editor.table.clearSelection()
        with patch('PySide6.QtWidgets.QInputDialog.getItem', return_value=('wait',True)):
            self.editor.add_action(before=True)
        self.assertEqual(self.editor.project.actions[0].kind,'wait')

    def test_fixed_wait_shows_duration_not_conditional_fields(self):
        self.editor.project.actions.insert(0, self.Action(kind='wait',wait_mode='duration',delay=3))
        self.editor.refresh({self.editor.project.actions[0].id})
        self.assertEqual(self.editor.delay_caption.text(),'WAIT DURATION')
        self.assertFalse(self.editor.wait_timeout.isVisible()) 
        self.assertIn('Pause',self.editor.table.item(0,2).text())

    def test_click_away_clears_selection_but_inspector_click_preserves_it(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        self.editor.table.selectRow(0)
        self.qt.processEvents()
        self.assertEqual(self.editor._rows(),[0])
        # The inspector heading is always visible. QTest must not send a
        # synthetic press to an offscreen/hidden spinbox: Qt may route it to
        # the main window instead, which is not a real inspector click.
        self.assertTrue(self.editor.inspector_title.isVisible())
        QTest.mouseClick(self.editor.inspector_title,Qt.LeftButton)
        self.assertEqual(self.editor._rows(),[0])
        QTest.mouseClick(self.editor.name,Qt.LeftButton)
        self.assertEqual(self.editor._rows(),[])


    def test_dragged_action_moves_from_bottom_to_first(self):
        wait=self.Action(kind='wait', wait_mode='duration', delay=3)
        self.editor.project.actions.append(wait)
        self.editor.refresh(set())
        self.editor.table.actionsDropped.emit([2],0)
        self.assertIs(self.editor.project.actions[0],wait)
        self.assertEqual([a.kind for a in self.editor.project.actions],
                         ['wait','click','type'])
        self.assertEqual(self.editor._rows(),[0])
        self.assertTrue(self.editor.is_dirty)

    def test_drag_multiple_rows_keeps_identity_and_timing(self):
        a=self.Action(kind='wait',wait_mode='duration',delay=3.5)
        b=self.Action(kind='key',key='enter',delay=0.3)
        self.editor.project.actions.extend([a,b])
        self.editor.refresh(set())
        self.editor.table.actionsDropped.emit([1,3],0)
        self.assertIs(self.editor.project.actions[1],b)
        self.assertEqual([a.kind for a in self.editor.project.actions],
                         ['type','key','click','wait'])
        self.assertEqual(b.delay,0.3)

    def test_properties_remain_selected_when_clicked(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        cases=[
            (self.Action(kind='click'), 'delay'),
            (self.Action(kind='click'), 'enable'),
            (self.Action(kind='drag'), 'coords_x'),
            (self.Action(kind='type',text='abc'), 'edit_text'),
            (self.Action(kind='type',text='abc'), 'char_delay'),
            (self.Action(kind='key',key='enter'), 'key'),
            (self.Action(kind='scroll'), 'scroll_y'),
            (self.Action(kind='wait',wait_mode='duration',delay=3), 'delay'),
            (self.Action(kind='wait',wait_mode='target_title',wait_value='Ready'), 'wait_value'),
            (self.Action(kind='wait',wait_mode='target_title',wait_value='Ready'), 'wait_timeout'),
            (self.Action(kind='secure_input',secure_mode='skip'), 'secure_mode'),
        ]
        for action,which in cases:
            with self.subTest(which=which,kind=action.kind):
                self.editor.project.actions[0]=action
                self.editor.refresh({action.id})
                field=(self.editor.coords['x'] if which=='coords_x'
                       else getattr(self.editor,which))
                self.editor.inspector_form.ensureWidgetVisible(field)
                self.qt.processEvents()
                # Spinboxes contain an internal line edit; clicking that
                # real child exercises the same interaction as the user.
                from PySide6.QtWidgets import QAbstractSpinBox, QTextEdit
                click_target=(field.lineEdit() if isinstance(field,QAbstractSpinBox)
                              else field.viewport() if isinstance(field,QTextEdit)
                              else field)
                self.assertTrue(click_target.isVisibleTo(self.editor),which)
                QTest.mouseClick(click_target,Qt.LeftButton)
                self.qt.processEvents()
                self.assertEqual(self.editor._rows(),[0],f'{action.kind} {which} unselected the action')
                if which=='secure_mode':
                    QTest.keyClick(field,Qt.Key_Escape)

    def test_click_blank_inspector_space_clears_selected_action(self):
        from PySide6.QtCore import Qt, QPoint
        from PySide6.QtTest import QTest
        self.editor.table.selectRow(0)
        self.qt.processEvents()
        self.assertEqual(self.editor._rows(),[0])
        blank=QPoint(2,self.editor.inspector_panel.height()//2)
        QTest.mouseClick(self.editor.inspector_panel,Qt.LeftButton,pos=blank)
        self.qt.processEvents()
        self.assertEqual(self.editor._rows(),[])

if __name__=='__main__':
    unittest.main()
