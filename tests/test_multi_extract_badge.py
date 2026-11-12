import unittest
from types import SimpleNamespace

from qtpy.QtCore import QPointF, Qt
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QGraphicsScene

from ballontranslator.ui.text_engine.item import TextBlkItem, _ConflictBadgeItem
from ballontranslator.utils.multi_extract import has_conflict, resolve
from ballontranslator.utils.textblock import TextBlock

# Module-level reference: a local QApplication is destroyed on return, which
# deletes every widget created under it.
APP = None


def get_app():
    global APP
    if APP is None:
        APP = QApplication.instance() or QApplication([])
    return APP


def make_block(payload=None):
    block = TextBlock([0, 0, 300, 120])
    block._bounding_rect = [0, 0, 300, 120]
    block.vertical = True
    block.text = ['そういえば']
    if payload is not None:
        block.multi_extract = payload
    return block


def make_item(payload=None):
    item = TextBlkItem(make_block(payload), 0)
    scene = QGraphicsScene()
    scene.addItem(item)
    # The scene owns the items: keep it alive for as long as the item is used.
    item._test_scene = scene
    get_app().processEvents()
    return item


CONFLICT = {
    'chosen': 0,
    'support': [0, 1],
    'candidates': [{'pass': 1, 'text': ['そういえは']}],
}


class ConflictBadgeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = get_app()

    def test_block_without_payload_has_no_badge(self):
        item = make_item()

        self.assertFalse(item._conflict_badge_item.isVisible())

    def test_block_with_payload_shows_the_badge(self):
        item = make_item(CONFLICT)

        self.assertTrue(item._conflict_badge_item.isVisible())

    def test_badge_is_a_fixed_size_dot(self):
        badge = make_item(CONFLICT)._conflict_badge_item

        self.assertEqual(badge.boundingRect().size().width(), 15.6)
        self.assertEqual(badge.boundingRect().size().height(), 15.6)
        self.assertTrue(
            badge.flags()
            & badge.GraphicsItemFlag.ItemIgnoresTransformations
        )
        self.assertEqual(
            badge.acceptedMouseButtons(),
            Qt.MouseButton.LeftButton,
        )

    def test_badge_sits_inside_the_bottom_right_corner(self):
        item = make_item(CONFLICT)
        badge = item._conflict_badge_item
        outline = item.geometry_controller.visual_outline_in_item()
        bounds = outline.boundingRect()
        dot = badge.mapRectToItem(item, badge.boundingRect())

        # The badge is anchored on the block's bottom-right corner and paints
        # up and left from it, so the whole dot stays inside the block.
        self.assertAlmostEqual(
            badge.pos().x(), bounds.right(), places=1
        )
        self.assertAlmostEqual(
            badge.pos().y(), bounds.bottom(), places=1
        )
        self.assertLessEqual(dot.right(), bounds.right() + 0.01)
        self.assertLessEqual(dot.bottom(), bounds.bottom() + 0.01)
        self.assertGreaterEqual(dot.left(), bounds.left() - 0.01)
        self.assertGreaterEqual(dot.top(), bounds.top() - 0.01)
        self.assertGreater(dot.center().x(), bounds.center().x())
        self.assertGreater(dot.center().y(), bounds.center().y())

    def test_resolving_the_block_hides_the_badge(self):
        item = make_item(CONFLICT)

        resolve(item.blk, 1)
        item.refresh_conflict_badge()

        self.assertFalse(has_conflict(item.blk))
        self.assertFalse(item._conflict_badge_item.isVisible())
        self.assertEqual(item.blk.get_text(), 'そういえは')

    def test_editing_hides_the_badge_and_leaving_editing_restores_it(self):
        item = make_item(CONFLICT)

        item.startEdit()
        get_app().processEvents()
        self.assertFalse(item._conflict_badge_item.isVisible())

        item.endEdit()
        get_app().processEvents()
        self.assertTrue(item._conflict_badge_item.isVisible())

    def test_suppressing_ui_guides_hides_the_badge(self):
        item = make_item(CONFLICT)

        item.set_ui_guide_suppressed(True)
        self.assertFalse(item._conflict_badge_item.isVisible())

        item.set_ui_guide_suppressed(False)
        self.assertTrue(item._conflict_badge_item.isVisible())

    def test_badge_does_not_shift_the_block_position(self):
        plain = make_item()
        marked = make_item(CONFLICT)

        self.assertEqual(plain.pos(), QPointF(0, 0))
        self.assertEqual(marked.pos(), QPointF(0, 0))
        self.assertEqual(
            plain.geometry_controller.visual_outline_in_item().boundingRect(),
            marked.geometry_controller.visual_outline_in_item().boundingRect(),
        )


def badge_center():
    """The dot's centre in badge coordinates.

    The badge is anchored on the block's bottom-right corner and paints up and
    left from its origin, so its own geometry lives in negative space.
    """
    half = _ConflictBadgeItem.DIAMETER / 2
    return QPointF(-half - _ConflictBadgeItem.INSET, -half - _ConflictBadgeItem.INSET)


class _FakeMouseEvent:
    """PyQt6 refuses to build scene mouse events, so mimic the two members
    the badge reads: the local position and ``accept()``."""

    def __init__(self, pos=None):
        self._pos = QPointF(pos) if pos is not None else badge_center()
        self.accepted = False

    def pos(self):
        return self._pos

    def accept(self):
        self.accepted = True


class ConflictBadgeClickTest(unittest.TestCase):
    """The badge is the in-canvas entry point of the review dialog."""

    @classmethod
    def setUpClass(cls):
        cls.app = get_app()

    def test_badge_is_clickable(self):
        badge = make_item(CONFLICT)._conflict_badge_item

        self.assertEqual(
            badge.acceptedMouseButtons(),
            Qt.MouseButton.LeftButton,
        )
        self.assertEqual(
            badge.cursor().shape(),
            Qt.CursorShape.PointingHandCursor,
        )
        self.assertTrue(badge.toolTip())

    def test_clicking_the_badge_requests_a_review(self):
        item = make_item(CONFLICT)
        requests = []
        item.review_multi_extract.connect(lambda: requests.append(True))
        badge = item._conflict_badge_item
        press = _FakeMouseEvent()
        release = _FakeMouseEvent()

        badge.mousePressEvent(press)
        badge.mouseReleaseEvent(release)

        self.assertTrue(press.accepted)
        self.assertTrue(release.accepted)
        self.assertEqual(requests, [True])

    def test_pressing_requests_nothing(self):
        item = make_item(CONFLICT)
        requests = []
        item.review_multi_extract.connect(lambda: requests.append(True))

        item._conflict_badge_item.mousePressEvent(_FakeMouseEvent())

        self.assertEqual(requests, [])

    def test_releasing_outside_the_badge_requests_nothing(self):
        item = make_item(CONFLICT)
        requests = []
        item.review_multi_extract.connect(lambda: requests.append(True))

        item._conflict_badge_item.mouseReleaseEvent(
            _FakeMouseEvent(QPointF(-40.0, -40.0))
        )

        self.assertEqual(requests, [])


class ConflictBadgeCanvasClickTest(unittest.TestCase):
    """The canvas must hand the badge its own pixels.

    The badge sits inside the block's bottom-right area, where the block's
    drag/reshape handling also claims the press.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = get_app()

    def _canvas(self):
        from ballontranslator.ui.canvas import Canvas

        canvas = Canvas()
        canvas.imgtrans_proj = SimpleNamespace(
            img_valid=True,
            current_img='a.jpg',
            pages={'a.jpg': []},
        )
        canvas.gv.resize(600, 400)
        canvas.gv.show()
        self.addCleanup(self._destroy, canvas)
        self.app.processEvents()
        return canvas

    @staticmethod
    def _destroy(canvas):
        canvas.gv.setParent(None)
        canvas.gv.deleteLater()
        get_app().processEvents()

    def test_clicking_a_selected_blocks_badge_requests_review(self):
        canvas = self._canvas()
        item = TextBlkItem(make_block(CONFLICT), 0)
        canvas.addItem(item)
        item.setSelected(True)
        canvas.txtblkShapeControl.setBlkItem(item)
        self.app.processEvents()
        requests = []
        item.review_multi_extract.connect(lambda: requests.append(True))
        badge = item._conflict_badge_item
        center = badge.mapToScene(badge.boundingRect().center())

        QTest.mouseClick(
            canvas.gv.viewport(),
            Qt.MouseButton.LeftButton,
            pos=canvas.gv.mapFromScene(center),
        )
        self.app.processEvents()

        self.assertEqual(requests, [True])
        # The press must not start a reshape or move the block.
        self.assertFalse(item.reshaping)
        self.assertEqual(item.pos(), QPointF(0, 0))

    def test_clicking_away_does_not_request_review(self):
        canvas = self._canvas()
        item = TextBlkItem(make_block(CONFLICT), 0)
        canvas.addItem(item)
        self.app.processEvents()
        requests = []
        item.review_multi_extract.connect(lambda: requests.append(True))

        QTest.mouseClick(
            canvas.gv.viewport(),
            Qt.MouseButton.LeftButton,
            pos=canvas.gv.mapFromScene(QPointF(20.0, 20.0)),
        )
        self.app.processEvents()

        self.assertEqual(requests, [])


if __name__ == '__main__':
    unittest.main()
