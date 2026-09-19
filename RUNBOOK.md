# Runbook: chạy Phase A feasibility spike

## 1. Cài đặt

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## 2. Chạy spike

```bash
python scripts/phase_a_spike.py
```

Lần đầu chạy, một cửa sổ Chromium sẽ mở tới `zigavn.com` với profile riêng lưu ở
`.chrome-profile/` (đã gitignore). Nếu chưa đăng nhập, script chỉ đợi — **tự đăng
nhập tay** trong cửa sổ đó (kể cả giải Turnstile nếu hiện ra). Các lần chạy sau,
cookie/localStorage còn nguyên trong `.chrome-profile/` nên vào thẳng, không cần
đăng nhập lại.

Sau khi login xong:

1. Script in "Đã login." rồi chờ bạn **tự dùng chuột** vào menu, chọn **CỜ ÚP**,
   vào một bàn (khuyến khích bàn tập luyện/cược thấp) và chờ ván bắt đầu.
2. Nhấn Enter trong terminal khi ván đã bắt đầu.
3. Script bơm `hook.js` vào trang và chờ patch xong các class nội bộ. Nếu báo lỗi
   timeout ở bước này, gần như chắc chắn Ziga đã đổi tên biến/hàm trong
   `gamelogic.min.js` — xem mục "Nếu hook không hoạt động" bên dưới.
4. Vào REPL với các lệnh:
   - `board` — in toàn bộ trạng thái bàn cờ đọc được (đối chiếu bằng mắt với UI thật)
   - `dump <idx>` — in thô mọi field của quân cờ số `idx` (0-31), dùng để xác nhận
     tên field (`col`, `row`, `owner`, `type`...) đang đúng
   - `select <idx>` — chọn quân số `idx` (tương đương bấm chuột vào quân đó)
   - `moves` — in các ô hợp lệ mà client vừa tính cho quân đang chọn (thông tin công
     bằng — đúng cái một người chơi thật thấy khi được bôi sáng)
   - `move <col> <row>` — gửi nước đi từ quân đang chọn tới ô (col,row) **hoàn toàn
     bằng code**, không đụng chuột
   - `quit` — thoát

**Tiêu chí Phase A pass**: gõ `select`, `moves`, `move` cho ra đúng 1 nước đi thật
trên bàn (nhìn thấy quân di chuyển/lật trên UI), và log `[event] network_event ...`
xuất hiện tương ứng khi bạn tự chơi tay 1-2 nước để đối chiếu.

## 3. Nếu hook không hoạt động

`docs/FINDINGS.md` liệt kê chi tiết các tên class/field suy ra từ đọc tĩnh
`gamelogic.min.js` (đã minify, tên biến 1-2 ký tự, có thể đổi bất cứ lúc nào Ziga
deploy bản mới). Nếu `bridge.wait_ready()` timeout hoặc `board`/`dump` trả về
`None`/field sai:

1. Tải lại bản JS mới nhất từ `https://zigavn.com/zigavn.com/gamelogic.min.js`
   (hoặc mở DevTools > Network khi vào trang thật để lấy đúng URL kèm query version).
2. Beautify lại để đọc:
   ```bash
   npm install --no-save js-beautify
   ./node_modules/.bin/js-beautify -f <file-moi>.js -o .scratch/gamelogic.beautified.js
   ```
3. Tìm lại các điểm neo trong `docs/FINDINGS.md` (`BkCoUpInGameLogic`, `.$g`,
   `BkChessBaseIngameLayer`, `layer.T().PP(...)`) — nếu tên class vẫn còn (Ziga hiếm
   khi đổi tên class, thường chỉ đổi tên field/hàm nội bộ do minifier mới), chỉ cần
   sửa lại field name tương ứng trong `zigacoup/hook.js`.
4. Cập nhật `docs/FINDINGS.md` với phát hiện mới.

## 4. Rủi ro cần nhớ (xem thêm PLAN.md)

- Tự động chơi vi phạm ToS của Ziga — không dùng ở bàn cược thật khi chưa xác nhận ổn định.
- Đóng cửa sổ trình duyệt hoặc `Ctrl+C` bất cứ lúc nào để dừng — chưa có gì tự động
  gửi request khi bạn không chủ động gõ lệnh trong REPL.
