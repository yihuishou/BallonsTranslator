import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from qtpy.QtCore import QRect, Qt
from qtpy.QtWidgets import QApplication, QLabel, QWidget

from ballontranslator.ui.adaptive_wrap_layout import AdaptiveWrapLayout
from ballontranslator.ui.text_engine.formatting.advanced import _atomic_unit


class AdaptiveWrapLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_expanding_units_fill_available_row_width(self):
        host = QWidget()
        layout = AdaptiveWrapLayout(
            host, horizontal_spacing=5, vertical_spacing=5
        )
        first = _atomic_unit(host, QLabel('First'))
        second = _atomic_unit(host, QLabel('Second'))
        layout.addWidget(first)
        layout.addWidget(second)

        layout.setGeometry(QRect(0, 0, 300, 40))

        self.assertEqual(second.geometry().right(), layout.contentsRect().right())

    def test_items_are_left_aligned_by_default(self):
        host = QWidget()
        layout = AdaptiveWrapLayout(host, horizontal_spacing=5, vertical_spacing=5)
        first = _atomic_unit(host, QLabel('First'))
        second = _atomic_unit(host, QLabel('Second'))
        layout.addWidget(first)
        layout.addWidget(second)

        layout.setGeometry(QRect(0, 0, 300, 40))

        self.assertEqual(first.geometry().left(), layout.contentsRect().left())

    def test_item_alignment_centers_every_row(self):
        host = QWidget()
        layout = AdaptiveWrapLayout(host, horizontal_spacing=5, vertical_spacing=5)
        first = _atomic_unit(host, QLabel('First'))
        second = _atomic_unit(host, QLabel('Second'))
        layout.addWidget(first)
        layout.addWidget(second)
        layout.setItemAlignment(Qt.AlignmentFlag.AlignHCenter)

        layout.setGeometry(QRect(0, 0, 300, 40))

        contents = layout.contentsRect()
        row_left = first.geometry().left()
        row_right = second.geometry().right()
        # The row content is centered inside the available width.
        self.assertAlmostEqual(
            row_left - contents.left(), contents.right() - row_right, delta=1
        )


if __name__ == '__main__':
    unittest.main()
