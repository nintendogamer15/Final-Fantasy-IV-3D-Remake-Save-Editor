#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 FFIV 3D Save Tool contributors
"""Qt (PySide6) GUI for the FFIV 3D Remake SAVE.BIN editor.

All save offsets, checksums, and editing operations remain in
``ffiv3d_save_tool.py``.  This module only presents those operations through
the same Qt/Fusion desktop framework used by the FFIX Save Editor.
"""
from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import ffiv3d_save_tool as tool


ASSETS_DIR = Path(__file__).resolve().parent / "assets"
SLOT_CHOICES = (
    ("1", "Slot 1"),
    ("2", "Slot 2"),
    ("3", "Slot 3"),
    ("all", "All occupied slots"),
)
PARTY_HEADINGS = ("Roster #", "Level", "HP", "MP", "STR", "STA", "SPD", "INT", "SPI")
INVENTORY_HEADINGS = ("ID", "Name", "Quantity")


def _dark_palette() -> QPalette:
    palette = QPalette()
    window = QColor(37, 37, 38)
    base = QColor(30, 30, 30)
    text = QColor(240, 240, 240)
    disabled = QColor(127, 127, 127)
    highlight = QColor(106, 90, 205)
    palette.setColor(QPalette.Window, window)
    palette.setColor(QPalette.WindowText, text)
    palette.setColor(QPalette.Base, base)
    palette.setColor(QPalette.AlternateBase, QColor(45, 45, 48))
    palette.setColor(QPalette.ToolTipBase, window)
    palette.setColor(QPalette.ToolTipText, text)
    palette.setColor(QPalette.Text, text)
    palette.setColor(QPalette.Disabled, QPalette.Text, disabled)
    palette.setColor(QPalette.Button, window)
    palette.setColor(QPalette.ButtonText, text)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, disabled)
    palette.setColor(QPalette.BrightText, QColor(255, 80, 80))
    palette.setColor(QPalette.Link, highlight)
    palette.setColor(QPalette.Highlight, highlight)
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    return palette


def _make_table(headings: tuple[str, ...]) -> QTableWidget:
    table = QTableWidget(0, len(headings))
    table.setHorizontalHeaderLabels(headings)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    return table


def _set_row(table: QTableWidget, row: int, values: tuple[object, ...]) -> None:
    for column, value in enumerate(values):
        item = QTableWidgetItem(str(value))
        item.setTextAlignment(Qt.AlignCenter)
        table.setItem(row, column, item)


class FFIV3DSaveGUI(QMainWindow):
    """Point-and-click editor backed exclusively by ``ffiv3d_save_tool``."""

    def __init__(self, save_path: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Final Fantasy IV 3D Remake Save Editor")
        icon_path = ASSETS_DIR / "icon.svg"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1240, 860)

        self.save_path = Path(save_path) if save_path else None
        self.data: bytearray | None = None
        self._dark = True
        self._light_palette = QApplication.palette()
        self._syncing_slot = False
        self._status_labels: dict[str, QLabel] = {}
        self._party_tables: dict[str, QTableWidget] = {}
        self._inventory_tables: dict[str, QTableWidget] = {}

        self._build_ui()
        self._apply_theme()
        if self.save_path:
            self._load_file(str(self.save_path))

    # ------------------------------------------------------------------ layout

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        file_row = QHBoxLayout()
        root.addLayout(file_row)
        file_row.addWidget(QLabel("Save file:"))
        self.path_edit = QLineEdit(str(self.save_path) if self.save_path else "")
        self.path_edit.setPlaceholderText("Path to SAVE.BIN")
        file_row.addWidget(self.path_edit, 1)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_input)
        file_row.addWidget(browse_button)
        load_button = QPushButton("Load")
        load_button.clicked.connect(lambda: self._load_file(self.path_edit.text()))
        file_row.addWidget(load_button)
        theme_button = QPushButton("Toggle Theme")
        theme_button.clicked.connect(self._toggle_theme)
        file_row.addWidget(theme_button)

        content = QHBoxLayout()
        root.addLayout(content, 1)
        content.addWidget(self._build_actions_panel())

        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)
        for slot_number in (1, 2, 3):
            self._build_slot_tab(str(slot_number))
        content.addWidget(self.tabs, 1)

        output_group = QGroupBox("Save changes")
        root.addWidget(output_group)
        output_row = QHBoxLayout(output_group)
        output_row.addWidget(QLabel("Output:"))
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("Blank creates SAVE.edited.BIN beside the input")
        output_row.addWidget(self.out_edit, 1)
        browse_out_button = QPushButton("Browse...")
        browse_out_button.clicked.connect(self._browse_output)
        output_row.addWidget(browse_out_button)
        write_new_button = QPushButton("Write New File")
        write_new_button.clicked.connect(self._write_new)
        output_row.addWidget(write_new_button)
        write_in_place_button = QPushButton("Write In-Place")
        write_in_place_button.clicked.connect(self._write_in_place)
        output_row.addWidget(write_in_place_button)

        log_group = QGroupBox("Log")
        root.addWidget(log_group)
        log_layout = QVBoxLayout(log_group)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(115)
        log_layout.addWidget(self.log_text)
        self.log_line("Ready. Choose SAVE.BIN and press Load.")

    def _build_actions_panel(self) -> QWidget:
        panel = QGroupBox("Target and actions")
        panel.setMaximumWidth(320)
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        layout = QVBoxLayout(panel)

        layout.addWidget(QLabel("Target slot"))
        self.target_combo = QComboBox()
        for value, label in SLOT_CHOICES:
            self.target_combo.addItem(label, value)
        self.target_combo.currentIndexChanged.connect(self._on_target_changed)
        layout.addWidget(self.target_combo)

        refresh_button = QPushButton("Inspect / Refresh")
        refresh_button.clicked.connect(self.refresh_views)
        layout.addWidget(refresh_button)

        for label, callback in (
            ("Max Current Party", self._max_party),
            ("Max All Roster Rows", self._max_all),
            ("Give All Items", self._give_items),
            ("Give All Gear", self._give_gear),
            ("Give Everything", self._give_everything),
            ("Equip Best (late-game)", self._equip_best),
            ("Fix Checksum Only", self._fix_checksum),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            layout.addWidget(button)

        add_group = QGroupBox("Add item / gear")
        layout.addWidget(add_group)
        add_layout = QVBoxLayout(add_group)
        self.item_combo = QComboBox()
        self.item_combo.setEditable(True)
        self.item_combo.addItems(sorted(tool.ALL_KNOWN.values()))
        self.item_combo.setCurrentText("")
        self.item_combo.lineEdit().setPlaceholderText("Name or 0xID")
        add_layout.addWidget(self.item_combo)
        quantity_row = QHBoxLayout()
        add_layout.addLayout(quantity_row)
        quantity_row.addWidget(QLabel("Quantity"))
        self.quantity_spin = QSpinBox()
        self.quantity_spin.setRange(1, 99)
        self.quantity_spin.setValue(99)
        quantity_row.addWidget(self.quantity_spin)
        add_button = QPushButton("Add Item")
        add_button.clicked.connect(self._add_item)
        quantity_row.addWidget(add_button)

        self.shadow_label = QLabel("Redundant copy: no file loaded")
        self.shadow_label.setWordWrap(True)
        self.shadow_label.setStyleSheet("color: #999999;")
        layout.addWidget(self.shadow_label)
        layout.addStretch(1)
        return panel

    def _build_slot_tab(self, key: str) -> None:
        page = QWidget()
        self.tabs.addTab(page, f"Slot {key}")
        layout = QVBoxLayout(page)

        status = QLabel("No file loaded.")
        status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        status.setWordWrap(True)
        self._status_labels[key] = status
        layout.addWidget(status)

        layout.addWidget(QLabel("Current party"))
        party_table = _make_table(PARTY_HEADINGS)
        self._party_tables[key] = party_table
        layout.addWidget(party_table, 1)

        layout.addWidget(QLabel("Inventory"))
        inventory_table = _make_table(INVENTORY_HEADINGS)
        self._inventory_tables[key] = inventory_table
        layout.addWidget(inventory_table, 1)

    # ---------------------------------------------------------------- theming

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        assert app is not None
        app.setStyle("Fusion")
        app.setPalette(_dark_palette() if self._dark else self._light_palette)

    def _toggle_theme(self) -> None:
        self._dark = not self._dark
        self._apply_theme()

    # --------------------------------------------------------------- utilities

    def log_line(self, text: str) -> None:
        self.log_text.appendPlainText(text)

    def require_data(self) -> bool:
        if self.data is None:
            self.log_line("No save file loaded yet.")
            return False
        return True

    def selected_target(self) -> str:
        return str(self.target_combo.currentData() or "1")

    def _target_bases(self, candidate: bytearray) -> list[int]:
        return tool.select_copy_bases(candidate, self.selected_target())

    def _labels(self, bases: list[int]) -> str:
        return ", ".join(tool.slot_label_for_base(base) for base in bases)

    def _browse_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open FFIV 3D save",
            str(self.save_path.parent if self.save_path else Path.cwd()),
            "FFIV save (SAVE.BIN *.BIN *.bin);;All files (*)",
        )
        if path:
            self.path_edit.setText(path)
            self._load_file(path)

    def _browse_output(self) -> None:
        start = self._default_output_path() if self.save_path else Path.cwd() / "SAVE.edited.BIN"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Write edited save",
            str(start),
            "FFIV save (*.BIN *.bin);;All files (*)",
        )
        if path:
            self.out_edit.setText(path)

    def _default_output_path(self) -> Path:
        assert self.save_path is not None
        return self.save_path.with_name(self.save_path.stem + ".edited" + self.save_path.suffix)

    # --------------------------------------------------------------- loading

    def _load_file(self, path_text: str) -> None:
        path_text = path_text.strip()
        if not path_text:
            self.log_line("Enter a SAVE.BIN path first.")
            return
        path = Path(path_text)
        try:
            candidate = bytearray(path.read_bytes())
            tool.validate_save(candidate)
        except (OSError, ValueError) as exc:
            self.log_line(f"Could not open {path}: {exc}")
            QMessageBox.critical(self, "Could not open save", str(exc))
            return

        self.save_path = path
        self.data = candidate
        self.path_edit.setText(str(path))
        if not self.out_edit.text().strip():
            self.out_edit.setText(str(self._default_output_path()))
        self.log_line(f"Loaded {path} ({len(candidate):,} bytes).")
        self.refresh_views()

    # ----------------------------------------------------------- slot syncing

    def _on_target_changed(self, _index: int) -> None:
        if self._syncing_slot:
            return
        target = self.selected_target()
        if target not in {"1", "2", "3"}:
            return
        self._syncing_slot = True
        try:
            self.tabs.setCurrentIndex(int(target) - 1)
        finally:
            self._syncing_slot = False

    def _on_tab_changed(self, index: int) -> None:
        if self._syncing_slot or not (0 <= index < 3):
            return
        self._syncing_slot = True
        try:
            target_index = self.target_combo.findData(str(index + 1))
            if target_index >= 0:
                self.target_combo.setCurrentIndex(target_index)
        finally:
            self._syncing_slot = False

    # ---------------------------------------------------------------- views

    def refresh_views(self) -> None:
        if self.data is None:
            return
        for slot_number, base in tool.VISIBLE_SLOT_BASES.items():
            key = str(slot_number)
            stored = tool.u32(self.data, base + tool.CHECKSUM_REL)
            calculated = tool.checksum_for_copy(self.data, base)
            occupied = tool.slot_looks_occupied(self.data, base)
            checksum_text = "OK" if stored == calculated else "BAD"
            sentinel = " (inactive sentinel)" if stored == tool.INACTIVE_CHECKSUM_SENTINEL else ""
            self._status_labels[key].setText(
                f"Base 0x{base:04X} · {'occupied' if occupied else 'empty/inactive'} · "
                f"checksum {checksum_text}{sentinel}\n"
                f"Stored 0x{stored:08X} · calculated 0x{calculated:08X}"
            )

            party = tool.detected_party_indices(self.data, base)
            party_table = self._party_tables[key]
            party_table.setRowCount(len(party))
            for row, roster_index in enumerate(party):
                char = tool.char_base(base, roster_index)
                _set_row(
                    party_table,
                    row,
                    (
                        roster_index,
                        self.data[char + tool.LEVEL_REL],
                        f"{tool.u32(self.data, char + tool.CUR_HP_REL)}/"
                        f"{tool.u32(self.data, char + tool.MAX_HP_REL)}",
                        f"{tool.u32(self.data, char + tool.CUR_MP_REL)}/"
                        f"{tool.u32(self.data, char + tool.MAX_MP_REL)}",
                        self.data[char + tool.STR_REL],
                        self.data[char + tool.STA_REL],
                        self.data[char + tool.SPD_REL],
                        self.data[char + tool.INT_REL],
                        self.data[char + tool.SPI_REL],
                    ),
                )

            entries = tool.inventory_entries(self.data, base)
            inventory_table = self._inventory_tables[key]
            inventory_table.setRowCount(len(entries))
            for row, (item_id, quantity) in enumerate(entries):
                _set_row(
                    inventory_table,
                    row,
                    (f"0x{item_id:04X}", tool.ALL_KNOWN.get(item_id, "Unknown"), quantity),
                )

        redundant_occupied = tool.slot_looks_occupied(self.data, tool.REDUNDANT_COPY_BASE)
        partner, difference = tool.redundant_partner_slot(self.data)
        if partner is not None:
            detail = f"paired with slot {partner} ({difference} body-byte differences)"
        elif difference is not None:
            detail = f"no confident pair (closest difference: {difference})"
        else:
            detail = "not occupied"
        self.shadow_label.setText(
            f"Redundant copy at 0x{tool.REDUNDANT_COPY_BASE:04X}: "
            f"{'occupied; ' if redundant_occupied else ''}{detail}. "
            "Visible-slot edits include it when occupied."
        )

    # --------------------------------------------------------------- editing

    def _perform_edit(
        self,
        operation: Callable[[bytearray, list[int]], str],
        *,
        fix_checksums: bool = True,
    ) -> None:
        if not self.require_data():
            return
        assert self.data is not None
        candidate = bytearray(self.data)
        try:
            bases = self._target_bases(candidate)
            message = operation(candidate, bases)
            if fix_checksums:
                tool.fix_checksums(candidate, bases)
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            self.log_line(f"Edit failed: {exc}")
            QMessageBox.critical(self, "Could not apply edit", str(exc))
            return
        self.data = candidate
        suffix = f" Checksums fixed for {self._labels(bases)}." if fix_checksums else ""
        self.log_line(message + suffix)
        self.refresh_views()

    def _max_party(self) -> None:
        def edit(candidate: bytearray, bases: list[int]) -> str:
            result = tool.max_party(candidate, bases)
            summary = "; ".join(
                f"{tool.slot_label_for_base(base)}={rows}" for base, rows in result.items()
            )
            return f"Maxed current-party roster rows: {summary}."

        self._perform_edit(edit)

    def _max_all(self) -> None:
        def edit(candidate: bytearray, bases: list[int]) -> str:
            result = tool.max_all_chars(candidate, bases)
            summary = "; ".join(
                f"{tool.slot_label_for_base(base)}={rows}" for base, rows in result.items()
            )
            return f"Maxed non-empty roster rows: {summary}."

        self._perform_edit(edit)

    def _give(self, additions: list[int], label: str) -> None:
        quantity = self.quantity_spin.value()

        def edit(candidate: bytearray, bases: list[int]) -> str:
            tool.upsert_inventory(candidate, additions, quantity=quantity, bases=bases)
            return f"Added/updated {len(set(additions))} {label} entries to quantity ≥ {quantity}."

        self._perform_edit(edit)

    def _give_items(self) -> None:
        self._give(list(tool.ITEMS), "item")

    def _give_gear(self) -> None:
        self._give(list(tool.ALL_GEAR), "gear")

    def _give_everything(self) -> None:
        self._give(list(tool.ALL_KNOWN), "item/gear")

    def _add_item(self) -> None:
        token = self.item_combo.currentText().strip()
        if not token:
            self.log_line("Enter an item/gear name or hex ID first.")
            return
        try:
            item_id = tool.resolve_item_id(token)
        except ValueError as exc:
            self.log_line(f"Could not resolve item: {exc}")
            QMessageBox.critical(self, "Unknown item or gear", str(exc))
            return
        name = tool.ALL_KNOWN.get(item_id, f"0x{item_id:04X}")
        self._give([item_id], name)

    def _equip_best(self) -> None:
        def edit(candidate: bytearray, bases: list[int]) -> str:
            changed = tool.equip_best_final_party(candidate, bases)
            names = ", ".join(changed) if changed else "no matching late-game party rows"
            return f"Equipped: {names}."

        self._perform_edit(edit)

    def _fix_checksum(self) -> None:
        def edit(candidate: bytearray, bases: list[int]) -> str:
            tool.fix_checksums(candidate, bases)
            return f"Fixed checksums for {self._labels(bases)}."

        self._perform_edit(edit, fix_checksums=False)

    # ---------------------------------------------------------------- output

    def _write_new(self) -> None:
        if not self.require_data() or self.save_path is None:
            return
        out_text = self.out_edit.text().strip()
        out_path = Path(out_text) if out_text else self._default_output_path()
        try:
            tool.write_new_save(self.save_path, out_path, self.data)
        except (OSError, ValueError) as exc:
            self.log_line(f"Could not write {out_path}: {exc}")
            QMessageBox.critical(self, "Write failed", str(exc))
            return
        self.log_line(f"Wrote: {out_path}")

    def _write_in_place(self) -> None:
        if not self.require_data() or self.save_path is None:
            return
        answer = QMessageBox.question(
            self,
            "Overwrite in place?",
            f"Overwrite {self.save_path}?\nA new numbered .bak backup will be written first.",
        )
        if answer != QMessageBox.Yes:
            return
        try:
            backup = tool.write_in_place_with_backup(self.save_path, self.data)
        except (OSError, ValueError) as exc:
            self.log_line(f"In-place write failed: {exc}")
            QMessageBox.critical(self, "Write failed", str(exc))
            return
        self.log_line(f"Wrote in place; backup: {backup}")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    save_path = argv[0] if argv else None
    app = QApplication(sys.argv[:1])
    app.setApplicationName("FFIV 3D Save Editor")
    window = FFIV3DSaveGUI(save_path)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
