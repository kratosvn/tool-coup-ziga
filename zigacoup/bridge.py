"""Phase A - bridge.py

Bom hook.js vao trang da load, nghe console log de nhan event NETWORK_* da decode,
va goi lai cac ham doc/ghi expose qua window.__zigaBot (xem hook.js + docs/FINDINGS.md).
"""

from __future__ import annotations

import json
import pathlib
import time
from typing import Any, Callable

HOOK_JS_PATH = pathlib.Path(__file__).parent / "hook.js"
_EVENT_PREFIX = "__ZIGABOT__"


class Bridge:
    def __init__(self, page):
        self.page = page
        self._events: list[dict] = []
        self._callbacks: list[Callable[[dict], None]] = []
        page.on("console", self._on_console)

    def _on_console(self, msg) -> None:
        text = msg.text
        if not text.startswith(_EVENT_PREFIX):
            return
        try:
            rec = json.loads(text[len(_EVENT_PREFIX):])
        except json.JSONDecodeError:
            return
        self._events.append(rec)
        for cb in self._callbacks:
            cb(rec)

    def on_event(self, cb: Callable[[dict], None]) -> None:
        self._callbacks.append(cb)

    @property
    def events(self) -> list[dict]:
        return list(self._events)

    def inject(self) -> None:
        js = HOOK_JS_PATH.read_text(encoding="utf-8")
        self.page.evaluate(js)

    def wait_ready(self, timeout: float = 60.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            kinds = {e["kind"] for e in self._events}
            if "bot_ready" in kinds:
                return True
            if "bot_ready_timeout" in kinds:
                return False
            time.sleep(0.2)
        return False

    # ---------------- read ----------------

    def is_logged_in(self) -> bool:
        return bool(self.page.evaluate("() => window.__zigaBot.isLoggedIn()"))

    def is_in_coup_game(self) -> bool:
        return bool(self.page.evaluate("() => window.__zigaBot.isInCoUpGame()"))

    def get_board(self) -> dict | None:
        return self.page.evaluate("() => window.__zigaBot.getBoard()")

    def dump_piece(self, idx: int) -> dict | None:
        return self.page.evaluate("(idx) => window.__zigaBot.dumpPiece(idx)", idx)

    def get_chess_type_enum(self) -> dict | None:
        return self.page.evaluate("() => window.__zigaBot.getChessTypeEnum()")

    def select_piece(self, idx: int) -> bool:
        return bool(self.page.evaluate("(idx) => window.__zigaBot.selectPiece(idx)", idx))

    def deselect(self) -> bool:
        return bool(self.page.evaluate("() => window.__zigaBot.deselect()"))

    def get_highlighted_moves(self) -> list[dict] | None:
        return self.page.evaluate("() => window.__zigaBot.getHighlightedMoves()")

    # ---------------- write ----------------

    def send_move(self, from_col: int, from_row: int, to_col: int, to_row: int) -> bool:
        return bool(
            self.page.evaluate(
                "([a,b,c,d]) => window.__zigaBot.sendMove(a,b,c,d)",
                [from_col, from_row, to_col, to_row],
            )
        )

    def send_ready(self, ready: bool) -> bool:
        return bool(self.page.evaluate("(r) => window.__zigaBot.sendReady(r)", bool(ready)))

    def send_chess_action(self, action: Any) -> bool:
        return bool(self.page.evaluate("(a) => window.__zigaBot.sendChessAction(a)", action))
