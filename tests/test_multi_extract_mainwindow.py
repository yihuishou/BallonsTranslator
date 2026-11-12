import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from qtpy.QtCore import QPoint, QPointF, QRect, QRectF
from qtpy.QtWidgets import QApplication, QMainWindow

from ballontranslator.ui import mainwindow
from ballontranslator.ui.mainwindow import MainWindow
from ballontranslator.ui.mainwindowbars import LeftBar, TitleBar
from ballontranslator.ui.text_engine.editing.manager import SceneTextManager
from ballontranslator.utils.multi_extract import has_conflict
from ballontranslator.utils.textblock import TextBlock

_APP = None


def qapp() -> QApplication:
    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication(sys.argv[:1])
    return _APP


class FakeAction:
    def __init__(self):
        self.enabled = True

    def setEnabled(self, enabled):
        self.enabled = bool(enabled)

    def isEnabled(self):
        return self.enabled


def make_block(text='そういえば', candidate='そういえは'):
    block = TextBlock([0, 0, 120, 60])
    block._bounding_rect = [0, 0, 120, 60]
    block.text = [text]
    block.multi_extract = {
        'chosen': 0,
        'support': [0, 1],
        'candidates': [{'pass': 1, 'text': [candidate]}],
    }
    return block


class ReviewActionStateTest(unittest.TestCase):

    def _host(self, pages):
        return SimpleNamespace(
            imgtrans_proj=SimpleNamespace(pages=pages),
            titleBar=SimpleNamespace(reviewMultiExtractAction=FakeAction()),
        )

    def test_action_is_disabled_without_conflicts(self):
        host = self._host({'a.jpg': [make_block()]})
        host.imgtrans_proj.pages['a.jpg'][0].multi_extract = {}

        MainWindow._refresh_multi_extract_review_action(host)

        self.assertFalse(host.titleBar.reviewMultiExtractAction.isEnabled())

    def test_action_is_enabled_with_conflicts(self):
        host = self._host({'a.jpg': [make_block()]})

        MainWindow._refresh_multi_extract_review_action(host)

        self.assertTrue(host.titleBar.reviewMultiExtractAction.isEnabled())

    def test_missing_action_is_tolerated(self):
        host = SimpleNamespace(
            imgtrans_proj=SimpleNamespace(pages={'a.jpg': [make_block()]}),
            titleBar=SimpleNamespace(),
        )

        MainWindow._refresh_multi_extract_review_action(host)


class ApplyReadingTest(unittest.TestCase):

    def _host(self):
        host = SimpleNamespace(
            imgtrans_proj=SimpleNamespace(current_img='a.jpg', pages={}),
            canvas=SimpleNamespace(
                textEditMode=lambda: False,
                saved=[], 
                setProjSaveState=lambda value: host.canvas.saved.append(value),
                update=lambda: None,
            ),
            st_manager=SimpleNamespace(
                textblk_item_list=[],
                pairwidget_list=[],
            ),
            titleBar=SimpleNamespace(reviewMultiExtractAction=FakeAction()),
        )
        # Bound helpers the method under test calls on itself.
        host._refresh_resolved_block = (
            lambda page, blk: MainWindow._refresh_resolved_block(host, page, blk)
        )
        host._refresh_multi_extract_review_action = (
            lambda: MainWindow._refresh_multi_extract_review_action(host)
        )
        return host

    def test_applying_outside_text_mode_writes_text_and_marks_the_project(self):
        block = make_block()
        host = self._host()
        host.imgtrans_proj.pages['a.jpg'] = [block]

        MainWindow._apply_multi_extract_reading(host, 'a.jpg', block, 1)

        self.assertEqual(block.get_text(), 'そういえは')
        self.assertFalse(has_conflict(block))
        self.assertEqual(host.canvas.saved, [True])
        self.assertFalse(host.titleBar.reviewMultiExtractAction.isEnabled())

    def test_refreshing_a_block_on_another_page_is_a_no_op(self):
        block = make_block()
        host = self._host()
        host.imgtrans_proj.current_img = 'b.jpg'
        host.imgtrans_proj.pages['a.jpg'] = [block]

        MainWindow._refresh_resolved_block(host, 'a.jpg', block)

        self.assertEqual(host.canvas.saved, [])

    def test_refreshing_missing_block_does_not_raise(self):
        host = self._host()
        host.imgtrans_proj.pages['a.jpg'] = []

        MainWindow._refresh_resolved_block(host, 'a.jpg', make_block())


class FakeViewport:
    """Just enough of a view to report where its middle lands."""

    def rect(self):
        return QRect(0, 0, 100, 100)

    def mapTo(self, _widget, point):
        return point


class FakeView:
    def __init__(self, center):
        self._center = QPoint(*center)
        self._viewport = FakeViewport()

    def viewport(self):
        return self._viewport

    def mapToGlobal(self, _point):
        return self._center


class FakeScreen:
    def __init__(self, rect):
        self._rect = rect

    def availableGeometry(self):
        return self._rect


class LocateReviewedBlockTest(unittest.TestCase):
    """The reviewed block is centered on the canvas after its page switch."""

    class _Item:
        def __init__(self, blk, rect):
            self.blk = blk
            self._rect = rect

        def sceneBoundingRect(self):
            return self._rect

    class _View:
        def __init__(self):
            self.centered = []

        def centerOn(self, point):
            self.centered.append(point)

    def _host(self, blocks, current_img='a.jpg'):
        host = SimpleNamespace(
            imgtrans_proj=SimpleNamespace(
                current_img=current_img,
                pages={'a.jpg': blocks},
                pagename2idx=lambda page: 0 if page == 'a.jpg' else -1,
            ),
            pageList=SimpleNamespace(
                rows=[],
                setCurrentRow=lambda row: host.pageList.rows.append(row),
            ),
            st_manager=SimpleNamespace(textblk_item_list=[]),
            canvas=SimpleNamespace(gv=self._View()),
        )
        return host

    def test_another_page_is_opened_and_the_block_is_centered(self):
        block = make_block()
        host = self._host([block], current_img='b.jpg')
        host.st_manager.textblk_item_list = [
            self._Item(block, QRectF(0, 0, 100, 50))
        ]

        MainWindow._locate_multi_extract_block(host, 'a.jpg', block)

        self.assertEqual(host.pageList.rows, [0])
        self.assertEqual(host.canvas.gv.centered, [QPointF(50, 25)])

    def test_the_current_page_is_kept_and_the_block_is_centered(self):
        block = make_block()
        host = self._host([block], current_img='a.jpg')
        host.st_manager.textblk_item_list = [
            self._Item(block, QRectF(10, 20, 40, 60))
        ]

        MainWindow._locate_multi_extract_block(host, 'a.jpg', block)

        self.assertEqual(host.pageList.rows, [])
        self.assertEqual(host.canvas.gv.centered, [QPointF(30, 50)])

    def test_a_block_outside_the_page_is_not_centered(self):
        block = make_block()
        host = self._host([block], current_img='a.jpg')
        host.st_manager.textblk_item_list = []

        MainWindow._locate_multi_extract_block(host, 'a.jpg', block)

        self.assertEqual(host.canvas.gv.centered, [])

    def test_an_unknown_page_is_ignored(self):
        block = make_block()
        host = self._host([block], current_img='a.jpg')
        host.st_manager.textblk_item_list = [
            self._Item(block, QRectF(0, 0, 100, 50))
        ]

        MainWindow._locate_multi_extract_block(host, 'missing.jpg', block)

        self.assertEqual(host.pageList.rows, [])
        self.assertEqual(host.canvas.gv.centered, [])


class ReviewWindowTest(unittest.TestCase):
    """The review window runs beside the canvas instead of blocking it."""

    class _Signal:
        def __init__(self):
            self.slots = []

        def connect(self, slot):
            self.slots.append(slot)

        def emit(self, *args):
            for slot in self.slots:
                slot(*args)

    class _FakeDialog:
        def __init__(self, project, apply_callback=None, locate_callback=None, parent=None):
            self.project = project
            self.apply_callback = apply_callback
            self.locate_callback = locate_callback
            self.finished = ReviewWindowTest._Signal()
            self.shown = False
            self.exec_calls = 0
            self.refreshed = False
            self.deleted = False

        def show(self):
            self.shown = True

        def exec_(self):
            self.exec_calls += 1

        def raise_(self):
            pass

        def activateWindow(self):
            pass

        def refresh(self):
            self.refreshed = True

        def reject(self):
            self.finished.emit(0)

        def deleteLater(self):
            self.deleted = True

        def width(self):
            return 820

        def height(self):
            return 460

        def resize(self, width, height):
            self.size = (width, height)

        def move(self, x, y):
            self.position = (x, y)

    def _host(self, pages):
        host = SimpleNamespace(
            imgtrans_proj=SimpleNamespace(pages=pages),
            _multi_extract_review_dialog=None,
            canvas=SimpleNamespace(gv=FakeView((0, 0))),
            screen=lambda: FakeScreen(QRect(0, 0, 1920, 1080)),
        )
        host._refresh_multi_extract_review_action = lambda: None
        host._apply_multi_extract_reading = lambda page, blk, index: None
        host._locate_multi_extract_block = lambda page, blk: None
        host._on_multi_extract_review_closed = (
            lambda result: MainWindow._on_multi_extract_review_closed(host, result)
        )
        host._place_multi_extract_review_dialog = (
            lambda dialog: MainWindow._place_multi_extract_review_dialog(host, dialog)
        )
        host._canvas_center_on_screen = (
            lambda: MainWindow._canvas_center_on_screen(host)
        )
        return host

    def _run(self, host):
        created = []

        def factory(*args, **kwargs):
            dialog = self._FakeDialog(*args, **kwargs)
            created.append(dialog)
            return dialog

        with mock.patch.object(
            mainwindow, 'MultiExtractReviewDialog', factory
        ):
            MainWindow.on_review_multi_extract(host)
        return created

    def test_the_window_is_shown_without_blocking_the_canvas(self):
        host = self._host({'a.jpg': [make_block()]})

        created = self._run(host)

        self.assertEqual(len(created), 1)
        self.assertTrue(created[0].shown)
        self.assertEqual(created[0].exec_calls, 0)

    def test_the_window_reports_the_picked_block_to_the_canvas(self):
        host = self._host({'a.jpg': [make_block()]})
        located = []
        host._locate_multi_extract_block = lambda page, blk: located.append(page)

        created = self._run(host)

        created[0].locate_callback('a.jpg', make_block())
        self.assertEqual(located, ['a.jpg'])

    def test_opening_the_window_again_reuses_it(self):
        host = self._host({'a.jpg': [make_block()]})

        created = self._run(host)
        self._run(host)

        self.assertEqual(len(created), 1)
        self.assertTrue(created[0].refreshed)

    def test_closing_the_window_releases_it(self):
        host = self._host({'a.jpg': [make_block()]})

        created = self._run(host)
        created[0].finished.emit(0)

        self.assertIsNone(host._multi_extract_review_dialog)
        self.assertTrue(created[0].deleted)


class ReviewDialogPlacementTest(unittest.TestCase):
    """The review window must not sit on the canvas' middle."""

    def _host(self, center):
        host = SimpleNamespace(
            canvas=SimpleNamespace(gv=FakeView(center)),
            screen=lambda: FakeScreen(QRect(0, 0, 1920, 1080)),
        )
        host._canvas_center_on_screen = (
            lambda: MainWindow._canvas_center_on_screen(host)
        )
        return host

    class _Dialog:
        def __init__(self):
            self.size = (0, 0)
            self.position = (0, 0)

        def width(self):
            return 820

        def height(self):
            return 460

        def resize(self, width, height):
            self.size = (width, height)

        def move(self, x, y):
            self.position = (x, y)

    def test_the_window_goes_to_the_corner_that_leaves_the_canvas_alone(self):
        host = self._host((1500, 800))
        dialog = self._Dialog()

        MainWindow._place_multi_extract_review_dialog(host, dialog)

        # The bottom right corner would cover the canvas middle.
        self.assertEqual(dialog.position, (20, 599))

    def test_a_free_corner_is_used_as_is(self):
        host = self._host((400, 300))
        dialog = self._Dialog()

        MainWindow._place_multi_extract_review_dialog(host, dialog)

        self.assertEqual(dialog.position, (1079, 599))


class ReviewMenuOwnershipTest(unittest.TestCase):
    """The review entry is wired to the bar that actually owns the Edit menu.

    SetupUi connects this signal through a parent window attribute, so a bar
    swap compiles and imports fine and only fails when the window is built.
    """

    def _bar(self, kind):
        app = qapp()
        host = QMainWindow()
        bar = kind(host)
        app.processEvents()
        self.addCleanup(host.deleteLater)
        self.addCleanup(bar.deleteLater)
        return bar

    def test_title_bar_exposes_the_review_trigger(self):
        bar = self._bar(TitleBar)

        self.assertTrue(hasattr(bar, 'review_multi_extract_trigger'))
        self.assertTrue(
            any(
                action is bar.reviewMultiExtractAction
                for action in bar.editToolBtn.menu().actions()
            )
        )

    def test_left_bar_does_not_expose_the_review_trigger(self):
        bar = self._bar(LeftBar)

        self.assertFalse(hasattr(bar, 'review_multi_extract_trigger'))


class ReviewRequestForwardingTest(unittest.TestCase):
    """A badge click is forwarded only after the scene unwinds its press."""

    class _Signal:
        def __init__(self):
            self.emitted = 0

        def emit(self):
            self.emitted += 1

    def test_forwarding_waits_for_the_next_event_loop_pass(self):
        qapp()
        signal = self._Signal()
        manager = SimpleNamespace(review_multi_extract_requested=signal)

        SceneTextManager.on_review_multi_extract_requested(manager)

        self.assertEqual(signal.emitted, 0)
        qapp().processEvents()
        self.assertEqual(signal.emitted, 1)


if __name__ == '__main__':
    unittest.main()
