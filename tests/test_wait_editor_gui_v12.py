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
        # Renaming the workflow is a real editable input, not blank space.
        QTest.mouseClick(self.editor.name,Qt.LeftButton)
        self.assertEqual(self.editor._rows(),[0])
        from PySide6.QtCore import QPoint
        blank=QPoint(2,self.editor.inspector_panel.height()//2)
        QTest.mouseClick(self.editor.inspector_panel,Qt.LeftButton,pos=blank)
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

    def test_bottom_toolbar_controls_keep_selected_action(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        self.editor.table.selectRow(0)
        self.qt.processEvents()
        controls=[
            ('timing gap',self.editor.uniform.field),
            ('apply to selected',self.editor.uniform_apply),
            ('mouse path',self.editor.global_mode),
            ('typing style',self.editor.global_typing),
            ('center cursor',self.editor.play_center),
            ('adaptive wait',self.editor.auto_wait_toggle),
            ('playback speed',self.editor.speed),
        ]
        for name,control in controls:
            with self.subTest(control=name):
                self.editor.table.selectRow(0)
                # The playback toolbar is horizontally scrollable on small
                # windows. Bring each button into view before simulating a
                # click; sending a synthetic click to an offscreen combo
                # instead hits blank space and incorrectly clears selection.
                self.editor.toolbar_scroll.ensureWidgetVisible(control)
                self.qt.processEvents()
                self.assertTrue(control.isVisibleTo(self.editor),name)
                QTest.mouseClick(control,Qt.LeftButton)
                self.qt.processEvents()
                self.assertEqual(self.editor._rows(),[0],
                                 f'{name} cleared the selected action')
                # Close editable combo dropdowns before the next control.
                if name in ('mouse path','typing style','playback speed'):
                    QTest.keyClick(control,Qt.Key_Escape)
                    self.qt.processEvents()

    def test_toolbar_values_change_without_deselecting(self):
        self.editor.table.selectRow(0)
        action=self.editor.project.actions[0]
        self.editor.uniform.setValue(1.3)
        self.editor.uniform_apply.click()
        self.qt.processEvents()
        self.assertEqual(action.delay,1.3)
        self.assertEqual(self.editor._rows(),[0])
        self.editor.global_mode.setCurrentText('Straight')
        self.editor.global_typing.setCurrentText('Instant')
        self.editor.speed.setCurrentText('1.5×')
        self.qt.processEvents()
        self.assertEqual(self.editor._rows(),[0])
        self.assertEqual(self.editor.project.cursor_mode,'straight')
        self.assertEqual(self.editor.project.global_typing_mode,'instant')

    def test_replay_dock_displays_step_marker(self):
        from types import SimpleNamespace
        self.editor.project.actions=[
            self.Action(kind='click',x=20,y=40),
            self.Action(kind='wait',delay=3,wait_mode='duration'),
            self.Action(kind='type',text='secret-data'),
        ]
        flag=SimpleNamespace(is_set=lambda:False)
        self.editor.player=SimpleNamespace(isRunning=lambda:True,
                                            awaiting_secure_input=False,
                                            pause_flag=flag,
                                            paused_at=0,
                                            pause_accumulated=0,
                                            cancel=lambda:None,
                                            wait=lambda _ms:None)
        try:
            self.editor.dock.show()
            self.editor.last_playback_step=1
            self.editor.dock.sync()
            self.qt.processEvents()
            self.assertTrue(self.editor.dock.step_status.isVisible())
            self.assertIn('STEP 002/003',self.editor.dock.step_status.toolTip())
            self.assertIn('WAIT 3.0s',self.editor.dock.step_status.toolTip())
            self.editor.last_playback_step=2
            self.editor.dock.sync()
            self.assertIn('TYPE (11 chars)',self.editor.dock.step_status.toolTip())
            self.assertNotIn('secret-data',self.editor.dock.step_status.toolTip())
        finally:
            self.editor.player=None
            self.editor.dock.hide()

    def test_mouse_speed_setting_keeps_action_selected_and_persists(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        self.editor.table.selectRow(0)
        self.qt.processEvents()
        QTest.mouseClick(self.editor.mouse_speed,Qt.LeftButton)
        self.qt.processEvents()
        self.assertEqual(self.editor._rows(),[0])
        QTest.keyClick(self.editor.mouse_speed,Qt.Key_Escape)
        self.editor.mouse_speed.setCurrentText('Fast')
        self.assertEqual(self.editor.project.mouse_speed_mode,'fast')
        self.assertEqual(self.editor._rows(),[0])
        from action_studio.core import Project
        saved=Project.from_dict(self.editor.project.to_dict())
        self.assertEqual(saved.mouse_speed_mode,'fast')

    def test_secure_inspector_fits_without_horizontal_scroll(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QPushButton, QLabel
        self.editor.project.actions[0]=self.Action(kind='secure_input',secure_mode='auto')
        action=self.editor.project.actions[0]
        self.editor.refresh({action.id})
        self.editor.inspector_form.ensureWidgetVisible(self.editor.secure_mode)
        self.qt.processEvents()
        self.assertEqual(self.editor.inspector_form.horizontalScrollBarPolicy(),
                         Qt.ScrollBarAlwaysOff)
        self.assertEqual(self.editor.inspector_title.text(),'Secure Input action')
        review=[b for b in self.editor.secure_container.findChildren(QPushButton)
                if b.text()=='Review value']
        self.assertEqual(len(review),1)
        self.assertTrue(review[0].parentWidget() is not None)
        self.assertGreater(self.editor.secret_edit.width(),80)
        hints=[l for l in self.editor.secure_container.findChildren(QLabel)
               if 'They never go in project JSON' in l.text()]
        self.assertEqual(len(hints),1)
        self.assertTrue(hints[0].wordWrap())

    def test_context_menu_applies_fast_to_multiple_selected_mouse_actions(self):
        from PySide6.QtWidgets import QTableWidgetSelectionRange
        actions=[
            self.Action(kind='click',x=15),
            self.Action(kind='wait',delay=3),
            self.Action(kind='drag',x=10,end_x=100),
            self.Action(kind='scroll',dy=-3),
        ]
        self.editor.project.actions=actions
        self.editor.refresh(set())
        self.editor.table.setRangeSelected(QTableWidgetSelectionRange(0,0,0,4),True)
        self.editor.table.setRangeSelected(QTableWidgetSelectionRange(1,0,3,4),True)
        self.assertEqual(self.editor._rows(),[0,1,2,3])
        menu=self.editor.build_action_context_menu(
            self.editor.table.visualRect(self.editor.table.model().index(2,0)).center())
        speed_menu=next(action.menu() for action in menu.actions()
                        if action.text()=='Mouse speed')
        fast=next(action for action in speed_menu.actions() if action.text()=='Fast')
        fast.trigger()
        self.assertEqual([a.mouse_speed_override for a in actions],
                         ['fast','inherit','fast','fast'])
        self.assertEqual(self.editor._rows(),[0,1,2,3])
        self.assertTrue(self.editor.is_dirty)
        self.assertIn('Mouse: Fast',self.editor.table.item(0,2).text())
        self.assertNotIn('Mouse:',self.editor.table.item(1,2).text())

    def test_context_menu_right_click_preserves_multi_selection(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QTableWidgetSelectionRange
        self.editor.project.actions=[self.Action(kind='click',x=i*10) for i in range(3)]
        self.editor.refresh(set())
        self.editor.table.setRangeSelected(QTableWidgetSelectionRange(0,0,1,4),True)
        self.assertEqual(self.editor._rows(),[0,1])
        pos=self.editor.table.visualRect(self.editor.table.model().index(1,1)).center()
        # Right click itself should not collapse the multi-selection.
        # Avoid opening a native popup in offscreen tests.
        self.editor.table.customContextMenuRequested.disconnect(
            self.editor.show_action_context_menu)
        QTest.mouseClick(self.editor.table.viewport(),Qt.RightButton,pos=pos)
        self.assertEqual(self.editor._rows(),[0,1])

    def test_context_menu_override_reset_and_bulk_enable_disable(self):
        a=self.Action(kind='click',mouse_speed_override='slow')
        b=self.Action(kind='click',mouse_speed_override='fast')
        self.editor.project.actions=[a,b]
        self.editor.refresh({a.id,b.id})
        menu=self.editor.build_action_context_menu(
            self.editor.table.visualRect(self.editor.table.model().index(0,0)).center())
        submenu=next(action.menu() for action in menu.actions()
                     if action.text()=='Mouse speed')
        inherit=next(action for action in submenu.actions() if action.text().startswith('Use global speed'))
        self.assertFalse(inherit.isChecked())
        inherit.trigger()
        self.assertEqual([a.mouse_speed_override,b.mouse_speed_override],['inherit','inherit'])
        another=self.editor.build_action_context_menu(
            self.editor.table.visualRect(self.editor.table.model().index(0,0)).center())
        next(action for action in another.actions() if action.text()=='Disable selected').trigger()
        self.assertFalse(a.enabled)
        self.assertFalse(b.enabled)

    def test_context_menu_nonmouse_rows_do_not_gain_speed_overrides(self):
        action=self.Action(kind='type',text='hello')
        self.editor.project.actions=[action]
        self.editor.refresh({action.id})
        menu=self.editor.build_action_context_menu(
            self.editor.table.visualRect(self.editor.table.model().index(0,0)).center())
        submenu=next(item.menu() for item in menu.actions() if item.text()=='Mouse speed')
        self.assertFalse(submenu.isEnabled())
        self.assertEqual(action.mouse_speed_override,'inherit')


if __name__=='__main__':
    unittest.main()
