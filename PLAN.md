# Plan: Bot auto-chơi Cờ Úp trên zigavn.com

## Bối cảnh

Mục tiêu: xây bot tự động chơi "Cờ Úp" (biến thể Cờ Tướng, quân úp mặt xáo trộn ngẫu nhiên) trên `https://zigavn.com/` bằng một tài khoản đã đăng nhập sẵn. 4 bước chính người dùng đặt ra:

1. Vào trang web đã login sẵn
2. Tìm ván chơi
3. Chơi game — **phần quan trọng nhất: xác định AI có chơi được không**
4. Chơi tiếp (lặp lại cho các ván sau)

Vì đây là game ẩn thông tin (quân úp), phần khó nhất không phải là điều khiển trình duyệt mà là (a) đọc được trạng thái bàn cờ từ một client render bằng canvas, và (b) ra quyết định hợp lý khi không biết chắc quân đối thủ là gì. Plan này ưu tiên xác minh tính khả thi của (a) và (b) trước khi đầu tư công sức build AI mạnh.

## Phát hiện kỹ thuật (đã khảo sát trực tiếp trang)

- **Engine:** Cocos2d-JS, toàn bộ UI vẽ trên `<canvas>` → không có DOM cho bàn cờ/quân cờ, selector CSS/XPath thường không dùng được.
- **Network:** WebSocket binary protocol (`wss://zigavn.com/ws/`, cổng dự phòng `ws://zigavn.com:18090`), dùng `DataView`/`Uint8Array` để đóng/mở gói — không phải JSON thuần.
- **Anti-bot:** Cloudflare Turnstile gắn trên trang (chặn login form). Vì bot tái dùng session/profile đã login sẵn, sẽ không đụng tới Turnstile.
- **Event names nội bộ đã thấy trong code:** `NETWORK_TABLE_JOIN_SUCCESS`, `NETWORK_GAME_JOIN_SUCCESS`, `NETWORK_ROOM_JOIN_SUCCESS`, `NETWORK_ROOM_TABLES_UPDATE`, `NETWORK_AUTO_FIND_TABLE_NOT_FOUND_RETURN`, `BTN_CO_UP`, `HOT_TABLE`... — client tự decode binary rồi dispatch các event này, ta chỉ cần nghe event thay vì tự parse byte.

### Luật Cờ Úp (lấy từ trang hướng dẫn chính chủ của Ziga)

- 32 quân, úp mặt xáo trộn ngẫu nhiên, trừ 2 Tướng lộ sẵn.
- Quân úp: khi di chuyển lần đầu, đi theo đúng luật của quân thật nằm ở đó; xong nước đi mới lật lộ mặt.
- Sĩ, Tượng được qua sông ("Sĩ chiến", "Tượng chiến") — khác cờ tướng chuẩn.
- Pháo ăn quân phải cách 1 quân đệm (như cờ tướng thường).
- Thắng: chiếu bí / đối thủ hết nước đi / đối thủ xin thua. Hòa sau 120 nước cả hai bên không ăn quân.

## Protocol map đã reverse-engineer (static analysis từ source `ziga/zigavn.com/zigavn.com/gamelogic.min.js`)

Source client (`gamelogic.min.js`, 642KB) **không obfuscate tên class/hàm quan trọng** — chỉ mangling biến local — nên đọc trực tiếp được rất nhiều thay vì phải dò mù qua live capture.

**Class map:** `BkCoUpGameLayer` / `BkCoUpInGameLogic` / `BkCoUpPiece` kế thừa `BkChessGameLayer` / `BkChessInGameLogic` / `BkChessPiece` (dùng chung engine với Cờ Tướng thường). `BkChessType` xác nhận 7 loại quân id 0-6 (Tướng/Sĩ/Tượng/Xe/Pháo/Mã/Tốt), bàn 9x10 (`BkChessSize.Dm=9, vp=10`), 32 quân index 0-31 (mốc `Cg=16` chia 2 bên).

**Header packet:** 7 byte = 2 byte length (`readShort`) + 1 byte type (`readByte`) + 4 byte int (`readInt`, có thể là sequence/session id) — parse trong `BkPacket.IO()`/`gK()`.

**Opcode đã xác nhận (giá trị field `Type`):**

| Hành động | Opcode | Payload | Nguồn trong code |
|---|---|---|---|
| Di chuyển quân (gửi lên server) | `De` = 28 | 4 byte: `[fromCol, fromRow, toCol, toRow]` | `BkChessBaseIngameLayer.fU()` (touch handler thật) → `T().PP(e,g,f,h)` → `BkPacket.qF()` |
| Lật quân — broadcast reveal (nhận từ server) | `Ie` = 30 | 2 byte: `[position, revealedPieceType]` | `BkCoUpInGameLogic.Lv()` |
| Move broadcast đầy đủ (nhận từ server) | case `vi` trong `BkChessInGameLogic.$g()` | 4 byte (`kr()`: readByte×4 + readInt) | có thể là fromPos,toPos,pieceType,captureFlag + thời gian còn lại — chưa xác nhận thứ tự chính xác |
| Login (AutoRegLogin) | `Lf` = 80 | client ID tự sinh + optional access token Facebook + captcha string | `BkGlobal.XR()` → `BkPacket.rF()` |
| Draw/Surrender | `CHESS_DRAW_REQUEST=0`, `CHESS_DRAW_ACCEPT=1`, `CHESS_DRAW_REFUSE=2`, `CHESS_SURRENDER=3` | — | hằng số toàn cục |
| Game end reason (từ server) | danh sách `wl[]`: 1=chiếu hết, 2=đối phương đầu hàng, 3=hết giờ, 4=cả 2 bên chỉ còn quân phòng thủ, 5=**60** nước liên tiếp không ăn quân (khác với 120 nước ghi trong trang hướng dẫn — tin theo code), 6=chiếu liên tiếp 8 lần, 7/8=đồng ý hòa | | mảng `wl` gần đầu file |

**Ranh giới "fair info" quan trọng nhất tìm được:** touch handler `fU()` cho thấy khi người chơi chọn 1 quân, client tự tính sẵn danh sách ô hợp lệ (lưu ở field dạng `this.tc`, tính trong hàm `QR(e)`) **ngay tại client, trước khi hỏi server** — nghĩa là client giữ toàn bộ danh tính quân thật (cả của mình và đối thủ) trong bộ nhớ để tính hợp lệ/chặn đường (Pháo cần biết occupancy, không cần biết identity quân chặn). Khi code `bridge.py` ở Phase B, **chỉ được đọc field loại quân (`Ga`) hoặc danh sách ô sáng (`this.tc`) trong ngữ cảnh mình vừa chọn quân CỦA MÌNH** — tuyệt đối không đọc trộm field `Ga` của quân úp bên đối thủ, để giữ đúng nguyên tắc AI công bằng đã chốt.

**Board rotation:** field `this.hc` (true khi mình là bên "đen"/xoay bàn) đảo toạ độ theo công thức `row' = 9-row, col' = 8-col` — cần xử lý khi map toạ độ hiển thị sang toạ độ logic.

**Data structure quân cờ (`this.V`):** cả 32 quân 2 bên nằm trong **1 mảng duy nhất** `this.V` trên game layer, không tách riêng mảng theo bên. Phân biệt quân đối thủ bằng field `ka` (side): `ka = Math.floor(index/16)` → index 0-15 = side 0, index 16-31 = side 1. So sánh với `myPlayer.ra` (side của mình, đọc từ `this.T().Ba().ra`) để biết quân nào là của đối thủ: `this.V.filter(p => p.ka !== myPlayer.ra)`.

**Move broadcast (`kr`) — đã giải mã đầy đủ 5 tham số** (khác với ghi chú "chưa xác nhận" trước đó): `kr(a,b,c,d,e)` nhận 4 byte đầu là toạ độ (khớp format gửi đi: fromCol,fromRow,toCol,toRow) và tham số cuối `e` (int) là **index quân bị ăn** (0-31), hoặc âm/ngoài range nếu không ăn quân (code check `0<=e && 32>e` mới đánh dấu `this.V[e].pa=true` và phát âm thanh ăn quân). Sau đó `this.Yc` (side đang đi) đảo `1-this.Yc`.

**Chưa xác nhận (cần live capture ở Phase A để chốt):** (1) cơ chế chính xác của auth handshake (client ID lưu ở đâu — cookie/localStorage — và server validate thế nào); (2) liệu `this.tc` có đúng là danh sách ô hợp lệ hay không; (3) **quan trọng nhất:** field `Ga` (loại quân thật) của quân úp thuộc đối thủ có được client điền sẵn giá trị thật ngay từ đầu ván không, hay chỉ điền sau khi lật — quyết định việc `bridge.py` cần tự chặn đọc field nào để giữ đúng nguyên tắc fair-info (xem thêm phần "Nguyên tắc thiết kế AI"). Field `Vu` trên `BkCoUpPiece` có vẻ liên quan nhưng logic override `IA` của nó chưa rõ nghĩa qua static analysis — cần verify bằng console.log `this.V` lúc bắt đầu ván.

## Nguyên tắc thiết kế AI (đã chốt với người dùng)

AI **chỉ dùng thông tin công bằng** — đúng những gì một người chơi thật nhìn thấy trên UI (bao gồm: ô nào hợp lệ khi mình chọn quân úp của chính mình, vì client cần biết trước để tô sáng). AI **không đọc trộm** danh tính quân úp của đối thủ từ state thật trong client (dù về mặt kỹ thuật có thể làm được) — vì đó là cheat thật sự (biết thông tin đối thủ không thấy được). Với quân úp của đối thủ, AI suy luận bằng xác suất (belief tracking) dựa trên số quân từng loại còn lại và lịch sử đã lật, giống cách người chơi thật suy đoán.

## Kiến trúc tổng thể

```
Playwright (Chromium, persistent profile đã login)
        │
        ├── page.addInitScript()  →  hook vào event bus / hàm nội bộ của Cocos client
        │        ├── READ:  nghe các NETWORK_* event đã decode sẵn → dựng "GameState" (bàn cờ, ai đến lượt, ô nào chọn được, ô hợp lệ khi chọn quân mình)
        │        └── WRITE: gọi trực tiếp hàm xử lý click/move nội bộ của client (không giả lập toạ độ pixel)
        │
        ├── bridge.py  ←→  page.exposeFunction / console-pipe  →  đẩy state qua Python theo thời gian thực
        │
        ├── belief.py  →  suy luận xác suất danh tính quân úp của đối thủ (chỉ dùng info công bằng)
        ├── engine.py  →  sinh nước đi hợp lệ (luật cờ úp: Sĩ/Tượng qua sông, Pháo cách 1 quân, v.v.)
        ├── ai.py      →  Monte Carlo determinization + Expectimax/alpha-beta trên bàn đã "giả định" cụ thể
        └── loop.py    →  vào web → tìm bàn → chờ lượt → AI quyết định → thực thi → lặp
```

### Vì sao kiến trúc này

- Board vẽ trên canvas → buộc phải hook JS hoặc dùng computer vision. Hook JS chính xác và ổn định hơn nhiều → chọn hook JS.
- Protocol WS binary, tự parse từ đầu tốn công và dễ vỡ khi server update → ăn theo bộ decode có sẵn của client (nó tự parse rồi dispatch event, mình chỉ nghe event).
- Gửi hành động bằng cách gọi hàm JS nội bộ (thay vì giả lập chuột theo toạ độ pixel canvas) → ra đúng byte như người chơi thật gửi, không phải đoán toạ độ mỗi khi canvas resize/scale.
- Turnstile chỉ chặn login form → dùng persistent profile/cookie đã login sẵn để né hoàn toàn.

## Phase A — Feasibility spike (làm trước, quan trọng nhất)

Mục tiêu: chứng minh đọc-được-state và gửi-được-move trước khi đầu tư AI. Đây là rủi ro lớn nhất của toàn dự án.

Nhờ đã đọc được source tĩnh, Phase A giờ là **verify + fill gaps** thay vì dò mù từ đầu:

1. **Launch trình duyệt với profile đã login**: `playwright.chromium.launch_persistent_context(user_data_dir=...)` trỏ vào Chrome profile thật (hoặc export `storage_state`) → mở `zigavn.com`, xác nhận đã đăng nhập (không thấy form login/Turnstile).
2. **Hook trực tiếp vào đúng class đã tìm được** qua `page.evaluate`/`addInitScript`: patch `BkConnectionManager.send` (log mọi packet gửi đi: `Type`, args gốc trước khi encode) và patch `BkChessInGameLogic.prototype.$g` / `BkCoUpInGameLogic.prototype.$g` (log mọi packet nhận, đối chiếu `a.Type` với opcode đã biết: `De`=28 move, `Ie`=30 reveal).
3. **Verify từng opcode đã suy ra** bằng cách chơi thử 1 ván tay và log song song: click chọn quân mình → in `this.tc`/kết quả `QR(e)` xem đúng là danh sách ô hợp lệ không; di chuyển → xác nhận gói gửi đi đúng `Type=28` với 4 byte `[fromCol,fromRow,toCol,toRow]` khớp thao tác thật; quân úp bị di chuyển → xác nhận broadcast `Type=30` đúng `[position,revealedType]`.
4. **Xác định cơ chế auth/session**: kiểm tra `BkGlobal.XR()` được gọi khi nào, client ID lấy từ đâu (cookie/localStorage/`NativeInterface`) — để biết chính xác cách "tái sử dụng session đã login" hoạt động ở tầng network, không chỉ ở tầng HTTP cookie.
5. **Test gửi action ngược**: gọi lại `BkChessBaseIngameLayer.prototype.fU(col,row)` hoặc trực tiếp `T().PP(fromCol,fromRow,toCol,toRow)` bằng `page.evaluate()` mà không cần chuột thật → xác nhận quân di chuyển thật trên bàn.
6. **Deliverable Phase A**: 1 script nhỏ chơi được ít nhất "1 nước lật + 1 nước đi" hoàn toàn bằng code, kèm bảng đối chiếu opcode suy từ static analysis vs thực tế quan sát được (để cập nhật lại mục Protocol map phía trên nếu có sai lệch).
7. **Fallback nếu Phase A thất bại**: nếu hook JS bị chặn hoàn toàn (khó xảy ra vì code không obfuscate), phương án còn lại là computer-vision đọc canvas + giả lập chuột theo pixel (chậm hơn, kém robust hơn) — sẽ cần quyết định lại với người dùng nếu rơi vào trường hợp này.

## Phase B — Build đầy đủ (chỉ làm sau khi Phase A pass)

| Module | Việc |
|---|---|
| `session.py` | Mở persistent context, kiểm tra login, xử lý session hết hạn (báo lỗi rõ ràng để re-login tay, không tự động điền lại form vì sẽ đụng Turnstile) |
| `bridge.py` | Hook JS (từ Phase A) đóng gói thành class ổn định, đẩy state qua Python real-time |
| `matchmaking.py` | Điều hướng menu → CỜ ÚP → chọn bàn/mức cược → bấm tìm bàn tự động, nhận diện `NETWORK_TABLE_JOIN_SUCCESS`/`NETWORK_GAME_JOIN_SUCCESS` |
| `engine.py` | Luật cờ úp đầy đủ: sinh nước đi hợp lệ cho quân đã lộ, xử lý Sĩ/Tượng qua sông, Pháo ăn cách quân, phát hiện chiếu bí/hết nước/hòa 120 nước |
| `belief.py` | Bayesian belief state: xác suất mỗi quân úp còn lại của đối thủ là loại gì, dựa trên số lượng từng loại quân còn chưa lộ + lịch sử đã lật |
| `ai.py` | Monte Carlo determinization: sample vài "bàn cờ cụ thể" theo belief → chạy minimax/alpha-beta (độ sâu nông, vì nhánh rất rộng do có nước "lật") trên mỗi sample → trung bình kết quả để chọn nước tốt nhất |
| `actions.py` | Thực thi nước đã chọn qua hàm JS nội bộ (từ Phase A bước 4); delay ngẫu nhiên hợp lý giữa các bước cho tự nhiên (chỉ để UX không giật cục, không thiết kế để né phát hiện anti-cheat) |
| `loop.py` / `main.py` | Orchestration: login → tìm bàn → chờ lượt → AI quyết định → thực thi → phát hiện kết thúc ván → lặp lại hoặc dừng |

## Rủi ro cần nắm rõ

- **Vi phạm ToS / rủi ro khoá tài khoản**: tự động chơi gần như chắc chắn vi phạm điều khoản dịch vụ của Ziga. Đây là quyết định của người dùng với tài khoản của họ — không khuyến nghị dùng cho bàn cược thật.
- **Session hết hạn**: cookie/token WS có thể ngắn hạn hơn cookie HTTP → cần verify ở Phase A, có thể phải re-login tay theo chu kỳ.
- **Client update**: nếu Ziga đổi minified code, hook ở `bridge.py`/`actions.py` có thể vỡ, cần bảo trì định kỳ.
- **Giới hạn của AI công bằng**: Monte Carlo determinization chơi khá tốt cho game ẩn tin tương tự (Banqi, Stratego) nhưng không "biết trước" như đọc state thật — kỳ vọng hợp lý, không phải bất khả chiến bại.

## Verification

- **Phase A**: chạy script, quan sát canvas thật đổi trạng thái đúng như lệnh gửi từ Python; log state khớp với những gì mắt thấy trên UI.
- **Phase B**: chơi thử 1 ván đầy đủ ở bàn cược thấp/tập luyện, log toàn bộ nước đi, so sánh kết quả thắng/thua/hòa engine tính ra có khớp thực tế game báo không.

## Next step

Bắt đầu code Phase A (feasibility spike) — mục tiêu duy nhất là chứng minh đọc-state + gửi-move hoạt động, trước khi đầu tư vào `belief.py`/`ai.py`.
