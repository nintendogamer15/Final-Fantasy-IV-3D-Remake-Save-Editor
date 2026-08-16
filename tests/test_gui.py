from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from ffiv3d_save_gui import FFIV3DSaveGUI
except ModuleNotFoundError:
    QApplication = None
    FFIV3DSaveGUI = None

import ffiv3d_save_tool as tool
from tests.helpers import make_save


@unittest.skipIf(QApplication is None, "PySide6 is not installed")
class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_load_render_and_max_party(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "SAVE.BIN"
            path.write_bytes(make_save())
            window = FFIV3DSaveGUI(str(path))
            try:
                self.assertEqual(window._party_tables["1"].rowCount(), 1)
                window._max_party()
                char = tool.char_base(tool.VISIBLE_SLOT_BASES[1], 1)
                self.assertEqual(window.data[char + tool.LEVEL_REL], 99)
                self.assertEqual(tool.u32(window.data, char + tool.CUR_HP_REL), 9_999)
            finally:
                window.close()

    def test_atomic_output_and_numbered_backup_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "SAVE.BIN"
            tool.atomic_write(path, b"first")
            self.assertEqual(path.read_bytes(), b"first")
            first = tool.available_backup_path(path)
            tool.atomic_write(first, b"backup")
            self.assertEqual(tool.available_backup_path(path).name, "SAVE.BIN.bak.1")


if __name__ == "__main__":
    unittest.main()
