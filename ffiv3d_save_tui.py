#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 FFIV 3D Save Tool contributors
"""
Textual TUI front-end for ffiv3d_save_tool.py.

This file contains no save-format knowledge of its own. All offsets,
checksum math, and editing logic live in ffiv3d_save_tool.py and are
imported here so the CLI and TUI never drift apart.

Run:
    python3 ffiv3d_save_tui.py [SAVE.BIN]

Requires the third-party "textual" package (the CLI tool itself has no
third-party dependencies; only this TUI front-end does):
    pip install textual
"""
from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    RadioButton,
    RadioSet,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

import ffiv3d_save_tool as tool


SLOT_CHOICES = [
    ("1", "slot 1"),
    ("2", "slot 2"),
    ("3", "slot 3"),
    ("all", "all occupied slots"),
]

SLOT_TO_TAB = {"1": "tab_1", "2": "tab_2", "3": "tab_3"}
TAB_TO_SLOT = {tab: slot for slot, tab in SLOT_TO_TAB.items()}


class ConfirmScreen(ModalScreen[bool]):
    """Yes/No confirmation modal for the destructive in-place write."""

    CSS = """
    ConfirmScreen {
        align: center middle;
    }
    #dialog {
        width: 60;
        height: auto;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
    }
    #buttons {
        height: auto;
        align: right middle;
        padding-top: 1;
    }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self.message)
            with Horizontal(id="buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Overwrite", id="confirm", variant="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")


class FFIVSaveApp(App):
    """Interactive TUI for inspecting and editing FFIV 3D Remake SAVE.BIN files."""

    TITLE = "FFIV 3D Remake Save Editor"
    CSS = """
    #sidebar {
        width: 44;
        border: round $primary;
        padding: 1;
    }
    #main {
        border: round $primary;
    }
    #log {
        height: 12;
        border: round $primary;
    }
    .section-title {
        text-style: bold;
        color: $accent;
        margin-top: 1;
    }
    """
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_views", "Refresh"),
    ]

    def __init__(self, save_path: str | None = None) -> None:
        super().__init__()
        self.save_path = Path(save_path) if save_path else None
        self.data: bytearray | None = None
        self._syncing_slot = False

    # ------------------------------------------------------------------ UI

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with VerticalScroll(id="sidebar"):
                yield Label("Save file")
                yield Input(
                    value=str(self.save_path) if self.save_path else "",
                    placeholder="path/to/SAVE.BIN",
                    id="path_input",
                )
                yield Button("Load", id="load_btn", variant="primary")

                yield Static("Target slot", classes="section-title")
                with RadioSet(id="slot_radio"):
                    for i, (value, label) in enumerate(SLOT_CHOICES):
                        yield RadioButton(label, value=(i == 0), id=f"slot_{value}")

                yield Static("Actions", classes="section-title")
                yield Button("Inspect / Refresh", id="inspect_btn")
                yield Button("Max Current Party", id="max_party_btn")
                yield Button("Max All Roster Rows", id="max_all_btn")
                yield Button("Give All Items", id="give_items_btn")
                yield Button("Give All Gear", id="give_gear_btn")
                yield Button("Give Everything", id="give_everything_btn")
                yield Button("Equip Best (late-game)", id="equip_best_btn")
                yield Button("Fix Checksum Only", id="fix_checksum_btn")

                yield Static("Add item / gear", classes="section-title")
                yield Select(
                    [(name, name) for _, name in sorted(tool.ALL_KNOWN.items(), key=lambda kv: kv[1])],
                    prompt="Pick from list…",
                    id="add_item_select",
                )
                yield Input(placeholder="or type name/0xID, e.g. Ragnarok", id="add_item_input")
                yield Button("Add Item", id="add_item_btn")

                yield Static("Quantity for added items", classes="section-title")
                yield Input(value="99", id="quantity_input")

                yield Static("Save changes", classes="section-title")
                yield Input(placeholder="output path (blank = auto name)", id="out_input")
                yield Button("Write New File", id="write_out_btn", variant="success")
                yield Button("Write In-Place (.bak backup)", id="write_inplace_btn", variant="warning")

            with Vertical():
                with TabbedContent(id="main"):
                    with TabPane("Slot 1", id="tab_1"):
                        yield self._make_slot_view("1")
                    with TabPane("Slot 2", id="tab_2"):
                        yield self._make_slot_view("2")
                    with TabPane("Slot 3", id="tab_3"):
                        yield self._make_slot_view("3")
                yield RichLog(id="log", wrap=True, markup=True)
        yield Footer()

    def _make_slot_view(self, key: str) -> Vertical:
        container = Vertical(id=f"view_{key}")
        return container

    def on_mount(self) -> None:
        for key in ("1", "2", "3"):
            view = self.query_one(f"#view_{key}", Vertical)
            view.mount(Static("No file loaded.", id=f"status_{key}"))
            table = DataTable(id=f"party_table_{key}")
            table.add_columns("Roster#", "Lvl", "HP", "MP", "STR", "STA", "SPD", "INT", "SPI")
            view.mount(table)
            view.mount(Static("", id=f"inventory_{key}"))

        log = self.query_one("#log", RichLog)
        log.write("[bold]Ready.[/bold] Enter a SAVE.BIN path and press Load.")

        if self.save_path:
            self._load_file(str(self.save_path))

    # --------------------------------------------------------------- helpers

    def log_line(self, text: str, style: str = "") -> None:
        log = self.query_one("#log", RichLog)
        log.write(f"[{style}]{text}[/{style}]" if style else text)

    def selected_slot_value(self) -> str:
        radio = self.query_one("#slot_radio", RadioSet)
        pressed = radio.pressed_button
        if pressed is None or pressed.id is None:
            return "1"
        return pressed.id.removeprefix("slot_")

    def require_data(self) -> bool:
        if self.data is None:
            self.log_line("No save file loaded yet.", "bold red")
            return False
        return True

    # ----------------------------------------------------- slot/tab syncing

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id != "slot_radio" or self._syncing_slot:
            return
        slot_value = (event.pressed.id or "").removeprefix("slot_")
        tab_id = SLOT_TO_TAB.get(slot_value)
        if tab_id is None:
            return
        self._syncing_slot = True
        try:
            self.query_one("#main", TabbedContent).active = tab_id
        finally:
            self._syncing_slot = False

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.tabbed_content.id != "main" or self._syncing_slot:
            return
        slot_value = TAB_TO_SLOT.get(event.pane.id or "")
        if slot_value is None:
            return
        radio = self.query_one("#slot_radio", RadioSet)
        target = radio.query_one(f"#slot_{slot_value}", RadioButton)
        if target == radio.pressed_button:
            return
        self._syncing_slot = True
        try:
            target.value = True
        finally:
            self._syncing_slot = False

    # --------------------------------------------------------------- loading

    def _load_file(self, path_str: str) -> None:
        path = Path(path_str)
        try:
            raw = bytearray(path.read_bytes())
            tool.validate_save(raw)
        except OSError as exc:
            self.log_line(f"Could not read {path}: {exc}", "bold red")
            return
        except ValueError as exc:
            self.log_line(f"Not a valid SAVE.BIN: {exc}", "bold red")
            return

        self.save_path = path
        self.data = raw
        self.log_line(f"Loaded {path} ({len(raw)} bytes).", "bold green")
        self.refresh_views()

    # --------------------------------------------------------------- views

    def action_refresh_views(self) -> None:
        self.refresh_views()

    def refresh_views(self) -> None:
        if self.data is None:
            return
        data = self.data
        bases = {"1": tool.VISIBLE_SLOT_BASES[1], "2": tool.VISIBLE_SLOT_BASES[2],
                 "3": tool.VISIBLE_SLOT_BASES[3]}

        for key, base in bases.items():
            status = self.query_one(f"#status_{key}", Static)
            table = self.query_one(f"#party_table_{key}", DataTable)
            inv = self.query_one(f"#inventory_{key}", Static)

            stored = tool.u32(data, base + tool.CHECKSUM_REL)
            calc = tool.checksum_for_copy(data, base)
            ok = stored == calc
            occupied = tool.slot_looks_occupied(data, base)
            sentinel = stored == tool.INACTIVE_CHECKSUM_SENTINEL

            lines = [
                f"base=0x{base:04X}  occupied={'yes' if occupied else 'no'}",
                f"checksum stored=0x{stored:08X} calc=0x{calc:08X} "
                f"[{'green' if ok else 'red'}]{'OK' if ok else 'BAD'}[/]"
                + (" (sentinel/empty)" if sentinel else ""),
            ]
            status.update("\n".join(lines))

            table.clear()
            for idx in tool.detected_party_indices(data, base):
                c = tool.char_base(base, idx)
                table.add_row(
                    str(idx),
                    str(data[c + tool.LEVEL_REL]),
                    f"{tool.u32(data, c + tool.CUR_HP_REL)}/{tool.u32(data, c + tool.MAX_HP_REL)}",
                    f"{tool.u32(data, c + tool.CUR_MP_REL)}/{tool.u32(data, c + tool.MAX_MP_REL)}",
                    str(data[c + tool.STR_REL]),
                    str(data[c + tool.STA_REL]),
                    str(data[c + tool.SPD_REL]),
                    str(data[c + tool.INT_REL]),
                    str(data[c + tool.SPI_REL]),
                )

            count = tool.u32(data, base + tool.ITEM_COUNT_REL)
            entries = tool.inventory_entries(data, base)
            names = ", ".join(tool.ALL_KNOWN.get(item_id, f"0x{item_id:04X}") for item_id, _ in entries[:20])
            more = "" if len(entries) <= 20 else f" (+{len(entries) - 20} more)"
            inv.update(f"inventory count: {count}\n{names}{more}")

    # --------------------------------------------------------------- actions

    def _quantity(self) -> int | None:
        raw = self.query_one("#quantity_input", Input).value.strip()
        try:
            return tool.validate_quantity(int(raw, 10))
        except ValueError as exc:
            self.log_line(f"Invalid quantity: {exc}", "bold red")
            return None

    def _perform_edit(
        self,
        operation: Callable[[bytearray, list[int]], str],
        *,
        fix_checksums: bool = True,
    ) -> None:
        """Apply an action to a copy and commit it only after full success."""
        if self.data is None:
            return
        candidate = bytearray(self.data)
        try:
            bases = tool.select_copy_bases(candidate, self.selected_slot_value())
            message = operation(candidate, bases)
            if fix_checksums:
                tool.fix_checksums(candidate, bases)
        except (IndexError, KeyError, OverflowError, TypeError, ValueError) as exc:
            self.log_line(f"Edit failed: {exc}", "bold red")
            return
        self.data = candidate
        suffix = f" (checksums fixed for {self._labels(bases)})" if fix_checksums else ""
        self.log_line(message + suffix, "green")
        self.refresh_views()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "add_item_select" or event.value == Select.BLANK:
            return
        self.query_one("#add_item_input", Input).value = str(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "load_btn":
            self._load_file(self.query_one("#path_input", Input).value.strip())
            return

        if button_id == "inspect_btn":
            if self.require_data():
                self.refresh_views()
                self.log_line("Refreshed.", "green")
            return

        if not self.require_data():
            return

        if button_id == "max_party_btn":
            def max_party(candidate: bytearray, bases: list[int]) -> str:
                by_base = tool.max_party(candidate, bases)
                return f"maxed current-party rows: {self._summarize(by_base)}"

            self._perform_edit(max_party)

        elif button_id == "max_all_btn":
            def max_all(candidate: bytearray, bases: list[int]) -> str:
                by_base = tool.max_all_chars(candidate, bases)
                return f"maxed non-empty roster rows: {self._summarize(by_base)}"

            self._perform_edit(max_all)

        elif button_id in ("give_items_btn", "give_gear_btn", "give_everything_btn"):
            additions: list[int] = []
            if button_id in ("give_items_btn", "give_everything_btn"):
                additions.extend(tool.ITEMS.keys())
            if button_id in ("give_gear_btn", "give_everything_btn"):
                additions.extend(tool.ALL_GEAR.keys())
            qty = self._quantity()
            if qty is None:
                return

            def give(candidate: bytearray, bases: list[int]) -> str:
                tool.upsert_inventory(candidate, additions, quantity=qty, bases=bases)
                return f"added/updated {len(set(additions))} inventory entries to quantity >= {qty}"

            self._perform_edit(give)

        elif button_id == "add_item_btn":
            token = self.query_one("#add_item_input", Input).value.strip()
            if not token:
                self.log_line("Enter an item/gear name or hex ID first.", "yellow")
                return
            try:
                item_id = tool.resolve_item_id(token)
            except ValueError as exc:
                self.log_line(f"error: {exc}", "bold red")
                return
            qty = self._quantity()
            if qty is None:
                return
            name = tool.ALL_KNOWN.get(item_id, f"0x{item_id:04X}")

            def add_item(candidate: bytearray, bases: list[int]) -> str:
                tool.upsert_inventory(candidate, [item_id], quantity=qty, bases=bases)
                return f"added {name} (0x{item_id:04X}) qty>={qty}"

            self._perform_edit(add_item)

        elif button_id == "equip_best_btn":
            def equip_best(candidate: bytearray, bases: list[int]) -> str:
                changed = tool.equip_best_final_party(candidate, bases)
                names = ", ".join(changed) if changed else "no matching late-game party rows detected"
                return f"equipped: {names}"

            self._perform_edit(equip_best)

        elif button_id == "fix_checksum_btn":
            def fix_checksum(candidate: bytearray, bases: list[int]) -> str:
                tool.fix_checksums(candidate, bases)
                return f"fixed checksums for: {self._labels(bases)}"

            self._perform_edit(fix_checksum, fix_checksums=False)

        elif button_id == "write_out_btn":
            self._write_out()

        elif button_id == "write_inplace_btn":
            self.push_screen(
                ConfirmScreen(
                    f"Overwrite {self.save_path} in place?\n"
                    "A new numbered .bak backup will be written first."
                ),
                self._on_inplace_confirmed,
            )

    def _labels(self, bases: list[int]) -> str:
        return ", ".join(tool.slot_label_for_base(b) for b in bases)

    def _summarize(self, by_base: dict[int, list[int]]) -> str:
        return "; ".join(f"{tool.slot_label_for_base(base)}={rows}" for base, rows in by_base.items())

    def _write_out(self) -> None:
        if not self.require_data() or self.save_path is None:
            return
        out_value = self.query_one("#out_input", Input).value.strip()
        if out_value:
            out_path = Path(out_value)
        elif self.save_path is not None:
            out_path = self.save_path.with_name(self.save_path.stem + ".edited" + self.save_path.suffix)
        else:
            self.log_line("No output path and no loaded file path to derive one from.", "bold red")
            return
        try:
            tool.write_new_save(self.save_path, out_path, self.data)
        except (OSError, ValueError) as exc:
            self.log_line(f"Could not write {out_path}: {exc}", "bold red")
            return
        self.log_line(f"wrote: {out_path}", "bold green")

    def _on_inplace_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed or self.data is None or self.save_path is None:
            return
        try:
            backup = tool.write_in_place_with_backup(self.save_path, self.data)
        except (OSError, ValueError) as exc:
            self.log_line(f"In-place write failed: {exc}", "bold red")
            return
        self.log_line(f"wrote in-place; backup: {backup}", "bold green")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    save_path = argv[0] if argv else None
    FFIVSaveApp(save_path).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
