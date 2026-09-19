#!/usr/bin/env python3
"""Phase A feasibility spike.

Muc tieu duy nhat: chung minh doc-duoc-state (bridge.get_board/get_highlighted_moves)
va gui-duoc-move (bridge.send_move) hoan toan bang code, khong dung chuot/ban phim
that trong luc choi (chi dung chuot 1 lan de tu vao ban, vi matchmaking tu dong la
viec cua Phase B / matchmaking.py).

Chay: python scripts/phase_a_spike.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from zigacoup.bridge import Bridge
from zigacoup.session import Session


def print_event(rec: dict) -> None:
    print(f"[event] {rec['kind']}: {rec['payload']}")


def print_board(board: dict) -> None:
    if not board:
        print("  (khong doc duoc board - co the chua vao ban Co Up)")
        return
    print(
        f"  flipped={board['flipped']} selected={board['selected']} "
        f"turnPlayerIndex={board['turnPlayerIndex']} myPlayerIndex={board['myPlayerIndex']} "
        f"gameState={board['gameState']}"
    )
    for p in board["pieces"]:
        if p["removed"]:
            continue
        print(
            f"    idx={p['idx']:2d} col={p['col']} row={p['row']} "
            f"owner={p['owner']} type={p['type']}"
        )


def main() -> None:
    with Session() as session:
        print(f"Da mo trinh duyet voi profile: {session.user_data_dir}")
        print("Dang cho login (cc.username)...")
        if not session.wait_for_login(timeout=300):
            print("Khong phat hien login trong 300s. Neu day la lan dau, hay dang nhap tay")
            print("(bao gom Turnstile neu hien ra) roi chay lai script.")
            return
        print("Da login.")

        bridge = Bridge(session.page)
        bridge.on_event(print_event)

        print()
        print("=" * 70)
        print("Hay tu vao 1 ban CO UP bang chuot (menu > CO UP > chon/tim ban),")
        print("doi ban bat dau (2 Tuong da hien, den luot minh hoac doi thu).")
        print("=" * 70)
        input("Nhan Enter khi ban da vao ban va van da bat dau...")

        print("Dang inject hook.js va cho cac class BkXxx san sang...")
        bridge.inject()
        if not bridge.wait_ready(timeout=60):
            print("Hook khong san sang sau 60s - co the Ziga da doi ten class.")
            print("Xem docs/FINDINGS.md de cap nhat lai ten field/ham trong hook.js.")
            return
        print("Hook san sang. Cac class da patch:", [e for e in bridge.events if e["kind"] == "bot_ready"])

        if not bridge.is_in_coup_game():
            print("Canh bao: bridge.is_in_coup_game() == False.")
            print("Co the ban dang o game khac hoac chua vao ban that su. Van tiep tuc,")
            print("nhung get_board() co the tra ve None.")

        print()
        print("Chess type enum (doi chieu voi FINDINGS.md):", bridge.get_chess_type_enum())

        print()
        print("Cac lenh: board | dump <idx> | select <idx> | moves | move <col> <row> | quit")
        while True:
            try:
                raw = input("> ").strip()
            except EOFError:
                break
            if not raw:
                continue
            parts = raw.split()
            cmd = parts[0].lower()

            if cmd == "quit":
                break
            elif cmd == "board":
                print_board(bridge.get_board())
            elif cmd == "dump" and len(parts) == 2:
                print(bridge.dump_piece(int(parts[1])))
            elif cmd == "select" and len(parts) == 2:
                ok = bridge.select_piece(int(parts[1]))
                print(f"selectPiece -> {ok}. Doi ~0.5-1s roi go 'moves' de xem goi y.")
            elif cmd == "moves":
                print(bridge.get_highlighted_moves())
            elif cmd == "move" and len(parts) == 3:
                board = bridge.get_board()
                if board is None or board["selected"] is None or board["selected"] < 0:
                    print("Chua co quan nao dang duoc chon (dung lenh 'select <idx>' truoc).")
                    continue
                sel_piece = next(p for p in board["pieces"] if p["idx"] == board["selected"])
                to_col, to_row = int(parts[1]), int(parts[2])
                ok = bridge.send_move(sel_piece["col"], sel_piece["row"], to_col, to_row)
                print(f"sendMove({sel_piece['col']},{sel_piece['row']} -> {to_col},{to_row}) = {ok}")
            else:
                print("Lenh khong hop le. Dung: board | dump <idx> | select <idx> | moves | move <col> <row> | quit")

        print("Dong session.")


if __name__ == "__main__":
    main()
