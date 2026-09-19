# Findings: reverse-engineering `gamelogic.min.js` (Phase A)

Nguồn: `ziga/zigavn.com/zigavn.com/gamelogic.min.js`, snapshot lấy ngày 2026-09-19 (mtime file trùng ngày, coi như bản đang live). Được beautify (chỉ format lại thụt lề, KHÔNG đổi tên biến) sang `.scratch/gamelogic.beautified.js` để đọc — file đó không commit vào git, tái tạo bằng:

```
npm install --no-save js-beautify
./node_modules/.bin/js-beautify -f ziga/zigavn.com/zigavn.com/gamelogic.min.js -o .scratch/gamelogic.beautified.js
```

**Độ tin cậy**: đây là phân tích tĩnh (đọc code, không chạy thật với tài khoản đã login). Tên biến đã bị minify (1-2 ký tự, ví dụ `fa`, `ka`, `Ga`) — suy luận ngữ nghĩa dựa trên cách dùng, log message tiếng Anh còn sót lại (`logMessage("...")` không bị minify vì là string), và đối chiếu case-value với các hằng số `NETWORK_*` đã thấy trong log. Cần xác nhận lại bằng chạy thật (Phase A bước 3) — nếu Ziga đổi code, các tên field dưới đây sẽ cần cập nhật lại trong `hook.js`.

Không có `"use strict"`, không bọc IIFE ở top-level → mọi `ClassName = X.extend({...})` là **global thật** (`window.ClassName`), truy cập trực tiếp được từ `page.evaluate`.

## Sơ đồ class

```
cc.Class
 └─ BkBaseLogic            .$g (network dispatch mặc định, no-op)
     ├─ BkCommonLogic      .$g override — xử lý event tầng lobby/account:
     │                        login, NETWORK_TABLE_JOIN_SUCCESS, NETWORK_ROOM_JOIN_SUCCESS,
     │                        NETWORK_ROOM_TABLES_UPDATE, NETWORK_GAME_JOIN_SUCCESS,
     │                        NETWORK_AUTO_FIND_TABLE_NOT_FOUND_RETURN, NETWORK_GET_GAME_ROOMS_BY_ROOM_TYPE_RETURN...
     │                        singleton: BkLogicManager.T()   (luôn tồn tại, 1 instance suốt phiên)
     └─ BkInGameLogic       .$g override — event chung trong ván (turn/ready...)
         └─ BkChessInGameLogic   .$g override — nước đi cờ tướng/cờ úp (select/move/capture/checkmate)
             └─ BkCoUpInGameLogic .$g override — thêm case "lật quân" (Ie) + 1 case phụ (af)
                                     singleton: BkLogicManager.na()  (tạo lại mỗi khi vào ván,
                                     loại instance phụ thuộc BkGlobal.ia — case `L` → BkCoUpInGameLogic)
```

`BkLogicManager.Gu()` (dòng ~11341 bản beautify) là bằng chứng trực tiếp: `switch(BkGlobal.ia){ case L: a = new BkCoUpInGameLogic; ... }` — `L` là hằng số game-id của Cờ Úp trong danh sách game Ziga hỗ trợ.

## Hook điểm ĐỌC (nhận packet đã decode)

Patch `$g` (prototype) của cả 5 lớp trên (kể cả các lớp cha, để không bỏ sót khi `na()` đang là instance khác) — kỹ thuật: wrap giữ nguyên hành vi gốc rồi log `a.Type` (số nguyên, đại diện cho hằng NETWORK_* — do bị minify nên tại runtime ta chỉ có con số, không có tên; nhưng patch tại đúng class + log message gốc còn sót lại string tiếng Anh nên vẫn correlate được với UI).

Case value đã đối chiếu chắc chắn với comment log gốc (namespace enum `ge` trong code, ví dụ `he=0, ie=3, ..., oe=9, pe=10, ..., we=22`):
- `oe` (giá trị 9) = NETWORK_TABLE_JOIN_SUCCESS
- `pe` (giá trị 10) = phản hồi tiếp theo sau khi vào bàn (gọi `this.oQ(a)`)
- `we` (giá trị 22) = NETWORK_ROOM_TABLES_UPDATE

Trong `BkChessInGameLogic.$g`, các case xử lý nước đi (tên hàm xử lý nội bộ, đọc payload bằng `a.O.readByte()/readInt()`):
| case (tên biến minify) | hàm gọi | tham số đọc | đoán ngữ nghĩa |
|---|---|---|---|
| `vi` | `this.lr(a)` → `layer.lr(b,a)` | 2 byte | chọn quân / cập nhật lượt |
| `Ae` | `this.zo(a)` → `layer.zo(b,a)` | 2 byte | cập nhật ô/nước đi thường |
| `Ee` | `this.kr(a)` → `layer.kr(b,c,d,e,int)` | 4 byte + 1 int | **di chuyển có tọa độ đầy đủ** (fromCol,fromRow,toCol,toRow,+giá trị phụ — có thể là mã quân bị ăn hoặc điểm) |
| `Ge` | `this.Hv(a)` → `layer.Hv(b,a)` | 2 byte | ? |
| `Qe` | `this.Gv(a)` → `layer.Gv(a)` | 1 byte | ? |
| `Pf` | `this.Jv(a)` → `layer.Jv(a)` | 1 byte | ? |
| `Th` | `layer.ZN()` | không | có thể là "hết nước đi / chiếu bí" |

Riêng `BkCoUpInGameLogic.$g` thêm:
| case | hàm | tham số | ngữ nghĩa |
|---|---|---|---|
| `Ie` | `this.Lv(a)` → `layer.Lv(b,a)` | 2 byte (vị trí, loại quân) | **server báo "quân tại vị trí X vừa lật ra là loại quân Y"** — đây là tín hiệu quan trọng nhất cho belief tracking |
| `af` | `this.DN(a)` → đọc 1 byte | 1 byte | chưa rõ, có thể "không có nước đi hợp lệ / pass" |

## Bàn cờ & trạng thái (đọc)

`window.BkGlobal.Yj` = scene ván đang chơi hiện tại. `.ja()` trên scene trả về **game layer** (`BkCoUpGameLayer`, kế thừa `BkChessBaseIngameLayer`) — đây là nơi giữ toàn bộ state hiển thị:

- `layer.V` — mảng 32 phần tử `BkChessPieceSprite`, mỗi phần tử có field:
  - `.fa` — cột (0-8), hệ toạ độ **local theo hướng hiển thị của người chơi hiện tại** (bị lật nếu `layer.hc` true)
  - `.rowIndex` — hàng (0-9), cùng hệ toạ độ trên
  - `.ka` — id chủ sở hữu quân (khớp với `layer.Nj`/turn index khi so sánh "quân của mình")
  - `.Ga` — loại quân (so sánh với `BkChessType.Hm.id` / `BkChessType.Gm.id` trong code — 2 loại được so sánh đặc biệt do bề rộng ô khác, khả năng là Xe/Pháo)
  - `.pa` — cờ "đã bị ăn / loại khỏi bàn"
- `layer.hc` — cờ lật bàn theo góc nhìn (true nếu bàn hiển thị đảo ngược cho người chơi này)
- `layer.le` — index quân đang được chọn (-1 = chưa chọn)
- `layer.Nj` — index người chơi đang tới lượt
- `layer.Yc` — index của "mình" (so `Nj == Yc` để biết có phải lượt mình không)
- `layer.tc[]` — tối đa 20 sprite gợi ý ô-đi-được (mỗi phần tử có `.cq`=cột, `.Ir`=hàng, hợp lệ khi `.x > 0`)
- `layer.Vp[]` — mảng phụ các cặp `[col,row]` hợp lệ khác (nước đặc biệt, ví dụ ăn Tướng đối mặt?)
- `layer.QR(idx)` — chọn quân `idx`, populate lại `tc[]`/`Vp[]` theo đúng luật của quân đó (kể cả quân úp của chính mình — **đây chính là "thông tin công bằng" plan yêu cầu**: gọi hàm này rồi đọc `tc/Vp` cho ta chính xác các ô hợp lệ mà một người chơi thật nhìn thấy khi bôi sáng, khỏi phải tự cài luật Sĩ/Tượng qua sông, Pháo cách quân...)
- `layer.fp()` — bỏ chọn / xoá highlight
- `layer.T()` — trả về logic instance đang active (tương đương `BkLogicManager.na()`), dùng để gọi hàm gửi packet

## Hook điểm GHI (gửi nước đi) — quan trọng nhất

Hàm xử lý click chuột trên bàn cờ, `BkChessBaseIngameLayer.fU(pixelX, pixelY)`, sau khi quy đổi ra (col,row) và biết đã có quân đang chọn, chốt lại chỉ bằng:

```js
// e,g = cột/hàng quân đang chọn (toạ độ local hiện tại)
// f,h = cột/hàng ô đích (toạ độ local hiện tại)
if (layer.hc) { g = 9-g; h = 9-h; e = 8-e; f = 8-f; }  // đổi sang toạ độ chuẩn mạng khi đang nhìn bàn bị lật
layer.T().PP(e, g, f, h);
```

Tức là **không cần giả lập pixel/chuột gì cả** — gọi thẳng `layer.T().PP(fromCol, fromRow, toCol, toRow)` (đã áp dụng lật toạ độ nếu cần) là gửi đúng byte y hệt người chơi thật bấm chuột. `HM(col,row)` là hàm client tự kiểm tra hợp lệ trước khi gọi PP (dùng để không gửi rác lên server) — bot có thể bỏ qua bước này nếu tự tin nước đi hợp lệ (đã lấy từ `tc/Vp` sau khi `QR(idx)`).

Các hàm gửi khác trên cùng logic instance (`layer.T()` / `BkLogicManager.na()`):
- `.yr(action)` — action ∈ {`CHESS_DRAW_REQUEST`, `CHESS_DRAW_ACCEPT`, `CHESS_DRAW_REFUSE`, `CHESS_SURRENDER`} — xin hoà / nhận hoà / từ chối hoà / xin thua
- `.TC(bool)` — bật/tắt sẵn sàng (nút "Chơi ngay"/"Huỷ sẵn sàng" trong bàn chờ)
- `.eP()` — không tham số, gọi từ nút cạnh 2 nút trên (đoán: rời bàn / chơi lại)

## Kiểm tra đã login

`window.cc.username` khác rỗng sau khi login thành công (gán ở nhiều chỗ trong luồng xử lý `NETWORK_LOG_IN`).

## Việc CẦN xác nhận bằng chạy thật (chưa thể tự làm vì cần tài khoản đã login)

1. Field name suy luận ở trên (`fa/rowIndex/ka/Ga/pa`, `tc/Vp`, `le/Nj/Yc/hc`) — dùng `bot.dumpPiece(idx)` (xem `zigacoup/hook.js`) để in hết field thô của 1 quân, so khớp bằng mắt với UI.
2. Ý nghĩa chính xác của case `Ge/Hv`, `Qe/Gv`, `Pf/Jv`, `Th/ZN`, và case `af/DN` riêng của Cờ Úp.
3. `layer.QR(idx)` có gửi round-trip mạng hay tính hoàn toàn phía client — ảnh hưởng độ trễ cần chờ trước khi đọc `tc/Vp`.
4. Giá trị field phụ thứ 5 trong case `Ee/kr(b,c,d,e,int)` (nghi là mã quân bị ăn).
