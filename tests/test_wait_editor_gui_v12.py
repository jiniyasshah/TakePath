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
        # The text field and checkboxes must fit the 320px inspector viewport.
        viewport=self.editor.inspector_form.viewport()
        for field in (self.editor.secret_edit,self.editor.secret_remember,
                      self.editor.secret_apply_all,self.editor.secret_reveal):
            self.assertLessEqual(
                field.mapTo(viewport,field.rect().topRight()).x(),
                viewport.width()+2,field.objectName() or type(field).__name__)
        self.assertFalse(viewport.autoFillBackground())
        self.assertIn('Remember securely on this device',self.editor.secret_remember.text())
        self.assertNotIn('Credential Manager / Keychain',self.editor.secret_remember.text())

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
        entries=[item.text() for item in menu.actions()]
        self.assertNotIn('Mouse speed',entries)
        self.assertIn('Typing speed',entries)
        self.assertEqual(action.mouse_speed_override,'inherit')


    def test_windows_interactive_island_and_compact_persistence(self):
        from unittest.mock import patch
        dock=self.editor.dock
        self.assertIsNotNone(dock.control_island)
        old=dock.compact_active
        try:
            with patch.object(dock,'_avoid_stealing_focus'), \
                 patch('action_studio.ui.window_rect',side_effect=lambda hwnd: (
                     [500,30,116,64] if hwnd==int(dock.control_island.winId())
                     else [60,41,34,42])):
                dock.show()
                self.editor.recorder.active=True
                dock.sync()
                self.qt.processEvents()
                self.assertTrue(dock.control_island.isVisible())
                self.assertTrue(dock.control_island.pause.isEnabled())
                self.assertTrue(dock.control_island.stop.isEnabled())
                self.assertFalse(dock.pause.isVisible())
                self.assertEqual(self.editor.recorder.interactive_bounds,(500,30,116,64))
                self.assertEqual(self.editor.recorder.interactive_grip_bounds,(60,41,34,42))
                self.assertTrue(dock.grip_overlay.isVisible())
                dock.set_compact_mode(True)
                from PySide6.QtTest import QTest
                QTest.qWait(310)
                dock._dock_geometry_animation.setCurrentTime(
                    dock._dock_geometry_animation.duration())
                self.assertEqual(dock.width(),214)
                self.assertEqual(dock.height(),64)
                self.assertEqual(dock.control_island.width(),116)
                self.assertEqual(dock.control_island.x(),dock.x()+dock.width())
                self.assertEqual(dock.control_island.y(),dock.y())
                self.assertEqual(dock.body.objectName(),'dockBodyJoinedLeft')
                self.assertEqual(dock.control_island.frame.objectName(),'dockBodyJoinedRight')
                self.assertEqual(dock.width()+dock.control_island.width(),330)
                grip_offset=dock.grip_overlay.pos()-dock.pos()
                self.assertEqual(grip_offset.x(),8)
                self.assertEqual(grip_offset.y(),11)
                self.assertTrue(dock.grip_placeholder.isVisible())
                dock.set_compact_mode(False)
                QTest.qWait(310)
                dock._dock_geometry_animation.setCurrentTime(
                    dock._dock_geometry_animation.duration())
                self.assertEqual(dock.width(),846)
                self.assertEqual(dock.height(),64)
                self.assertEqual(dock.control_island.x(),dock.x()+dock.width())
                self.assertEqual(dock.grip_overlay.pos()-dock.pos(),grip_offset)
                self.editor.recorder.active=False
                dock.sync()
                QTest.qWait(310)
                dock._dock_geometry_animation.setCurrentTime(
                    dock._dock_geometry_animation.duration())
                self.assertFalse(dock.control_island.isVisible())
                self.assertFalse(dock.grip_overlay.isVisible())
                self.assertIsNone(self.editor.recorder.interactive_bounds)
                self.assertIsNone(self.editor.recorder.interactive_grip_bounds)
                self.assertEqual(dock.height(),84)
                self.assertEqual(dock.body.objectName(),'dockBody')
        finally:
            self.editor.recorder.active=False
            dock.set_compact_mode(old)
            dock.hide()

    def test_windows_controller_pause_and_stop_mouse_clicks(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        dock=self.editor.dock
        try:
            dock.show()
            self.editor.recorder.active=True
            events=[]
            with patch.object(dock,'_avoid_stealing_focus'), \
                 patch('action_studio.ui.window_rect',side_effect=lambda hwnd: (
                     [500,30,116,64] if hwnd==int(dock.control_island.winId())
                     else [60,41,34,42])), \
                 patch.object(self.editor.recorder,'toggle_pause',
                              side_effect=lambda:events.append('pause')), \
                 patch.object(self.editor.recorder,'stop',
                              side_effect=lambda:events.append('stop')):
                dock.sync()
                self.qt.processEvents()
                QTest.mouseClick(dock.control_island.pause,Qt.LeftButton)
                QTest.mouseClick(dock.control_island.stop,Qt.LeftButton)
                self.assertEqual(events,['pause','stop'])
                self.assertTrue(dock.grip_overlay.drag_handle.isEnabled())
        finally:
            self.editor.recorder.active=False
            dock.sync()
            dock.hide()

    def test_smart_dock_does_not_steal_browser_focus_flag(self):
        from PySide6.QtCore import Qt
        dock=self.editor.dock
        island=dock.control_island
        grip=dock.grip_overlay
        for widget in (island,grip):
            self.assertTrue(bool(widget.windowFlags() & Qt.WindowDoesNotAcceptFocus))
            self.assertTrue(widget.testAttribute(Qt.WA_ShowWithoutActivating))
            self.assertTrue(widget.isWindow())
            self.assertIsNone(widget.parentWidget())
        self.assertTrue(dock.isWindow())
    def test_type_context_shows_typing_not_mouse_controls(self):
        action=self.Action(kind='type',text='example',char_delay=.1)
        self.editor.project.actions=[action]
        self.editor.refresh({action.id})
        menu=self.editor.build_action_context_menu(
            self.editor.table.visualRect(self.editor.table.model().index(0,0)).center())
        labels=[item.text() for item in menu.actions()]
        self.assertIn('Typing speed',labels)
        self.assertNotIn('Mouse speed',labels)
        self.assertNotIn('Wait duration',labels)
        typing=next(item.menu() for item in menu.actions()
                    if item.text()=='Typing speed')
        fast=next(item for item in typing.actions() if item.text()=='Fast')
        fast.trigger()
        self.assertEqual(action.typing_speed_override,'fast')
        self.assertEqual(self.editor._rows(),[0])
        self.assertIn('Typing: Fast',self.editor.table.item(0,2).text())

    def test_mixed_type_wait_mouse_selection_shows_relevant_categories(self):
        from PySide6.QtWidgets import QTableWidgetSelectionRange
        actions=[self.Action(kind='click'),self.Action(kind='type',text='test'),
                 self.Action(kind='wait',delay=3,wait_mode='duration'),
                 self.Action(kind='secure_input',secure_mode='skip'),
                 self.Action(kind='key',key='enter')]
        self.editor.project.actions=actions
        self.editor.refresh(set())
        self.editor.table.setRangeSelected(QTableWidgetSelectionRange(0,0,4,4),True)
        pos=self.editor.table.visualRect(self.editor.table.model().index(1,0)).center()
        menu=self.editor.build_action_context_menu(pos)
        labels=[item.text() for item in menu.actions()]
        for label in ('Mouse speed','Typing speed','Wait duration'):
            self.assertIn(label,labels)
        typing=next(item.menu() for item in menu.actions() if item.text()=='Typing speed')
        next(item for item in typing.actions() if item.text()=='Slow').trigger()
        self.assertEqual([a.typing_speed_override for a in actions],
                         ['inherit','slow','inherit','inherit','inherit'])
        self.assertEqual(self.editor._rows(),[0,1,2,3,4])

    def test_fixed_wait_context_has_wait_duration_but_no_speed_menu(self):
        a=self.Action(kind='wait',wait_mode='duration',delay=3)
        self.editor.project.actions=[a]
        self.editor.refresh({a.id})
        pos=self.editor.table.visualRect(self.editor.table.model().index(0,0)).center()
        menu=self.editor.build_action_context_menu(pos)
        labels=[item.text() for item in menu.actions()]
        self.assertIn('Wait duration',labels)
        self.assertNotIn('Mouse speed',labels)
        self.assertNotIn('Typing speed',labels)
        times=next(item.menu() for item in menu.actions() if item.text()=='Wait duration')
        next(item for item in times.actions() if item.text()=='5 seconds').trigger()
        self.assertEqual(a.delay,5)

    def test_mouse_speed_submenu_stays_accessible_during_hover(self):
        from PySide6.QtWidgets import QApplication
        a=self.Action(kind='click')
        self.editor.project.actions=[a]
        self.editor.refresh({a.id})
        pos=self.editor.table.visualRect(self.editor.table.model().index(0,0)).center()
        menu=self.editor.build_action_context_menu(pos)
        submenu=next(item.menu() for item in menu.actions() if item.text()=='Mouse speed')
        disable=next(item for item in menu.actions() if item.text()=='Disable selected')
        menu.show()
        submenu.show()
        QApplication.processEvents()
        self.assertTrue(submenu.isVisible())
        menu.hovered.emit(disable)
        self.assertTrue(submenu.isVisible(), 'App must not force-hide submenu during cursor travel')
        next(item for item in submenu.actions() if item.text()=='Fast').trigger()
        self.assertEqual(a.mouse_speed_override,'fast')
        menu.hide()

    def test_active_dock_centers_the_combined_capsule(self):
        from unittest.mock import patch
        from PySide6.QtGui import QGuiApplication
        dock=self.editor.dock
        old=dock.compact_active
        try:
            dock.set_compact_mode(True)
            self.editor.recorder.active=True
            with patch.object(dock,'_avoid_stealing_focus'), \
                 patch('action_studio.ui.window_rect',side_effect=lambda hwnd: (
                     [500,30,116,64] if hwnd==int(dock.control_island.winId())
                     else [60,41,34,42])):
                dock.show()
                dock.sync()
                dock.place('top',initially=True)
                from PySide6.QtTest import QTest
                QTest.qWait(310)
                dock._dock_geometry_animation.setCurrentTime(
                    dock._dock_geometry_animation.duration())
                self.qt.processEvents()
                area=QGuiApplication.primaryScreen().availableGeometry()
                full_width=dock.width()+dock.control_island.width()
                self.assertEqual(dock.x(),area.left()+(area.width()-full_width)//2)
                self.assertEqual(dock.control_island.x(),dock.x()+dock.width())
                self.assertEqual(dock.control_island.y(),dock.y())
                self.assertEqual(dock.control_island.height(),dock.height())
                self.assertEqual(dock.grip_overlay.x(),dock.x()+8)
                self.assertEqual(dock.grip_overlay.y(),
                                 dock.y()+(dock.height()-dock.grip_overlay.height())//2)
        finally:
            self.editor.recorder.active=False
            dock.sync()
            dock.set_compact_mode(old)
            dock.hide()

    def test_compact_replay_dock_auto_shrinks_and_sidecar_is_adjacent(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        dock=self.editor.dock
        old=dock.compact_active
        flag=SimpleNamespace(is_set=lambda:False)
        try:
            dock.set_compact_mode(True)
            self.editor.player=SimpleNamespace(
                isRunning=lambda:True,awaiting_secure_input=False,pause_flag=flag)
            with patch.object(dock,'_avoid_stealing_focus'), \
                 patch('action_studio.ui.window_rect',side_effect=lambda hwnd: (
                     [500,30,116,64] if hwnd==int(dock.control_island.winId())
                     else [60,41,34,42])):
                dock.show()
                dock.sync()
                from PySide6.QtTest import QTest
                QTest.qWait(310)
                dock._dock_geometry_animation.setCurrentTime(
                    dock._dock_geometry_animation.duration())
                self.qt.processEvents()
                self.assertEqual(dock.width(),290)
                self.assertEqual(dock.height(),64)
                self.assertFalse(dock.clock.isVisible())
                self.assertTrue(dock.step_status.isVisible())
                self.assertEqual(dock.control_island.x(), dock.x()+dock.width())
                self.assertEqual(dock.control_island.y(), dock.y())
                self.assertEqual(dock.width()+dock.control_island.width(),406)
                self.assertEqual(dock.grip_overlay.x(),dock.x()+8)
                self.assertEqual(dock.body.objectName(),'dockBodyJoinedLeft')
        finally:
            self.editor.player=None
            dock.set_compact_mode(old)
            dock.hide()


    def test_secure_preflight_explicitly_reuses_first_value(self):
        from action_studio.ui import SecurePreflightDialog
        names=[('a'*32,'First secure step'),('b'*32,'Second secure step')]
        dlg=SecurePreflightDialog(names,self.editor,allow_save=True)
        dlg.inputs[names[0][0]].setText('same-dummy-secret')
        dlg.apply_all.setChecked(True)
        self.assertFalse(dlg.inputs[names[1][0]].isEnabled())
        self.assertTrue(dlg.remember[names[0][0]].isChecked())
        from PySide6.QtWidgets import QDialog
        dlg._confirm()
        self.assertEqual(dlg.result(),QDialog.Accepted)
        self.assertEqual(dlg.submitted(),[
            (names[0][0],'same-dummy-secret',True),
            (names[1][0],'same-dummy-secret',True),
        ])
        dlg.close()

    def test_secure_inspector_apply_all_stores_one_shared_reference(self):
        from types import SimpleNamespace
        from action_studio.core import Project
        values={}
        fake=SimpleNamespace(
            set=lambda ref,value:values.__setitem__(ref,value),
            get=lambda ref:values.get(ref),
            delete=lambda ref:values.pop(ref,None))
        self.editor.credential_store=fake
        a=self.Action(kind='secure_input',secure_mode='auto')
        b=self.Action(kind='secure_input',secure_mode='auto')
        self.editor.project=Project(actions=[a,b])
        self.editor.refresh({a.id})
        self.editor.secret_edit.setText('shared-dummy-passphrase')
        self.editor.secret_remember.setChecked(True)
        self.editor.secret_apply_all.setChecked(True)
        self.editor.set_secure_value()
        self.assertEqual(a.secure_ref,b.secure_ref)
        self.assertEqual(values[a.secure_ref],'shared-dummy-passphrase')
        self.assertEqual(len(values),3)  # shared ref plus both stable action IDs
        self.assertEqual(values[a.id],'shared-dummy-passphrase')
        self.assertEqual(values[b.id],'shared-dummy-passphrase')
        self.assertNotIn('shared-dummy-passphrase',str(self.editor.project.to_dict()))
        # Editing one item later must not overwrite the still-shared value.
        self.editor.refresh({a.id})
        self.editor.secret_edit.setText('different-dummy-passphrase')
        self.editor.secret_apply_all.setChecked(False)
        self.editor.set_secure_value()
        self.assertNotEqual(a.secure_ref,b.secure_ref)
        self.assertEqual(values[b.secure_ref],'shared-dummy-passphrase')

    def test_secure_vault_alias_survives_unsaved_reference(self):
        from types import SimpleNamespace
        from action_studio.core import Project
        a=self.Action(kind='secure_input',secure_mode='auto')
        saved={a.id:'persisted-dummy'}
        self.editor.project=Project(actions=[a])
        self.editor.credential_store=SimpleNamespace(
            get=lambda ref:saved.get(ref),
            set=lambda ref,value:saved.__setitem__(ref,value),
            delete=lambda ref:saved.pop(ref,None))
        self.editor.refresh({a.id})
        self.assertEqual(a.secure_ref,'')
        self.assertEqual(self.editor._read_saved_secret(a),'persisted-dummy')
        self.assertTrue(self.editor._prepare_secure_values())
        self.assertEqual(self.editor.prepared_secure[a.id],'persisted-dummy')
        self.editor.prepared_secure.clear()
        self.editor.forget_secure_value()
        self.assertNotIn(a.id,saved)

    def test_dock_minimizes_to_taskbar_proxy(self):
        dock=self.editor.dock
        dock.show()
        self.qt.processEvents()
        dock.minimize_to_taskbar()
        self.qt.processEvents()
        self.assertTrue(self.editor._dock_taskbar_minimized)
        self.assertFalse(dock.isVisible())
        self.assertTrue(self.editor.isMinimized())
        self.editor.showNormal()
        self.qt.processEvents()
        from PySide6.QtTest import QTest
        QTest.qWait(40)
        self.assertFalse(self.editor._dock_taskbar_minimized)
        self.assertTrue(dock.isVisible())
        dock.hide()

    def test_taskbar_remains_available_during_recorder_mode(self):
        dock=self.editor.dock
        self.editor.show_dock()
        self.qt.processEvents()
        self.assertTrue(self.editor.isVisible())
        self.assertTrue(self.editor.isMinimized())
        self.assertTrue(dock.isVisible())
        dock.minimize_to_taskbar()
        self.qt.processEvents()
        self.assertTrue(self.editor.isVisible())
        self.assertTrue(self.editor.isMinimized())
        self.assertFalse(dock.isVisible())
        self.editor.showNormal()
        self.qt.processEvents()
        from PySide6.QtTest import QTest
        QTest.qWait(70)
        self.assertTrue(self.editor.isMinimized())
        self.assertTrue(dock.isVisible())
        self.editor.show_editor()
        self.qt.processEvents()
        self.assertFalse(self.editor._dock_taskbar_mode)
        self.assertTrue(self.editor.isVisible())
        self.assertFalse(dock.isVisible())

    def test_windows_taskbar_icon_is_loaded(self):
        from action_studio.ui import app_icon
        from PySide6.QtCore import QSize
        icon=app_icon()
        self.assertFalse(icon.isNull())
        self.assertFalse(icon.pixmap(QSize(32,32)).isNull())

    def test_compact_dock_retains_combined_center_on_resize(self):
        from PySide6.QtTest import QTest
        from unittest.mock import patch
        dock=self.editor.dock
        old=dock.compact_active
        try:
            with patch.object(dock,'_avoid_stealing_focus'), \
                 patch('action_studio.ui.window_rect',return_value=[400,20,116,64]):
                dock.show()
                dock.move(100,120)
                self.editor.recorder.active=True
                dock.set_compact_mode(True)
                dock.sync()
                QTest.qWait(300)
                dock._dock_geometry_animation.setCurrentTime(
                    dock._dock_geometry_animation.duration())
                compact_center=dock.x()+(dock.width()+dock.control_island.width())/2
                compact_y=dock.y()+dock.height()/2
                dock.set_compact_mode(False)
                QTest.qWait(300)
                dock._dock_geometry_animation.setCurrentTime(
                    dock._dock_geometry_animation.duration())
                self.assertAlmostEqual(dock.x()+(dock.width()+dock.control_island.width())/2,
                                       compact_center,delta=2)
                self.assertAlmostEqual(dock.y()+dock.height()/2,compact_y,delta=2)
                self.assertEqual(dock.grip_overlay.x(),dock.x()+8)
        finally:
            self.editor.recorder.active=False
            dock.sync()
            dock.set_compact_mode(old)
            dock.hide()

    def test_encrypted_save_open_and_export_require_no_passphrase_dialog(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from types import SimpleNamespace
        from unittest.mock import patch
        from action_studio.core import Project
        from action_studio.encrypted_projects import load_encrypted_project
        saved={}
        store=SimpleNamespace(
            set=lambda ref,value:saved.__setitem__(ref,value),
            get=lambda ref:saved.get(ref),
            delete=lambda ref:saved.pop(ref,None))
        self.editor.credential_store=store
        secure=self.Action(kind='secure_input',secure_mode='auto')
        self.editor.project=Project(name='Confidential sample',actions=[
            self.Action(kind='type',text='private content'),secure])
        self.editor.session_secrets={secure.id:'dummy saved input'}
        self.editor.name.setText('Confidential sample')
        self.editor.is_dirty=False
        with TemporaryDirectory() as directory:
            base=Path(directory)
            save_path=base/'saved.vas.json'
            export_path=base/'export.vas.json'
            self.editor.project_path=save_path
            with (patch('PySide6.QtWidgets.QMessageBox.critical') as fail,
                  patch('action_studio.ui.PortablePassphraseDialog',create=True,
                        side_effect=AssertionError('passphrase requested'))):
                self.assertTrue(self.editor.save())
                fail.assert_not_called()
            encrypted=save_path.read_text(encoding='utf-8')
            self.assertNotIn('private content',encrypted)
            self.assertNotIn('dummy saved input',encrypted)
            self.assertEqual(load_encrypted_project(save_path,store)[1][secure.id],
                             'dummy saved input')
            with patch('action_studio.ui.QFileDialog.getSaveFileName',
                       return_value=(str(export_path),'TakePath projects (*.vas.json)')):
                self.assertTrue(self.editor.export_encrypted_project())
            self.assertTrue(export_path.exists())
            self.assertEqual(load_encrypted_project(export_path,store)[1][secure.id],
                             'dummy saved input')
            self.editor.project_path=None
            self.editor.session_secrets.clear()
            with patch('action_studio.ui.QFileDialog.getOpenFileName',
                       return_value=(str(save_path),'TakePath projects (*.vas.json)')):
                self.editor.open_project()
            self.assertEqual(self.editor.project.actions[0].text,'private content')
            self.assertEqual(self.editor.session_secrets[secure.id],'dummy saved input')
            self.assertEqual(self.editor._snapshot_secure_values()[secure.id],
                             'dummy saved input')

    def test_encrypted_save_without_vault_fails_closed(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from unittest.mock import patch
        self.editor.credential_store=None
        with TemporaryDirectory() as directory:
            path=Path(directory)/'should-not-write.vas.json'
            self.editor.project_path=path
            with patch('PySide6.QtWidgets.QMessageBox.critical') as alert:
                self.assertFalse(self.editor.save())
                self.assertTrue(alert.called)
            self.assertFalse(path.exists())



if __name__=='__main__':
    unittest.main()
