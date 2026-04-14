#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tiger Dev Tools - Unified Local Proxy Server
- GET  /{filename}.html  → 直接提供本機 HTML 頁面
- POST /proxy            → 轉發 API 請求（繞過瀏覽器 CORS 限制）
"""
import json
import os
import sys
import urllib.request
import urllib.error
import webbrowser
import threading
import tkinter as tk
from PIL import Image, ImageTk
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PORT = 8766
# 打包成 EXE 後 __file__ 會指向暫存目錄，改用 sys.executable 取得真正位置
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    RESOURCE_DIR = sys._MEIPASS   # 打包內的靜態資源
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RESOURCE_DIR = BASE_DIR


# ── Splash Screen ─────────────────────────────────────────────────────────────
def show_splash():
    W, H = 420, 340
    root = tk.Tk()
    root.overrideredirect(True)          # 無邊框
    root.attributes('-topmost', True)
    root.configure(bg='#0f172a')

    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f'{W}x{H}+{(sw-W)//2}+{(sh-H)//2}')

    canvas = tk.Canvas(root, width=W, height=H, bg='#0f172a', highlightthickness=0)
    canvas.pack()

    # 圓角背景效果（用矩形模擬）
    canvas.create_rectangle(0, 0, W, H, fill='#0f172a', outline='#334155', width=2)

    # ── Icon 圖片 ──────────────────────────────────────────────────────────────
    img_path = os.path.join(RESOURCE_DIR, 'splash.png')
    photo = None
    if os.path.exists(img_path):
        pil_img = Image.open(img_path).convert('RGBA').resize((140, 140), Image.LANCZOS)
        photo = ImageTk.PhotoImage(pil_img)
        canvas.create_image(W // 2, 120, image=photo)
        canvas._photo = photo   # 防止 GC 回收

    # ── 標題文字 ───────────────────────────────────────────────────────────────
    canvas.create_text(W // 2, 218,
                       text='後端開發人員工具',
                       font=('Microsoft JhengHei', 17, 'bold'),
                       fill='#e2e8f0')

    # ── 橫幅文字（從下方滑入）─────────────────────────────────────────────────
    BANNER_TEXT = '台雞店  關心您身心靈健康!~'
    banner_start_y = H + 30
    banner_end_y   = 270
    banner = canvas.create_text(W // 2, banner_start_y,
                                 text=BANNER_TEXT,
                                 font=('Microsoft JhengHei', 13),
                                 fill='#f48c06')

    # 底部細線裝飾
    line = canvas.create_line(40, H - 20, W - 40, H - 20, fill='#1e3a5f', width=1)

    STEPS = 35

    def animate(step=0):
        if step <= STEPS:
            t = step / STEPS
            # ease-out cubic
            ease = 1 - (1 - t) ** 3
            y = banner_start_y + (banner_end_y - banner_start_y) * ease
            canvas.coords(banner, W // 2, y)
            root.after(14, animate, step + 1)
        else:
            root.after(2200, root.destroy)  # 停留 2.2 秒後關閉

    root.after(200, animate)
    root.mainloop()
PROXY_TIMEOUT = 600   # 10 min，reconcile 大時間範圍時需要足夠等待

DEFAULT_PAGE = 'megaxcess-audit-reconcile-tool.html'


class Handler(BaseHTTPRequestHandler):

    # ── OPTIONS preflight ────────────────────────────────────────────────────
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    # ── GET：提供 HTML 靜態頁面 ──────────────────────────────────────────────
    def do_GET(self):
        path = self.path.split('?')[0].lstrip('/')
        if not path:
            self._redirect('/' + DEFAULT_PAGE)
            return

        file_path = os.path.join(BASE_DIR, path)
        MIME = {'.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css'}
        ext  = os.path.splitext(path)[1].lower()
        if os.path.isfile(file_path) and ext in MIME:
            with open(file_path, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', f'{MIME[ext]}; charset=utf-8')
            self._cors()
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(404)
            self._cors()
            self.end_headers()
            self.wfile.write(f'Not found: {path}'.encode('utf-8'))

    # ── POST /proxy：轉發 API 請求 ──────────────────────────────────────────
    def do_POST(self):
        if self.path.split('?')[0] != '/proxy':
            self.send_response(404)
            self._cors()
            self.end_headers()
            return

        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw)
        except Exception:
            self.send_response(400)
            self._cors()
            self.end_headers()
            self.wfile.write(b'Invalid JSON body')
            return

        target_url  = data.get('url', '')
        fwd_headers = data.get('headers', {})
        fwd_method  = data.get('method', 'GET').upper()

        print(f'[proxy] {fwd_method} {target_url}')

        req = urllib.request.Request(
            target_url,
            headers=fwd_headers,
            method=fwd_method
        )
        try:
            with urllib.request.urlopen(req, timeout=PROXY_TIMEOUT) as resp:
                resp_body = resp.read()
                self.send_response(resp.status)
                self.send_header('Content-Type',
                                 resp.headers.get('Content-Type', 'application/json'))
                self._cors()
                self.end_headers()
                self.wfile.write(resp_body)

        except urllib.error.HTTPError as e:
            resp_body = e.read()
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            self.wfile.write(resp_body)

        except Exception as e:
            self.send_response(502)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))

    # ── helpers ──────────────────────────────────────────────────────────────
    def _redirect(self, location):
        self.send_response(302)
        self.send_header('Location', location)
        self.end_headers()

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')

    def log_message(self, fmt, *args):
        print(f'[{self.log_date_time_string()}] {fmt % args}')


if __name__ == '__main__':
    open_page = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PAGE
    server = ThreadingHTTPServer(('localhost', PORT), Handler)

    print('=' * 52)
    print('  Tiger Dev Tools Proxy')
    print(f'  http://localhost:{PORT}')
    print(f'  Opening : {open_page}')
    print('  Close this window to stop the server.')
    print('=' * 52)

    # 背景跑 server，splash 結束後再開瀏覽器
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # Splash 動畫（阻塞直到關閉）
    show_splash()

    # Splash 結束後開啟瀏覽器
    webbrowser.open(f'http://localhost:{PORT}/{open_page}')

    try:
        server_thread.join()
    except KeyboardInterrupt:
        print('\nServer stopped.')
