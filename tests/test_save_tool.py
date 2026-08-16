from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import ffiv3d_save_tool as tool
from tests.helpers import make_save


class SaveLayoutTests(unittest.TestCase):
    def test_synthetic_save_has_valid_checksums(self) -> None:
        save = make_save()
        for _base, _stored, _calculated, valid in tool.checksum_status(
            save, [tool.VISIBLE_SLOT_BASES[1], tool.REDUNDANT_COPY_BASE]
        ):
            self.assertTrue(valid)

    def test_checksum_repair_tracks_body_changes(self) -> None:
        save = make_save()
        base = tool.VISIBLE_SLOT_BASES[1]
        save[base + tool.GIL_REL] ^= 0xFF
        self.assertNotEqual(
            tool.u32(save, base + tool.CHECKSUM_REL),
            tool.checksum_for_copy(save, base),
        )
        tool.fix_checksums(save, [base])
        self.assertEqual(
            tool.u32(save, base + tool.CHECKSUM_REL),
            tool.checksum_for_copy(save, base),
        )

    def test_visible_target_includes_occupied_redundant_copy(self) -> None:
        save = make_save()
        self.assertEqual(
            tool.select_copy_bases(save, "1"),
            [tool.VISIBLE_SLOT_BASES[1], tool.REDUNDANT_COPY_BASE],
        )

    def test_max_party_updates_detailed_and_quick_values(self) -> None:
        save = make_save()
        bases = tool.select_copy_bases(save, "1")
        result = tool.max_party(save, bases)
        tool.fix_checksums(save, bases)

        self.assertEqual(result[tool.VISIBLE_SLOT_BASES[1]], [1])
        for base in bases:
            char = tool.char_base(base, 1)
            self.assertEqual(save[char + tool.LEVEL_REL], 99)
            self.assertEqual(tool.u32(save, char + tool.CUR_HP_REL), 9_999)
            self.assertEqual(tool.u16(save, char + tool.HP_CAP_SOURCE_REL), 9_999)
            self.assertEqual(tool.u32(save, char + tool.CUR_MP_REL), 999)
            self.assertEqual(tool.u16(save, char + tool.MP_CAP_SOURCE_REL), 999)
            self.assertEqual(
                tool.u32(save, base + tool.CHECKSUM_REL),
                tool.checksum_for_copy(save, base),
            )

    def test_inventory_upsert_preserves_order_and_raises_quantity(self) -> None:
        save = make_save()
        base = tool.VISIBLE_SLOT_BASES[1]
        tool.upsert_inventory(save, [5001, 5002], quantity=20, bases=[base])
        self.assertEqual(tool.inventory_entries(save, base), [(5001, 20), (5002, 20)])

    def test_wrong_file_size_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unexpected file size"):
            tool.validate_save_size(b"not a save")

    def test_full_validation_rejects_same_size_non_save(self) -> None:
        with self.assertRaisesRegex(ValueError, "No FFIV 3D save-copy header"):
            tool.validate_save(bytes(tool.SAVE_SIZE))

        save = make_save()
        save[tool.VISIBLE_SLOT_BASES[1] + tool.CHECKSUM_REL] ^= 0xFF
        tool.validate_save(save)  # Invalid checksums must remain repairable.

    def test_inventory_input_bounds_are_enforced(self) -> None:
        save = make_save()
        original = bytes(save)
        for quantity in (0, -1, 100, 65_535):
            with self.subTest(quantity=quantity):
                with self.assertRaisesRegex(ValueError, "Quantity"):
                    tool.upsert_inventory(save, [5002], quantity=quantity, bases=[0])
                self.assertEqual(bytes(save), original)

        for token in ("0", "-1", "0x10000", f"0x{tool.EMPTY_ID:X}"):
            with self.subTest(token=token):
                with self.assertRaisesRegex(ValueError, "Item ID"):
                    tool.resolve_item_id(token)

    def test_inventory_update_is_transactional_across_copies(self) -> None:
        save = make_save()
        full = [(1000 + index, 1) for index in range(tool.INVENTORY_CAPACITY)]
        tool.write_inventory_entries(save, tool.REDUNDANT_COPY_BASE, full)
        original = bytes(save)

        with self.assertRaisesRegex(ValueError, "capacity"):
            tool.upsert_inventory(
                save,
                [5002],
                quantity=20,
                bases=[tool.VISIBLE_SLOT_BASES[1], tool.REDUNDANT_COPY_BASE],
            )
        self.assertEqual(bytes(save), original)

    def test_equip_best_accepts_one_shot_base_iterables(self) -> None:
        save = make_save()
        bases = [tool.VISIBLE_SLOT_BASES[1], tool.REDUNDANT_COPY_BASE]
        changed = tool.equip_best_final_party(save, (base for base in bases))
        self.assertIn("Cecil@slot1", changed)
        for base in bases:
            self.assertIn(6007, dict(tool.inventory_entries(save, base)))

    def test_safe_writes_refuse_input_and_preserve_numbered_backups(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "SAVE.BIN"
            original = bytes(make_save())
            first_edit = bytearray(original)
            first_edit[tool.VISIBLE_SLOT_BASES[1] + tool.GIL_REL] = 1
            second_edit = bytearray(first_edit)
            second_edit[tool.VISIBLE_SLOT_BASES[1] + tool.GIL_REL] = 2
            path.write_bytes(original)

            with self.assertRaisesRegex(ValueError, "loaded input"):
                tool.write_new_save(path, path, first_edit)
            self.assertEqual(path.read_bytes(), original)

            first_backup = tool.write_in_place_with_backup(path, first_edit)
            second_backup = tool.write_in_place_with_backup(path, second_edit)
            self.assertEqual(first_backup.name, "SAVE.BIN.bak")
            self.assertEqual(second_backup.name, "SAVE.BIN.bak.1")
            self.assertEqual(first_backup.read_bytes(), original)
            self.assertEqual(second_backup.read_bytes(), bytes(first_edit))
            self.assertEqual(path.read_bytes(), bytes(second_edit))

    def test_cli_reports_bad_files_and_output_conflicts_without_tracebacks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            invalid = temp / "INVALID.BIN"
            invalid.write_bytes(bytes(tool.SAVE_SIZE))
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
                result = tool.main([str(invalid), "--inspect"])
            self.assertEqual(result, 2)
            self.assertIn("not a valid SAVE.BIN", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
                result = tool.main([str(temp / "MISSING.BIN"), "--inspect"])
            self.assertEqual(result, 1)
            self.assertIn("could not read", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

            save_path = temp / "SAVE.BIN"
            original = bytes(make_save())
            save_path.write_bytes(original)
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
                result = tool.main(
                    [str(save_path), "--fix-checksum", "--out", str(save_path)]
                )
            self.assertEqual(result, 2)
            self.assertIn("loaded input", stderr.getvalue())
            self.assertEqual(save_path.read_bytes(), original)

    def test_cli_successfully_writes_an_atomic_edited_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            save_path = temp / "SAVE.BIN"
            output_path = temp / "SAVE_EDITED.BIN"
            original = bytes(make_save())
            save_path.write_bytes(original)

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                io.StringIO()
            ):
                result = tool.main(
                    [
                        str(save_path),
                        "--slot",
                        "1",
                        "--max-party",
                        "--out",
                        str(output_path),
                    ]
                )

            self.assertEqual(result, 0)
            self.assertEqual(save_path.read_bytes(), original)
            edited = output_path.read_bytes()
            tool.validate_save(edited)
            for base in (tool.VISIBLE_SLOT_BASES[1], tool.REDUNDANT_COPY_BASE):
                self.assertEqual(
                    tool.u32(edited, base + tool.CHECKSUM_REL),
                    tool.checksum_for_copy(edited, base),
                )

    def test_list_known_does_not_require_a_save(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = tool.main(["--list-known", "ragnarok"])
        self.assertEqual(result, 0)
        self.assertIn("Ragnarok", output.getvalue())


if __name__ == "__main__":
    unittest.main()
