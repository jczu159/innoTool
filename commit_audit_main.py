"""
Tiger Missing Commit Finder
找出哪些 commit 已存在於 remote tag / release branch，但尚未 cherry-pick 進 main。
支援單筆右鍵 / 圈選批次 cherry-pick。
"""
import os
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import config_manager as cfg

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────
CONFIG_KEY    = "commit_audit"
DEFAULT_ROOT  = r"D:\tigerProject"
DEFAULT_MAIN  = "origin/main"
FETCH_WORKERS = 10

EXCLUDED_DIRS = {
    "tiger-tools", "tiger-value", "tiger-values", "tiger-wallet",
    "tiger-sqlddl", "tiger-sign", "tiger-s3-lambda", "tiger-registry",
    "tiger-proxy", "tiger-project", "tiger-oncall-sql", "tiger-initial",
    "tiger-blockchain", "tiger-actuator", ".git", "__pycache__",
    "node_modules", "dist", "build",
}

COL_SVC    = "service"
COL_HASH   = "hash"
COL_AUTHOR = "author"
COL_DATE   = "date"
COL_MSG    = "message"
COL_REFS   = "refs"
COL_STATUS = "cp_status"   # cherry-pick 結果欄


# ─────────────────────────────────────────────
# Git helpers
# ─────────────────────────────────────────────
def _run_git(repo: str, args: list, timeout: int = 60):
    try:
        r = subprocess.run(
            ["git"] + args, cwd=repo,
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace"
        )
        return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "timeout"
    except Exception as e:
        return False, "", str(e)


def fetch_repo(repo: str):
    return _run_git(repo, ["fetch", "--all", "--tags", "--prune", "--force"], timeout=120)


def current_branch(repo: str) -> str:
    ok, out, _ = _run_git(repo, ["branch", "--show-current"])
    return out.strip() if ok else "unknown"


def cherry_pick(repo: str, commit_hash: str):
    """執行 git cherry-pick -x <hash>，回傳 (ok, stdout, stderr)"""
    return _run_git(repo, ["cherry-pick", "-x", commit_hash], timeout=60)


def cherry_pick_abort(repo: str):
    return _run_git(repo, ["cherry-pick", "--abort"], timeout=30)


_RELEASE_RE = re.compile(r'release[-/]', re.IGNORECASE)


def get_release_refs(repo: str) -> list[str]:
    """回傳符合 release-x.y.z 或 release/x.y.z 格式的所有 tag 與 remote branch。"""
    refs = []

    # tags: release-5.39.7 / release/5.39.7
    ok, out, _ = _run_git(repo, ["tag", "--list"], timeout=30)
    if ok and out:
        for tag in out.splitlines():
            tag = tag.strip()
            if _RELEASE_RE.match(tag):
                refs.append(f"refs/tags/{tag}")

    # remote branches: origin/release/5.39.4
    ok, out, _ = _run_git(repo, ["branch", "-r", "--list"], timeout=30)
    if ok and out:
        for branch in out.splitlines():
            branch = branch.strip().lstrip("* ")
            if _RELEASE_RE.search(branch):
                refs.append(branch)

    return refs


def get_missing_commits(repo: str, author: str, date_from: str, date_to: str,
                        main_branch: str = "origin/main") -> list[dict]:
    release_refs = get_release_refs(repo)
    if not release_refs:
        return []   # 這個 repo 沒有任何 release tag/branch，直接略過

    fmt  = "%H|%h|%an|%ad|%s|%D"
    args = (
        ["log"] + release_refs + ["--not", main_branch,
        "--format=" + fmt,
        "--date=format:%Y-%m-%d %H:%M",
        "--no-walk=unsorted"]   # 避免只走 tag tips，要走完整 log
    )
    # --no-walk 在這裡反而不對：我們要看 range，拿掉
    args = ["log"] + release_refs + ["--not", main_branch,
            "--format=" + fmt, "--date=format:%Y-%m-%d %H:%M"]

    if author.strip():
        args += [f"--author={author.strip()}"]
    if date_from.strip():
        args += [f"--after={date_from.strip()} 00:00:00"]
    if date_to.strip():
        args += [f"--before={date_to.strip()} 23:59:59"]

    ok, out, _ = _run_git(repo, args, timeout=60)
    if not ok or not out:
        return []

    main_name = main_branch.split("/")[-1]
    results = []
    seen = set()
    for line in out.splitlines():
        parts = line.split("|", 5)
        if len(parts) < 6:
            continue
        full_hash, short_hash, auth, date, msg, refs = parts
        if full_hash in seen:
            continue
        seen.add(full_hash)
        # 只保留 release 相關的 ref 標示
        clean_refs = ", ".join(
            r.strip() for r in refs.split(",")
            if r.strip()
            and "origin/HEAD" not in r
            and main_name not in r
        )
        results.append({
            "hash":       full_hash,
            "short_hash": short_hash,
            "author":     auth,
            "date":       date,
            "message":    msg,
            "refs":       clean_refs or "(release ref)",
            "cp_status":  "",
        })
    return results


def is_valid_repo(path: str) -> bool:
    return os.path.isdir(path) and os.path.isdir(os.path.join(path, ".git"))


def discover_services(root: str) -> list[str]:
    if not os.path.isdir(root):
        return []
    return sorted(
        name for name in os.listdir(root)
        if name not in EXCLUDED_DIRS and is_valid_repo(os.path.join(root, name))
    )


# ─────────────────────────────────────────────
# Service row model
# ─────────────────────────────────────────────
class ServiceRow:
    def __init__(self, name: str, path: str):
        self.name    = name
        self.path    = path
        self.checked = True
        self.status  = "Ready" if is_valid_repo(path) else "Not Found"


# ─────────────────────────────────────────────
# Cherry-pick confirm dialog
# ─────────────────────────────────────────────
class CherryPickDialog(tk.Toplevel):
    """顯示即將 cherry-pick 的 commit 清單，讓使用者確認後執行。"""

    def __init__(self, parent, items: list[dict], service_paths: dict[str, str]):
        super().__init__(parent)
        self.title("確認 Cherry-pick")
        self.geometry("900x500")
        self.resizable(True, True)
        self.grab_set()

        self.items         = items          # list of result dict
        self.service_paths = service_paths  # name -> path
        self.confirmed     = False

        self._build(parent)

    def _build(self, parent):
        # 顯示每個服務目前在哪個 branch
        info_frm = ttk.LabelFrame(self, text="各服務目前 Branch", padding=6)
        info_frm.pack(fill=tk.X, padx=8, pady=(8, 0))

        services = sorted({it["service"] for it in self.items})
        for svc in services:
            path   = self.service_paths.get(svc, "")
            branch = current_branch(path) if path else "unknown"
            color  = "#f44747" if branch not in ("main",) else "#4ec94e"
            row = ttk.Frame(info_frm)
            row.pack(fill=tk.X, pady=1)
            ttk.Label(row, text=f"  {svc}", width=28, anchor=tk.W).pack(side=tk.LEFT)
            lbl = tk.Label(row, text=f"目前 branch: {branch}",
                           fg=color, bg=self.cget("bg"), font=("Consolas", 9, "bold"))
            lbl.pack(side=tk.LEFT)

        # Commit 清單
        list_frm = ttk.LabelFrame(self, text=f"即將 cherry-pick {len(self.items)} 筆 commit（由舊到新）", padding=4)
        list_frm.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        cols   = [COL_SVC, COL_HASH, COL_DATE, COL_MSG]
        hdrs   = {"service": "服務", "hash": "Hash", "date": "日期", "message": "Message"}
        widths = {"service": 140, "hash": 85, "date": 130, "message": 460}

        tree = ttk.Treeview(list_frm, columns=cols, show="headings", height=10)
        for c in cols:
            tree.heading(c, text=hdrs[c])
            tree.column(c, width=widths[c], anchor=tk.W)
        vsb = ttk.Scrollbar(list_frm, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # 依 service + date 排序（舊 → 新），確保順序正確
        sorted_items = sorted(self.items, key=lambda r: (r["service"], r["date"]))
        for i, r in enumerate(sorted_items):
            tree.insert("", tk.END, values=(
                r["service"], r["short_hash"], r["date"], r["message"]
            ), tags=("odd" if i % 2 else "even",))
        tree.tag_configure("odd",  background="#f9f9f9")
        tree.tag_configure("even", background="#ffffff")
        self.sorted_items = sorted_items  # 回傳給呼叫端使用

        # 警告
        warn = ttk.Label(self,
            text="⚠  cherry-pick 將直接套用到各服務的本地目前 branch，請確認已切換至正確 branch！",
            foreground="#ffcc00")
        warn.pack(padx=8, pady=(0, 4))

        # 按鈕列
        btn_frm = ttk.Frame(self)
        btn_frm.pack(pady=6)
        ttk.Button(btn_frm, text="✅ 確認執行", width=16,
                   command=self._on_confirm).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frm, text="❌ 取消",     width=12,
                   command=self.destroy).pack(side=tk.LEFT, padx=8)

    def _on_confirm(self):
        self.confirmed = True
        self.destroy()


# ─────────────────────────────────────────────
# Main App
# ─────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tiger Missing Commit Finder")
        self.geometry("1440x840")
        self.minsize(1100, 640)

        self._services: list[ServiceRow] = []
        self._results:  list[dict]       = []
        self._load_config()
        self._build_ui()
        self._apply_config()
        self._refresh_service_table()

    # ── Config ────────────────────────────────
    def _load_config(self):
        all_cfg    = cfg.load_config()
        self._cfg  = all_cfg.get(CONFIG_KEY, {})

    def _save_config(self):
        all_cfg = cfg.load_config()
        all_cfg[CONFIG_KEY] = {
            "root":        self.var_root.get().strip(),
            "main_branch": self.var_main.get().strip(),
            "author":      self.var_author.get().strip(),
            "date_from":   self.var_from.get().strip(),
            "date_to":     self.var_to.get().strip(),
        }
        cfg.save_config(all_cfg)
        self.log_inf("設定已儲存")

    def _apply_config(self):
        self.var_root.set(  self._cfg.get("root",        DEFAULT_ROOT))
        self.var_main.set(  self._cfg.get("main_branch", DEFAULT_MAIN))
        self.var_author.set(self._cfg.get("author",      ""))
        self.var_from.set(  self._cfg.get("date_from",   ""))
        self.var_to.set(    self._cfg.get("date_to",     ""))

    # ── UI Build ──────────────────────────────
    def _build_ui(self):
        self._build_settings_frame()
        self._build_filter_frame()
        self._build_main_area()
        self._build_log()

    def _build_settings_frame(self):
        frm = ttk.LabelFrame(self, text="目錄設定", padding=6)
        frm.pack(fill=tk.X, padx=8, pady=(8, 0))

        self.var_root = tk.StringVar()
        self.var_main = tk.StringVar()

        ttk.Label(frm, text="本地根目錄:").grid(row=0, column=0, sticky=tk.E, padx=(4, 2))
        ttk.Entry(frm, textvariable=self.var_root, width=42).grid(row=0, column=1, sticky=tk.W, padx=(0, 4))
        ttk.Button(frm, text="瀏覽", command=self._browse_root, width=6).grid(row=0, column=2, padx=2)

        ttk.Label(frm, text="Main Branch:").grid(row=0, column=3, sticky=tk.E, padx=(12, 2))
        ttk.Entry(frm, textvariable=self.var_main, width=18).grid(row=0, column=4, sticky=tk.W, padx=(0, 4))

        ttk.Button(frm, text="重新掃描服務", command=self._on_rescan,     width=14).grid(row=0, column=5, padx=6)
        ttk.Button(frm, text="儲存設定",     command=self._save_config,   width=10).grid(row=0, column=6, padx=2)

    def _build_filter_frame(self):
        frm = ttk.LabelFrame(self, text="篩選條件 & 操作", padding=6)
        frm.pack(fill=tk.X, padx=8, pady=(4, 0))

        self.var_author = tk.StringVar()
        self.var_from   = tk.StringVar()
        self.var_to     = tk.StringVar()

        ttk.Label(frm, text="作者:").grid(row=0, column=0, sticky=tk.E, padx=(4, 2))
        ttk.Entry(frm, textvariable=self.var_author, width=18).grid(row=0, column=1, sticky=tk.W, padx=(0, 8))

        ttk.Label(frm, text="從:").grid(row=0, column=2, sticky=tk.E, padx=(4, 2))
        ttk.Entry(frm, textvariable=self.var_from, width=13).grid(row=0, column=3, sticky=tk.W, padx=(0, 4))

        ttk.Label(frm, text="到:").grid(row=0, column=4, sticky=tk.E, padx=(4, 2))
        ttk.Entry(frm, textvariable=self.var_to, width=13).grid(row=0, column=5, sticky=tk.W, padx=(0, 10))

        ttk.Button(frm, text="🔍 Fetch+掃描",       command=self._on_fetch_and_scan, width=14).grid(row=0, column=6,  padx=3)
        ttk.Button(frm, text="⚡ 快速掃描",           command=self._on_quick_scan,     width=12).grid(row=0, column=7,  padx=3)

        ttk.Separator(frm, orient=tk.VERTICAL).grid(row=0, column=8, sticky="ns", padx=6)

        ttk.Button(frm, text="🍒 Cherry-pick 選取",  command=self._on_cherry_pick_selected, width=18,
                   style="Accent.TButton").grid(row=0, column=9,  padx=3)
        ttk.Button(frm, text="🍒 Cherry-pick 全部",  command=self._on_cherry_pick_all,      width=18).grid(row=0, column=10, padx=3)

        ttk.Separator(frm, orient=tk.VERTICAL).grid(row=0, column=11, sticky="ns", padx=6)

        ttk.Button(frm, text="📋 複製結果", command=self._on_copy_results,  width=11).grid(row=0, column=12, padx=3)
        ttk.Button(frm, text="🗑 清除",     command=self._on_clear_results, width=8).grid(row=0, column=13, padx=3)

        # 提示文字
        ttk.Label(frm, text="Ctrl+點擊 可多選", foreground="#888888").grid(
            row=1, column=9, columnspan=3, sticky=tk.W, pady=(2, 0))

    def _build_main_area(self):
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        left = ttk.LabelFrame(paned, text="服務清單", padding=4)
        paned.add(left, weight=1)
        self._build_service_table(left)

        right = ttk.LabelFrame(paned,
            text="漏 cherry-pick 的 Commit（存在於 release tag / release branch，但不在 main）", padding=4)
        paned.add(right, weight=4)
        self._build_result_table(right)

    def _build_service_table(self, parent):
        cols = ["check", "name", "status"]
        self.svc_tree = ttk.Treeview(parent, columns=cols, show="headings", height=20)
        self.svc_tree.heading("check",  text="✓")
        self.svc_tree.heading("name",   text="服務名稱")
        self.svc_tree.heading("status", text="狀態")
        self.svc_tree.column("check",  width=30,  anchor=tk.CENTER)
        self.svc_tree.column("name",   width=180, anchor=tk.W)
        self.svc_tree.column("status", width=80,  anchor=tk.CENTER)

        vsb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.svc_tree.yview)
        self.svc_tree.configure(yscrollcommand=vsb.set)
        self.svc_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.svc_tree.bind("<ButtonRelease-1>", self._on_svc_click)
        self.svc_tree.tag_configure("ok",       background="#e0ffe0")
        self.svc_tree.tag_configure("notfound", background="#fff3cd")
        self.svc_tree.tag_configure("scanning", background="#e0f0ff")

        btn_frm = ttk.Frame(parent)
        btn_frm.pack(fill=tk.X, pady=2)
        ttk.Button(btn_frm, text="全選",   command=lambda: self._toggle_all(True),  width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frm, text="全不選", command=lambda: self._toggle_all(False), width=8).pack(side=tk.LEFT, padx=2)

    def _build_result_table(self, parent):
        cols  = [COL_SVC, COL_HASH, COL_AUTHOR, COL_DATE, COL_MSG, COL_REFS, COL_STATUS]
        hdrs  = {
            COL_SVC:    "服務",
            COL_HASH:   "Commit Hash",
            COL_AUTHOR: "作者",
            COL_DATE:   "日期",
            COL_MSG:    "Commit Message",
            COL_REFS:   "存在於 (branch/tag)",
            COL_STATUS: "Cherry-pick",
        }
        widths = {
            COL_SVC:    115, COL_HASH:  88, COL_AUTHOR:  75,
            COL_DATE:   128, COL_MSG:  360, COL_REFS:   200,
            COL_STATUS:  90,
        }

        frm = ttk.Frame(parent)
        frm.pack(fill=tk.BOTH, expand=True)

        # ★ selectmode=extended 支援多選
        self.res_tree = ttk.Treeview(frm, columns=cols, show="headings", selectmode="extended")
        for c in cols:
            self.res_tree.heading(c, text=hdrs[c], command=lambda _c=c: self._sort_results(_c))
            anch = tk.CENTER if c in (COL_HASH, COL_DATE, COL_STATUS) else tk.W
            self.res_tree.column(c, width=widths[c], anchor=anch)

        vsb = ttk.Scrollbar(frm, orient=tk.VERTICAL,   command=self.res_tree.yview)
        hsb = ttk.Scrollbar(frm, orient=tk.HORIZONTAL, command=self.res_tree.xview)
        self.res_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.res_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frm.rowconfigure(0, weight=1)
        frm.columnconfigure(0, weight=1)

        self.res_tree.tag_configure("odd",      background="#f9f9f9")
        self.res_tree.tag_configure("even",     background="#ffffff")
        self.res_tree.tag_configure("cp_ok",    background="#d4edda")  # 派彩成功 綠
        self.res_tree.tag_configure("cp_err",   background="#f8d7da")  # 失敗 紅
        self.res_tree.tag_configure("cp_skip",  background="#fff3cd")  # 跳過 黃

        # ── 右鍵選單 ──
        self._ctx_menu = tk.Menu(self, tearoff=0)
        self._ctx_menu.add_command(label="🍒 Cherry-pick 此 commit",    command=self._on_cherry_pick_selected)
        self._ctx_menu.add_command(label="🍒 Cherry-pick 已選取全部",   command=self._on_cherry_pick_selected)
        self._ctx_menu.add_separator()
        self._ctx_menu.add_command(label="複製 Commit Hash",            command=self._copy_hash)
        self._ctx_menu.add_command(label="複製整行",                     command=self._copy_row)
        self.res_tree.bind("<Button-3>", self._on_right_click)

        # 狀態列
        self.lbl_count = ttk.Label(parent, text="共 0 筆", anchor=tk.W)
        self.lbl_count.pack(fill=tk.X, padx=2)

    def _build_log(self):
        frm = ttk.LabelFrame(self, text="Log", padding=4)
        frm.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.log_text = tk.Text(
            frm, height=6, state=tk.DISABLED,
            bg="#1e1e1e", fg="#d4d4d4",
            font=("Consolas", 9), wrap=tk.WORD)
        sb = ttk.Scrollbar(frm, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    # ── Log ───────────────────────────────────
    def log(self, msg: str, color: str = "#d4d4d4"):
        def _do():
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.tag_configure(color, foreground=color)
            ts = datetime.now().strftime("%H:%M:%S")
            self.log_text.insert(tk.END, f"[{ts}] {msg}\n", color)
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
        self.after(0, _do)

    def log_ok(self,   m): self.log(f"[OK]  {m}", "#4ec94e")
    def log_err(self,  m): self.log(f"[ERR] {m}", "#f44747")
    def log_inf(self,  m): self.log(f"[--]  {m}", "#9cdcfe")
    def log_warn(self, m): self.log(f"[!]   {m}", "#ffcc00")

    # ── Service table helpers ─────────────────
    def _refresh_service_table(self):
        root = self.var_root.get().strip() if hasattr(self, "var_root") else DEFAULT_ROOT
        self._services = [
            ServiceRow(name, os.path.join(root, name))
            for name in discover_services(root)
        ]
        self.svc_tree.delete(*self.svc_tree.get_children())
        for s in self._services:
            tag = "ok" if s.status == "Ready" else "notfound"
            self.svc_tree.insert("", tk.END, iid=s.name, values=(
                "☑" if s.checked else "☐", s.name, s.status
            ), tags=(tag,))
        self.log_inf(f"掃描到 {len(self._services)} 個服務")

    def _update_svc_row(self, s: ServiceRow, tag: str = None):
        t = tag or ("ok" if s.status == "Ready" else "scanning")
        self.svc_tree.item(s.name, values=(
            "☑" if s.checked else "☐", s.name, s.status
        ), tags=(t,))

    def _on_svc_click(self, event):
        col = self.svc_tree.identify("column", event.x, event.y)
        if col != "#1":
            return
        iid = self.svc_tree.identify_row(event.y)
        if not iid:
            return
        s = next((x for x in self._services if x.name == iid), None)
        if s:
            s.checked = not s.checked
            self._update_svc_row(s)

    def _toggle_all(self, state: bool):
        for s in self._services:
            s.checked = state
            self._update_svc_row(s)

    # ── Result table helpers ──────────────────
    def _svc_path(self, svc_name: str) -> str:
        s = next((x for x in self._services if x.name == svc_name), None)
        return s.path if s else ""

    def _populate_results(self, rows: list[dict]):
        self._results = rows
        self.res_tree.delete(*self.res_tree.get_children())
        for i, r in enumerate(rows):
            base_tag = "odd" if i % 2 else "even"
            cp_tag   = {"✅ Done": "cp_ok", "❌ Conflict": "cp_err",
                        "⏭ Skip": "cp_skip"}.get(r.get("cp_status", ""), base_tag)
            self.res_tree.insert("", tk.END, iid=str(i), values=(
                r["service"], r["short_hash"], r["author"],
                r["date"], r["message"], r["refs"], r.get("cp_status", ""),
            ), tags=(cp_tag,))
        self.lbl_count.config(text=f"共 {len(rows)} 筆漏撿 commit")

    def _refresh_row(self, idx: int):
        r = self._results[idx]
        cp_tag = {"✅ Done": "cp_ok", "❌ Conflict": "cp_err",
                  "⏭ Skip": "cp_skip"}.get(r.get("cp_status", ""), "even")
        self.res_tree.item(str(idx), values=(
            r["service"], r["short_hash"], r["author"],
            r["date"], r["message"], r["refs"], r.get("cp_status", ""),
        ), tags=(cp_tag,))

    def _sort_results(self, col: str):
        key_map = {COL_SVC: "service", COL_HASH: "short_hash", COL_AUTHOR: "author",
                   COL_DATE: "date",   COL_MSG: "message",     COL_REFS: "refs"}
        k = key_map.get(col, col)
        self._results.sort(key=lambda r: r.get(k, ""))
        self._populate_results(self._results)

    def _selected_result_items(self) -> list[dict]:
        """取得 res_tree 目前選取列對應的 result dict 清單"""
        sel = self.res_tree.selection()
        items = []
        for iid in sel:
            try:
                items.append(self._results[int(iid)])
            except (ValueError, IndexError):
                pass
        return items

    # ── Context menu ──────────────────────────
    def _on_right_click(self, event):
        iid = self.res_tree.identify_row(event.y)
        if not iid:
            return
        # 如果點到的列不在已選取範圍內，就重設選取
        if iid not in self.res_tree.selection():
            self.res_tree.selection_set(iid)
        sel_count = len(self.res_tree.selection())
        self._ctx_menu.entryconfig(0, label=f"🍒 Cherry-pick 此 commit")
        self._ctx_menu.entryconfig(1, label=f"🍒 Cherry-pick 已選取 {sel_count} 筆")
        self._ctx_menu.post(event.x_root, event.y_root)

    def _copy_hash(self):
        sel = self.res_tree.selection()
        if not sel:
            return
        vals = self.res_tree.item(sel[0], "values")
        try:
            full = self._results[int(sel[0])]["hash"]
        except Exception:
            full = vals[1]
        self.clipboard_clear()
        self.clipboard_append(full)
        self.log_inf(f"已複製 hash: {full}")

    def _copy_row(self):
        sel = self.res_tree.selection()
        if not sel:
            return
        lines = []
        for iid in sel:
            vals = self.res_tree.item(iid, "values")
            lines.append("\t".join(str(v) for v in vals))
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))

    # ── Browse ────────────────────────────────
    def _browse_root(self):
        d = filedialog.askdirectory(title="選擇本地根目錄", initialdir=self.var_root.get())
        if d:
            self.var_root.set(os.path.normpath(d))
            self._on_rescan()

    # ── Scan actions ──────────────────────────
    def _on_rescan(self):
        self._refresh_service_table()

    def _on_clear_results(self):
        self._results = []
        self.res_tree.delete(*self.res_tree.get_children())
        self.lbl_count.config(text="共 0 筆")

    def _validate_inputs(self) -> bool:
        if not self.var_author.get().strip() and not self.var_from.get().strip():
            messagebox.showwarning("提示", "請至少填入「作者」或「日期起」")
            return False
        if not any(s.checked for s in self._services):
            messagebox.showwarning("提示", "請至少勾選一個服務")
            return False
        return True

    def _on_fetch_and_scan(self):
        if not self._validate_inputs():
            return
        self._save_config()
        targets = [s for s in self._services if s.checked and s.status != "Not Found"]

        def worker():
            self.after(0, lambda: self.log_inf(f"── 開始 Fetch {len(targets)} 個服務 ──"))
            self.after(0, self._on_clear_results)

            def fetch_one(s: ServiceRow):
                s.status = "Fetching..."
                self.after(0, lambda _s=s: self._update_svc_row(_s, "scanning"))
                ok, _, err = fetch_repo(s.path)
                s.status = "Ready" if ok else "Fetch Error"
                self.after(0, lambda _s=s: self._update_svc_row(_s))
                if not ok:
                    self.after(0, lambda _s=s, e=err: self.log_err(f"{_s.name}: fetch 失敗 - {e}"))

            with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
                list(pool.map(fetch_one, targets))

            self.after(0, lambda: self.log_inf("Fetch 完成，開始掃描..."))
            self._do_scan(targets)

        threading.Thread(target=worker, daemon=True).start()

    def _on_quick_scan(self):
        if not self._validate_inputs():
            return
        self._save_config()
        targets = [s for s in self._services if s.checked and s.status != "Not Found"]
        self.after(0, self._on_clear_results)
        threading.Thread(target=self._do_scan, args=(targets,), daemon=True).start()

    def _do_scan(self, targets: list[ServiceRow]):
        author    = self.var_author.get().strip()
        date_from = self.var_from.get().strip()
        date_to   = self.var_to.get().strip()
        main_br   = self.var_main.get().strip() or DEFAULT_MAIN

        self.after(0, lambda: self.log_inf(
            f"掃描 → 作者:{author or '(全部)'} 從:{date_from or '(不限)'} "
            f"到:{date_to or '(不限)'} main:{main_br}"))

        all_results = []
        for idx, s in enumerate(targets, 1):
            s.status = "Scanning..."
            self.after(0, lambda _s=s: self._update_svc_row(_s, "scanning"))
            self.after(0, lambda i=idx, t=len(targets), n=s.name:
                       self.log_inf(f"[{i}/{t}] {n}..."))

            commits = get_missing_commits(s.path, author, date_from, date_to, main_br)
            for c in commits:
                c["service"] = s.name
            all_results.extend(commits)

            count = len(commits)
            s.status = f"⚠ {count} 筆" if count else "✓ 無漏"
            self.after(0, lambda _s=s, cnt=count: (
                self._update_svc_row(_s),
                self.log_warn(f"{_s.name}: {cnt} 筆漏撿") if cnt
                else self.log_ok(f"{_s.name}: 無遺漏")
            ))

        self.after(0, lambda: self._populate_results(all_results))
        self.after(0, lambda: self.log_inf(
            f"掃描完成 ─ 共 {len(all_results)} 筆（{len(targets)} 個服務）"))

    # ── Cherry-pick actions ───────────────────
    def _on_cherry_pick_selected(self):
        items = self._selected_result_items()
        if not items:
            messagebox.showwarning("提示", "請先在右側結果表格選取至少一筆 commit\n（可用 Ctrl+點擊 多選）")
            return
        self._launch_cherry_pick(items)

    def _on_cherry_pick_all(self):
        if not self._results:
            messagebox.showwarning("提示", "沒有結果，請先掃描")
            return
        self._launch_cherry_pick(list(self._results))

    def _launch_cherry_pick(self, items: list[dict]):
        # 過濾掉已 Done 的
        pending = [r for r in items if r.get("cp_status") != "✅ Done"]
        if not pending:
            messagebox.showinfo("提示", "選取的 commit 都已 cherry-pick 完成")
            return

        svc_paths = {s.name: s.path for s in self._services}
        dlg = CherryPickDialog(self, pending, svc_paths)
        self.wait_window(dlg)

        if not dlg.confirmed:
            self.log_inf("使用者取消 cherry-pick")
            return

        # 依 service 分組，依日期由舊到新執行
        sorted_items = dlg.sorted_items
        threading.Thread(
            target=self._do_cherry_pick,
            args=(sorted_items, svc_paths),
            daemon=True
        ).start()

    def _do_cherry_pick(self, items: list[dict], svc_paths: dict[str, str]):
        self.after(0, lambda: self.log_inf(f"── 開始 cherry-pick {len(items)} 筆 ──"))

        success = fail = skip = 0

        for r in items:
            svc  = r["service"]
            path = svc_paths.get(svc, "")
            h    = r["hash"]
            sh   = r["short_hash"]
            msg  = r["message"]

            if not path or not is_valid_repo(path):
                r["cp_status"] = "⏭ Skip"
                skip += 1
                self.after(0, lambda _r=r: self._refresh_row_by_hash(_r))
                self.after(0, lambda s=svc, _h=sh: self.log_warn(f"{s} [{_h}]: 路徑無效，跳過"))
                continue

            self.after(0, lambda s=svc, _h=sh, m=msg:
                       self.log_inf(f"{s} [{_h}] cherry-pick: {m[:60]}"))

            ok, out, err = cherry_pick(path, h)

            if ok:
                r["cp_status"] = "✅ Done"
                success += 1
                self.after(0, lambda _r=r: self._refresh_row_by_hash(_r))
                self.after(0, lambda s=svc, _h=sh: self.log_ok(f"{s} [{_h}]: cherry-pick 成功"))
            else:
                r["cp_status"] = "❌ Conflict"
                fail += 1
                self.after(0, lambda _r=r: self._refresh_row_by_hash(_r))
                err_msg = (err or out)[:200]
                self.after(0, lambda s=svc, _h=sh, e=err_msg:
                           self.log_err(f"{s} [{_h}]: 失敗 → {e}"))
                # 自動 abort 避免 repo 卡住
                cherry_pick_abort(path)
                self.after(0, lambda s=svc: self.log_warn(f"{s}: 已執行 cherry-pick --abort，請手動處理衝突"))
                # 同一個 service 後續的跳過，避免更多衝突
                for remaining in items:
                    if remaining["service"] == svc and remaining.get("cp_status", "") == "":
                        remaining["cp_status"] = "⏭ Skip"
                        skip += 1
                        self.after(0, lambda _r=remaining: self._refresh_row_by_hash(_r))

        self.after(0, lambda s=success, f=fail, sk=skip:
                   self.log_inf(f"── Cherry-pick 完成：✅ {s} 筆成功 ❌ {f} 筆衝突 ⏭ {sk} 筆跳過 ──"))

    def _refresh_row_by_hash(self, r: dict):
        """依 result dict 找到對應 iid 並刷新"""
        try:
            idx = self._results.index(r)
            self._refresh_row(idx)
        except ValueError:
            pass

    # ── Copy ──────────────────────────────────
    def _on_copy_results(self):
        if not self._results:
            self.log_warn("沒有結果可複製")
            return
        header = "服務\tHash\t作者\t日期\tMessage\t存在於\tCherry-pick"
        lines  = [header] + [
            f"{r['service']}\t{r['hash']}\t{r['author']}\t"
            f"{r['date']}\t{r['message']}\t{r['refs']}\t{r.get('cp_status','')}"
            for r in self._results
        ]
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        self.log_ok(f"已複製 {len(self._results)} 筆（可直接貼 Excel）")


# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
