#!/usr/bin/env python3
"""
MegaXcess Mapping Tool
- 讀取 Provider PDF (Regex 解析)
- 與 DB (slot_game_setting_i18n) 比對
- 直接寫入 tiger_thirdparty.megaxcess_game_type_mapping

Build EXE:
    pip install pyinstaller pdfplumber mysql-connector-python
    pyinstaller --onefile --windowed --collect-all=pdfplumber
                --hidden-import=mysql.connector
                --name="MegaXcess Mapping Tool"
                megaxcess_mapping_tool.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import re
import os

# ── 已知 Provider ──────────────────────────────────────────────────
KNOWN_PROVIDERS = [
    (27,  "JDB_SLOT"),
    (36,  "JILI"),
    (38,  "CQ9_SLOT"),
    (40,  "PP_SLOT"),
    (41,  "NETENT"),
    (42,  "REDTIGER"),
]

# ── 預設 DB 設定 ────────────────────────────────────────────────────
DEFAULT_DB_HOST = "tiger-dev-rds.servicelab.sh"
DEFAULT_DB_PORT = 3306
DEFAULT_DB_USER = "inno_rd"
DEFAULT_DB_PASS = "29SU5Rkt"


# ══════════════════════════════════════════════════════════════════════
class MappingTool(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("MegaXcess Mapping Tool")
        self.geometry("1000x720")
        self.resizable(True, True)

        self.pdf_path     = tk.StringVar()
        self.provider_var = tk.StringVar(value="41 (NETENT)")
        self.db_host      = tk.StringVar(value=DEFAULT_DB_HOST)
        self.db_port      = tk.StringVar(value=str(DEFAULT_DB_PORT))
        self.db_user      = tk.StringVar(value=DEFAULT_DB_USER)
        self.db_pass      = tk.StringVar(value=DEFAULT_DB_PASS)

        self.preview_data: list = []

        self._build_ui()

    # ── UI ─────────────────────────────────────────────────────────
    def _build_ui(self):
        # DB Config
        db_frame = ttk.LabelFrame(self, text=" DB Config ", padding=8)
        db_frame.pack(fill='x', padx=10, pady=(8, 4))

        ttk.Label(db_frame, text="Host:").grid(row=0, column=0, sticky='w')
        ttk.Entry(db_frame, textvariable=self.db_host, width=34).grid(row=0, column=1, padx=4)
        ttk.Label(db_frame, text="Port:").grid(row=0, column=2)
        ttk.Entry(db_frame, textvariable=self.db_port, width=6).grid(row=0, column=3, padx=4)
        ttk.Label(db_frame, text="User:").grid(row=0, column=4, padx=(10, 0))
        ttk.Entry(db_frame, textvariable=self.db_user, width=12).grid(row=0, column=5)
        ttk.Label(db_frame, text="Pass:").grid(row=0, column=6, padx=(10, 0))
        ttk.Entry(db_frame, textvariable=self.db_pass, width=14, show="*").grid(row=0, column=7)
        ttk.Button(db_frame, text="Test DB", command=self._test_db, width=9).grid(row=0, column=8, padx=8)

        # Input
        in_frame = ttk.LabelFrame(self, text=" Input ", padding=8)
        in_frame.pack(fill='x', padx=10, pady=4)

        ttk.Label(in_frame, text="Provider:").grid(row=0, column=0, sticky='w')
        prov_values = [f"{c} ({n})" for c, n in KNOWN_PROVIDERS]
        ttk.Combobox(in_frame, textvariable=self.provider_var,
                     values=prov_values, width=20).grid(row=0, column=1, padx=6)

        ttk.Label(in_frame, text="PDF:").grid(row=0, column=2, padx=(20, 0))
        ttk.Entry(in_frame, textvariable=self.pdf_path, width=46).grid(row=0, column=3, padx=4)
        ttk.Button(in_frame, text="Browse...", command=self._browse_pdf).grid(row=0, column=4)
        ttk.Button(in_frame, text="  Parse PDF  ",
                   command=self._start_parse).grid(row=0, column=5, padx=10)

        # Status + Progress
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(self, textvariable=self.status_var, anchor='w',
                  relief='sunken').pack(fill='x', padx=10, pady=(4, 0))
        self.progress = ttk.Progressbar(self, mode='indeterminate')
        self.progress.pack(fill='x', padx=10, pady=2)

        # Preview Table
        prev_frame = ttk.LabelFrame(self, text=" Preview ", padding=5)
        prev_frame.pack(fill='both', expand=True, padx=10, pady=4)

        cols = ('action', 'game_code', 'game_name', 'game_type', 'game_offering')
        self.tree = ttk.Treeview(prev_frame, columns=cols, show='headings', height=16)
        widths = {'action': 70, 'game_code': 170, 'game_name': 340, 'game_type': 85, 'game_offering': 95}
        for c in cols:
            self.tree.heading(c, text=c.replace('_', ' ').title())
            self.tree.column(c, width=widths[c], anchor='w', stretch=(c == 'game_name'))

        vsb = ttk.Scrollbar(prev_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        self.tree.tag_configure('new',    background='#d4edda', foreground='#155724')
        self.tree.tag_configure('update', background='#fff3cd', foreground='#856404')
        self.tree.tag_configure('skip',   background='#f8f9fa', foreground='#6c757d')

        # Bottom Bar
        bot = ttk.Frame(self)
        bot.pack(fill='x', padx=10, pady=6)

        self.summary_var = tk.StringVar(value="")
        ttk.Label(bot, textvariable=self.summary_var).pack(side='left', padx=4)
        self.apply_btn = ttk.Button(bot, text="  Apply to DB  ",
                                    command=self._apply_to_db, state='disabled')
        self.apply_btn.pack(side='right', padx=4)
        ttk.Button(bot, text="Export SQL", command=self._export_sql).pack(side='right', padx=4)

        # Log
        log_frame = ttk.LabelFrame(self, text=" Log ", padding=4)
        log_frame.pack(fill='x', padx=10, pady=(0, 8))
        self.log_box = scrolledtext.ScrolledText(
            log_frame, height=5, state='disabled',
            font=('Consolas', 9), bg='#1e1e1e', fg='#d4d4d4')
        self.log_box.pack(fill='x')

    # ── Helpers ────────────────────────────────────────────────────
    def _log(self, msg: str):
        self.log_box.config(state='normal')
        self.log_box.insert('end', msg + '\n')
        self.log_box.see('end')
        self.log_box.config(state='disabled')
        self.update_idletasks()

    def _set_status(self, msg: str):
        self.status_var.set(msg)
        self.update_idletasks()

    def _browse_pdf(self):
        path = filedialog.askopenfilename(
            title="Select Game List PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if path:
            self.pdf_path.set(path)

    def _get_provider_code(self) -> int:
        val = self.provider_var.get().strip()
        m = re.match(r'^(\d+)', val)
        if m:
            return int(m.group(1))
        raise ValueError(f"Cannot parse provider code: '{val}'")

    def _get_db_conn(self):
        import mysql.connector
        return mysql.connector.connect(
            host=self.db_host.get(),
            port=int(self.db_port.get()),
            user=self.db_user.get(),
            password=self.db_pass.get(),
            database='tiger_thirdparty',
            charset='utf8mb4',
            connection_timeout=10,
            use_pure=True,
        )

    def _test_db(self):
        try:
            conn = self._get_db_conn()
            conn.close()
            messagebox.showinfo("DB Test", "Connection successful!")
        except Exception as e:
            messagebox.showerror("DB Error", str(e))

    # ── Parse Flow ─────────────────────────────────────────────────
    def _start_parse(self):
        if not self.pdf_path.get():
            messagebox.showwarning("Warning", "Please select a PDF file first.")
            return
        try:
            self._get_provider_code()
        except ValueError as e:
            messagebox.showwarning("Warning", str(e))
            return
        self.apply_btn.config(state='disabled')
        self.progress.start()
        threading.Thread(target=self._do_parse, daemon=True).start()

    def _do_parse(self):
        try:
            provider = self._get_provider_code()

            # 1. PDF 解析
            self._set_status("Parsing PDF...")
            self._log(f"[PDF] {self.pdf_path.get()}")
            pdf_games = self._parse_pdf(self.pdf_path.get())
            self._log(f"[PDF] Extracted {len(pdf_games)} games")

            # 2. DB 比對
            self._set_status("Querying DB...")
            db_codes = self._get_db_codes(provider)
            self._log(f"[DB] slot_game_setting_i18n: {len(db_codes)} codes for provider={provider}")
            existing = self._get_existing_mapping(provider)
            self._log(f"[DB] megaxcess_game_type_mapping: {len(existing)} existing entries")

            # 3. Preview
            rows = self._build_preview(pdf_games, db_codes, existing, provider)
            n = sum(1 for r in rows if r['action'] == 'NEW')
            u = sum(1 for r in rows if r['action'] == 'UPDATE')
            s = sum(1 for r in rows if r['action'] == 'SKIP')
            self._log(f"[Preview] NEW={n}  UPDATE={u}  SKIP={s}")

            self.after(0, lambda: self._show_preview(rows))
            self._set_status(f"Done.  Total={len(rows)}  NEW={n}  UPDATE={u}  SKIP={s}")

        except Exception as e:
            import traceback as tb
            self._log(f"[ERROR]\n{tb.format_exc()}")
            self._set_status(f"Error: {e}")
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.after(0, self.progress.stop)

    # ── PDF Regex Parse ────────────────────────────────────────────
    def _parse_pdf(self, pdf_path: str) -> dict:
        import pdfplumber

        result = {}
        pattern = re.compile(
            r'\s*\d+\.\s+'
            r'(eCASINO\s+G\s*AMES|eBINGO\s+G\s*AMES)\s+'
            r'(.+?)\s+'
            r'([a-z0-9_\-]{4,32})\s+-\s+[\d.]+\s+'
            r'(SLOT|TABLE|LIVE|FISHING|ARCADE|VIDEO\s*POKER|BINGO)'
        )
        offering_map = {'eCASINO G AMES': 'EGAMES', 'eBINGO G AMES': 'EBINGO'}

        with pdfplumber.open(pdf_path) as pdf:
            self._log(f"[PDF] Pages: {len(pdf.pages)}")
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                for line in text.split('\n'):
                    m = pattern.match(line)
                    if m:
                        offering_raw = re.sub(r'\s+', ' ', m.group(1)).strip()
                        result[m.group(3).strip()] = {
                            'game_name':     m.group(2).strip(),
                            'game_type':     re.sub(r'\s+', '_', m.group(4).strip()),
                            'game_offering': offering_map.get(offering_raw, 'EGAMES'),
                        }
        return result

    # ── DB Queries ─────────────────────────────────────────────────
    def _get_db_codes(self, provider: int) -> dict:
        conn = self._get_db_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT code, MAX(name) as name
            FROM tiger_thirdparty.slot_game_setting_i18n
            WHERE provider = %s AND language = 2
            GROUP BY code ORDER BY code
        """, (provider,))
        result = {code: (name or '') for code, name in cur.fetchall()}
        cur.close(); conn.close()
        return result

    def _get_existing_mapping(self, provider: int) -> dict:
        conn = self._get_db_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT game_code, game_name, game_type, game_offering
            FROM tiger_thirdparty.megaxcess_game_type_mapping
            WHERE provider = %s
        """, (provider,))
        result = {r['game_code']: r for r in cur.fetchall()}
        cur.close(); conn.close()
        return result

    # ── Build Preview ──────────────────────────────────────────────
    @staticmethod
    def _norm(s: str) -> str:
        s = re.sub(r"[^A-Z0-9]", "_", s.upper())
        return re.sub(r"_+", "_", s).strip("_")

    def _build_preview(self, pdf_games: dict, db_codes: dict, existing: dict, provider: int) -> list:
        rows = []
        for code, db_name in sorted(db_codes.items()):
            if code in pdf_games:
                g     = pdf_games[code]
                name  = g['game_name']
                gtype = g['game_type']
                offer = g['game_offering']
            else:
                name  = db_name or code
                gtype = 'SLOT'
                offer = 'EGAMES'

            if code in existing:
                ex = existing[code]
                action = 'SKIP' if (ex['game_type'] == gtype and ex['game_offering'] == offer) else 'UPDATE'
            else:
                action = 'NEW'

            rows.append({
                'action':          action,
                'provider':        provider,
                'game_code':       code,
                'game_name':       name,
                'normalized_name': self._norm(name),
                'game_type':       gtype,
                'game_offering':   offer,
            })
        return rows

    # ── Show Preview ───────────────────────────────────────────────
    def _show_preview(self, rows: list):
        self.preview_data = rows
        for item in self.tree.get_children():
            self.tree.delete(item)

        n = u = s = 0
        for r in rows:
            a = r['action']
            self.tree.insert('', 'end',
                             values=(a, r['game_code'], r['game_name'],
                                     r['game_type'], r['game_offering']),
                             tags=(a.lower(),))
            if a == 'NEW':    n += 1
            elif a == 'UPDATE': u += 1
            else: s += 1

        self.summary_var.set(f"Total: {len(rows)}   NEW: {n}   UPDATE: {u}   SKIP: {s}")
        if n + u > 0:
            self.apply_btn.config(state='normal')

    # ── Export SQL ─────────────────────────────────────────────────
    def _export_sql(self):
        if not self.preview_data:
            messagebox.showwarning("Warning", "No data to export. Parse a PDF first.")
            return
        try:
            code = self._get_provider_code()
        except ValueError:
            code = "unknown"

        path = filedialog.asksaveasfilename(
            defaultextension='.sql',
            filetypes=[("SQL files", "*.sql"), ("All files", "*.*")],
            initialfile=f"provider_{code}_mapping.sql")
        if not path:
            return

        with open(path, 'w', encoding='utf-8') as f:
            f.write(self._make_sql(self.preview_data))
        messagebox.showinfo("Export", f"SQL exported to:\n{path}")

    # ── Apply to DB ────────────────────────────────────────────────
    def _apply_to_db(self):
        active = [r for r in self.preview_data if r['action'] in ('NEW', 'UPDATE')]
        if not active:
            messagebox.showinfo("Info", "Nothing to apply.")
            return
        if not messagebox.askyesno("Confirm",
                                   f"Apply {len(active)} rows to DB?\n(NEW + UPDATE only)"):
            return
        threading.Thread(target=self._do_apply, daemon=True).start()

    def _do_apply(self):
        try:
            self.progress.start()
            self._set_status("Applying to DB...")
            active = [r for r in self.preview_data if r['action'] in ('NEW', 'UPDATE')]

            conn = self._get_db_conn()
            cur = conn.cursor()
            sql = """
                INSERT INTO tiger_thirdparty.megaxcess_game_type_mapping
                    (provider, game_code, game_name, normalized_name, game_type, game_offering)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    game_name       = VALUES(game_name),
                    normalized_name = VALUES(normalized_name),
                    game_type       = VALUES(game_type),
                    game_offering   = VALUES(game_offering)
            """
            batch = [(r['provider'], r['game_code'], r['game_name'],
                      r['normalized_name'], r['game_type'], r['game_offering'])
                     for r in active]
            cur.executemany(sql, batch)
            conn.commit()
            affected = cur.rowcount
            cur.close(); conn.close()

            self._log(f"[DB] Applied {len(active)} rows, rowcount={affected}")
            self._set_status(f"Done. Applied {len(active)} rows.")
            self.after(0, lambda: messagebox.showinfo(
                "Success", f"Applied {len(active)} rows.\nrowcount={affected}"))

        except Exception as e:
            import traceback as tb
            self._log(f"[ERROR]\n{tb.format_exc()}")
            self._set_status(f"Error: {e}")
            self.after(0, lambda: messagebox.showerror("DB Error", str(e)))
        finally:
            self.after(0, self.progress.stop)

    # ── Generate SQL ───────────────────────────────────────────────
    @staticmethod
    def _make_sql(rows: list) -> str:
        active = [r for r in rows if r['action'] in ('NEW', 'UPDATE')]
        if not active:
            return "-- No changes to apply\n"

        def esc(s): return str(s).replace("'", "''")

        parts = []
        for r in active:
            parts.append(
                f"    -- {r['action']}: {r['game_code']}\n"
                f"    ({r['provider']}, '{esc(r['game_code'])}', '{esc(r['game_name'])}', "
                f"'{esc(r['normalized_name'])}', '{r['game_type']}', '{r['game_offering']}')"
            )

        return (
            "INSERT INTO tiger_thirdparty.megaxcess_game_type_mapping\n"
            "    (provider, game_code, game_name, normalized_name, game_type, game_offering)\n"
            "VALUES\n"
            + ",\n".join(parts) + "\n"
            "ON DUPLICATE KEY UPDATE\n"
            "    game_name       = VALUES(game_name),\n"
            "    normalized_name = VALUES(normalized_name),\n"
            "    game_type       = VALUES(game_type),\n"
            "    game_offering   = VALUES(game_offering);\n"
        )


# ══════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    import sys, traceback

    log_path = os.path.join(os.path.expanduser('~'), 'Desktop', 'megaxcess_tool_error.log')
    try:
        app = MappingTool()
        app.mainloop()
    except Exception as _e:
        with open(log_path, 'w', encoding='utf-8') as _f:
            _f.write(traceback.format_exc())
        try:
            import tkinter as _tk
            from tkinter import messagebox as _mb
            _r = _tk.Tk(); _r.withdraw()
            _mb.showerror("Startup Error", f"{_e}\n\nLog: {log_path}")
            _r.destroy()
        except Exception:
            pass
        sys.exit(1)
