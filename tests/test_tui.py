from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    from ffiv3d_save_tui import FFIVSaveApp
    from textual.widgets import Input
except ModuleNotFoundError:
    FFIVSaveApp = None
    Input = None

import ffiv3d_save_tool as tool
from tests.helpers import make_save


@unittest.skipIf(FFIVSaveApp is None, "Textual is not installed")
class TuiSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_load_and_max_party(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "SAVE.BIN"
            path.write_bytes(make_save())
            app = FFIVSaveApp(str(path))

            async with app.run_test(size=(140, 50)) as pilot:
                await pilot.pause()
                await pilot.click("#max_party_btn")
                await pilot.pause()
                char = tool.char_base(tool.VISIBLE_SLOT_BASES[1], 1)
                self.assertEqual(app.data[char + tool.LEVEL_REL], 99)
                self.assertEqual(tool.u32(app.data, char + tool.CUR_HP_REL), 9_999)

    async def test_invalid_or_failed_edits_do_not_mutate_loaded_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "SAVE.BIN"
            path.write_bytes(make_save())
            app = FFIVSaveApp(str(path))

            async with app.run_test(size=(140, 50)) as pilot:
                await pilot.pause()
                original = bytes(app.data)

                app.query_one("#quantity_input", Input).value = "100"
                await pilot.click("#give_items_btn")
                await pilot.pause()
                self.assertEqual(bytes(app.data), original)

                def fail_after_mutation(candidate: bytearray, bases: list[int]) -> str:
                    candidate[bases[0] + tool.GIL_REL] ^= 0xFF
                    raise ValueError("synthetic failure")

                app._perform_edit(fail_after_mutation)
                self.assertEqual(bytes(app.data), original)


if __name__ == "__main__":
    unittest.main()
