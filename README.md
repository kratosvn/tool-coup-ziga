# co-tuong-auto

Bot tự động chơi "Cờ Úp" trên `zigavn.com`. Xem [PLAN.md](PLAN.md) cho bối cảnh/kiến
trúc đầy đủ, [docs/FINDINGS.md](docs/FINDINGS.md) cho kết quả reverse-engineering
client, và [RUNBOOK.md](RUNBOOK.md) để chạy Phase A (feasibility spike).

## Trạng thái

- **Phase A (feasibility spike)**: code đã viết (`zigacoup/session.py`,
  `zigacoup/bridge.py`, `zigacoup/hook.js`, `scripts/phase_a_spike.py`), dựa trên
  phân tích tĩnh client thật (`ziga/zigavn.com/`). **Chưa được xác nhận chạy thật**
  — cần chạy `scripts/phase_a_spike.py` với tài khoản đã login để verify (xem
  RUNBOOK.md mục 2 "Tiêu chí Phase A pass").
- **Phase B (belief.py, engine.py, ai.py, matchmaking.py, actions.py, loop.py)**:
  chưa bắt đầu, đợi Phase A pass.

## Cấu trúc

```
zigacoup/
  session.py   - mo Chromium voi profile da login (persistent context)
  bridge.py    - bom hook.js, nghe network event, goi ham doc/ghi state
  hook.js      - patch vao client Cocos2d-JS de doc/ghi state bang thong tin cong bang
scripts/
  phase_a_spike.py - REPL kiem chung Phase A
docs/
  FINDINGS.md  - chi tiet reverse-engineering (class/field map, do tin cay)
ziga/          - mirror tinh cua trang (dung de doi chieu khi Ziga doi code)
```
