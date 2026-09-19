"""Phase A - session.py

Mo Chromium voi 1 profile ben (persistent context) de tai dung cookie da login,
tranh dung phai Cloudflare Turnstile (chi chan login form).

Lan dau chay: user_data_dir rong -> cua so trinh duyet hien ra, tu dang nhap tay
1 lan (script chi cho, KHONG tu dien form). Cac lan sau: cookie/localStorage con
nguyen trong user_data_dir -> vao thang.
"""

from __future__ import annotations

import pathlib
import time

from playwright.sync_api import BrowserContext, Page, sync_playwright

ZIGA_URL = "https://zigavn.com/"
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_USER_DATA_DIR = REPO_ROOT / ".chrome-profile"


class Session:
    def __init__(self, user_data_dir: pathlib.Path | None = None, headless: bool = False):
        self.user_data_dir = pathlib.Path(user_data_dir or DEFAULT_USER_DATA_DIR)
        self.headless = headless
        self._pw = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    def __enter__(self) -> "Session":
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        self.context = self._pw.chromium.launch_persistent_context(
            str(self.user_data_dir),
            headless=self.headless,
            viewport={"width": 1280, "height": 800},
        )
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.goto(ZIGA_URL, wait_until="domcontentloaded")
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.context:
            self.context.close()
        if self._pw:
            self._pw.stop()

    def wait_for_login(self, timeout: float = 300.0) -> bool:
        """Doi cc.username khac rong. Neu profile chua login, cua so van mo de
        nguoi dung tu dang nhap tay (ke ca vuot Turnstile) - script chi cho."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                username = self.page.evaluate("window.cc && window.cc.username || ''")
            except Exception:
                username = ""
            if username:
                return True
            time.sleep(1.0)
        return False


if __name__ == "__main__":
    with Session() as session:
        print(f"Da mo {ZIGA_URL} voi profile: {session.user_data_dir}")
        print("Neu chua login, hay dang nhap tay trong cua so trinh duyet vua mo (bao gom Turnstile neu co).")
        ok = session.wait_for_login(timeout=300)
        print("Login OK, cc.username co gia tri." if ok else "Timeout cho login (300s).")
        input("Nhan Enter de dong trinh duyet...")
