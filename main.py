import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import config_manager as cfg
import gitlab_service as gl_svc
import git_service as git_svc
import version_parser as vp

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────
COL_CHECK  = "check"
COL_NAME   = "name"
COL_TAG    = "latest_tag"
COL_PATH   = "local_path"
COL_BRANCH = "new_branch"
COL_STATUS = "status"

STATUS_READY     = "Ready"
STATUS_NOT_FOUND = "Not Found"
STATUS_NO_TAG    = "No Tag"
STATUS_WORKING   = "Working..."
STATUS_DONE      = "Done"
STATUS_ERROR     = "Error"

DEFAULT_URL    = "https://gitlab.service-hub.tech"
DEFAULT_GROUP  = "java-backend"
DEFAULT_FILTER = "tiger"
DEFAULT_ROOT   = r"D:\tigerProject"
FETCH_WORKERS  = 20   # 併發打 GitLab API 數量

EXCLUDED_PROJECTS = {
    "tiger-tools",
    "tiger-value",
    "tiger-values",
    "tiger-wallet",
    "tiger-sqlddl",
    "tiger-sign",
    "tiger-s3-lambda",
    "tiger-registry",
    "tiger-proxy",
    "tiger-project",
    "tiger-oncall-sql",
    "tiger-initial",
    "tiger-blockchain",
    "tiger-actuator",
}


# ─────────────────────────────────────────────
# Model
# ─────────────────────────────────────────────
class ProjectRow:
    def __init__(self, name: str, project_id: int, local_path: str):
        self.name       = name
        self.project_id = project_id
        self.local_path = local_path
        self.latest_tag = ""
        self.new_branch = ""
        self.status     = STATUS_NOT_FOUND
        self.checked    = True

    def refresh_status(self):
        git = git_svc.GitService(self.local_path)
        if not git.exists():
            self.status = STATUS_NOT_FOUND
        elif not git.is_valid_repo():
            self.status = "Not a Repo"
        elif not self.latest_tag:
            self.status = STATUS_NO_TAG
        else:
            self.status = STATUS_READY


# ─────────────────────────────────────────────
# Main Application
# ─────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tiger Release Branch Helper")
        self.geometry("1200x750")
        self.minsize(960, 600)

        self.projects: list[ProjectRow] = []
        self._custom_paths: dict[str, str] = {}   # name -> 自訂路徑

        self._load_config()
        self._build_ui()
        self._apply_config_to_ui()

    # ── Config ────────────────────────────────
    def _load_config(self):
        self._config = cfg.load_config()
        self._custom_paths = self._config.get("custom_paths", {})

    def _save_config(self):
        self._config["gitlab_url"]    = self.var_url.get().strip()
        self._config["group"]         = self.var_group.get().strip()
        self._config["filter"]        = self.var_filter.get().strip()
        self._config["local_root"]    = self.var_root.get().strip()
        self._config["custom_paths"]  = self._custom_paths
        token = self.var_token.get().strip()
        if token:
            self._config["token_enc"] = cfg.encrypt_token(token)
        cfg.save_config(self._config)
        self.log_inf("設定已儲存")

    def _apply_config_to_ui(self):
        self.var_url.set(   self._config.get("gitlab_url", DEFAULT_URL))
        self.var_group.set( self._config.get("group",      DEFAULT_GROUP))
        self.var_filter.set(self._config.get("filter",     DEFAULT_FILTER))
        self.var_root.set(  self._config.get("local_root", DEFAULT_ROOT))
        self.var_token.set( cfg.decrypt_token(self._config.get("token_enc", "")))

    def _resolve_path(self, project_name: str) -> str:
        """優先用自訂路徑，否則 root + name"""
        if project_name in self._custom_paths:
            return self._custom_paths[project_name]
        return os.path.join(self.var_root.get().strip(), project_name)

    # ── UI Build ──────────────────────────────
    def _build_ui(self):
        self._build_settings_frame()
        self._build_toolbar()
        self._build_table()
        self._build_log()

    def _build_settings_frame(self):
        frm = ttk.LabelFrame(self, text="GitLab 設定", padding=6)
        frm.pack(fill=tk.X, padx=8, pady=(8, 0))

        self.var_url    = tk.StringVar()
        self.var_token  = tk.StringVar()
        self.var_group  = tk.StringVar()
        self.var_filter = tk.StringVar()
        self.var_root   = tk.StringVar()
        self.var_branch = tk.StringVar()

        fields = [
            ("GitLab URL",   self.var_url,    False, 30),
            ("Access Token", self.var_token,  True,  28),
            ("Group",        self.var_group,  False, 16),
            ("Filter",       self.var_filter, False, 10),
            ("本地根目錄",    self.var_root,   False, 20),
            ("目標 Branch",  self.var_branch, False, 16),
        ]

        for col, (label, var, is_pw, w) in enumerate(fields):
            ttk.Label(frm, text=label + ":").grid(row=0, column=col * 2, sticky=tk.E, padx=(6, 2))
            show = "*" if is_pw else ""
            ttk.Entry(frm, textvariable=var, show=show, width=w).grid(
                row=0, column=col * 2 + 1, sticky=tk.W, padx=(0, 6))

        ttk.Button(frm, text="儲存設定", command=self._save_config).grid(
            row=0, column=len(fields) * 2, padx=4)

    def _build_toolbar(self):
        bar = ttk.Frame(self, padding=(8, 4))
        bar.pack(fill=tk.X)

        buttons = [
            ("重新載入專案",      self._on_reload),
            ("取得最新 Tags",     self._on_fetch_tags),
            ("自動帶出 Branch",   self._on_auto_branch),
            ("單筆切 Branch",     self._on_single_branch),
            ("批次一鍵切 Branch", self._on_batch_branch),
            ("全選 / 全不選",     self._on_toggle_all),
            ("同步 GAME",         self._on_sync_game),
            ("同步 COMMON",       self._on_sync_common),
        ]
        for text, cmd in buttons:
            ttk.Button(bar, text=text, command=cmd, width=16).pack(side=tk.LEFT, padx=3)

    def _build_table(self):
        frm = ttk.Frame(self)
        frm.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        cols    = [COL_CHECK, COL_NAME, COL_TAG, COL_PATH, COL_BRANCH, COL_STATUS]
        headers = {
            COL_CHECK:  "✓",
            COL_NAME:   "專案名稱",
            COL_TAG:    "最新 Tag",
            COL_PATH:   "本地路徑（雙擊可修改）",
            COL_BRANCH: "目標 Branch",
            COL_STATUS: "狀態",
        }
        widths = {
            COL_CHECK: 30, COL_NAME: 190, COL_TAG: 130,
            COL_PATH: 280, COL_BRANCH: 140, COL_STATUS: 100,
        }

        self.tree = ttk.Treeview(frm, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            self.tree.heading(c, text=headers[c])
            anchor = tk.CENTER if c in (COL_CHECK, COL_STATUS) else tk.W
            self.tree.column(c, width=widths[c], anchor=anchor)

        vsb = ttk.Scrollbar(frm, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<ButtonRelease-1>",  self._on_row_click)
        self.tree.bind("<Double-Button-1>",  self._on_row_double_click)

        self.tree.tag_configure("error",  background="#ffe0e0")
        self.tree.tag_configure("ready",  background="#e0ffe0")
        self.tree.tag_configure("nopath", background="#fff3cd")

    def _build_log(self):
        frm = ttk.LabelFrame(self, text="Log", padding=4)
        frm.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.log_text = tk.Text(
            frm, height=8, state=tk.DISABLED,
            bg="#1e1e1e", fg="#d4d4d4",
            font=("Consolas", 9), wrap=tk.WORD)
        sb = ttk.Scrollbar(frm, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    # ── Log ───────────────────────────────────
    def log(self, msg: str, color: str = "white"):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.tag_configure(color, foreground=color)
        self.log_text.insert(tk.END, msg + "\n", color)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def log_ok(self, msg):  self.log(f"[OK]  {msg}", "#4ec94e")
    def log_err(self, msg): self.log(f"[ERR] {msg}", "#f44747")
    def log_inf(self, msg): self.log(f"[--]  {msg}", "#9cdcfe")

    # ── Table helpers ─────────────────────────
    def _row_tag(self, p: ProjectRow) -> str:
        return {
            STATUS_READY:     "ready",
            STATUS_NOT_FOUND: "nopath",
            STATUS_ERROR:     "error",
        }.get(p.status, "")

    def _refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        for p in self.projects:
            self.tree.insert("", tk.END, iid=p.name, values=(
                "☑" if p.checked else "☐",
                p.name,
                p.latest_tag or "-",
                p.local_path,
                p.new_branch or "-",
                p.status,
            ), tags=(self._row_tag(p),))

    def _update_row(self, p: ProjectRow):
        self.tree.item(p.name, values=(
            "☑" if p.checked else "☐",
            p.name,
            p.latest_tag or "-",
            p.local_path,
            p.new_branch or "-",
            p.status,
        ), tags=(self._row_tag(p),))

    # ── Click handlers ────────────────────────
    def _on_row_click(self, event):
        """第 1 欄（checkbox）單擊切換勾選"""
        col = self.tree.identify("column", event.x, event.y)
        if col != "#1":
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        proj = next((p for p in self.projects if p.name == iid), None)
        if proj:
            proj.checked = not proj.checked
            self._update_row(proj)

    def _on_row_double_click(self, event):
        """雙擊任意欄 → 開資料夾選擇器修改本地路徑"""
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        proj = next((p for p in self.projects if p.name == iid), None)
        if not proj:
            return

        init_dir = proj.local_path if os.path.isdir(proj.local_path) else os.path.expanduser("~")
        chosen = filedialog.askdirectory(
            title=f"選擇 {proj.name} 的本地資料夾",
            initialdir=init_dir,
        )
        if not chosen:
            return

        chosen = os.path.normpath(chosen)
        proj.local_path = chosen
        self._custom_paths[proj.name] = chosen
        proj.refresh_status()
        self._update_row(proj)
        self._save_config()
        self.log_inf(f"{proj.name}: 本地路徑設為 {chosen}  →  {proj.status}")

    def _on_toggle_all(self):
        target = not all(p.checked for p in self.projects)
        for p in self.projects:
            p.checked = target
        self._refresh_table()

    # ── Pom helpers ───────────────────────────
    def _parse_pom_version(self, pom_path: str, tag: str) -> str | None:
        """從 pom.xml 讀取 <tag>v?x.y.z</tag>，回傳不含 v 的版本字串"""
        try:
            with open(pom_path, encoding="utf-8") as f:
                content = f.read()
            m = re.search(rf'<{re.escape(tag)}>v?(\d+\.\d+\.\d+)</{re.escape(tag)}>', content)
            return m.group(1) if m else None
        except Exception:
            return None

    def _update_pom_version(self, pom_path: str, tag: str, new_ver: str) -> bool:
        """將 pom.xml 內 <tag> 的版本改為 v{new_ver}，回傳是否有實際變更"""
        try:
            with open(pom_path, encoding="utf-8") as f:
                content = f.read()
            new_content = re.sub(
                rf'<{re.escape(tag)}>v?\d+\.\d+\.\d+</{re.escape(tag)}>',
                f'<{tag}>v{new_ver}</{tag}>',
                content,
            )
            if new_content == content:
                return False
            with open(pom_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return True
        except Exception:
            return False

    @staticmethod
    def _ver_tuple(ver: str) -> tuple:
        return tuple(int(x) for x in ver.strip().lstrip("v").split("."))

    # ── Sync GAME / COMMON ────────────────────
    def _get_lib_version(self, lib_name: str, svc) -> str | None:
        """
        取得 lib_name 應使用的版本（不含 v 前綴）：
        - 本地 branch 以 release 開頭 → 從 branch 名稱解析版本號
        - 否則 → 從 GitLab 取最新 release tag
        """
        lib_path = self._resolve_path(lib_name)
        git = git_svc.GitService(lib_path)
        if git.is_valid_repo():
            branch = git.current_branch()
            m = re.match(r'^release[/\-](\d+\.\d+\.\d+)$', branch)
            if m:
                ver = m.group(1)
                self.after(0, lambda n=lib_name, b=branch, v=ver: self.log_inf(
                    f"{n}: 本地 branch={b}，使用版本 v{v}"))
                return ver

        # 本地不在 release branch，改用線上最新 tag
        pid = next((p.project_id for p in self.projects if p.name == lib_name), None)
        if pid is None:
            try:
                pid = svc.find_project_id_by_name(lib_name)
            except Exception:
                pass
        if pid:
            try:
                tags   = svc.get_tags(pid)
                latest = vp.get_latest_tag(tags)
                if latest:
                    m = re.match(r'^release-(\d+\.\d+\.\d+)$', latest)
                    if m:
                        ver = m.group(1)
                        self.after(0, lambda n=lib_name, t=latest, v=ver: self.log_inf(
                            f"{n}: 線上最新 tag={t}，使用版本 v{v}"))
                        return ver
            except Exception as e:
                self.after(0, lambda n=lib_name, ex=e: self.log_err(
                    f"{n}: 取線上 tag 失敗: {ex}"))
        return None

    def _on_sync_game(self):
        """同步 tiger-game 版本，僅對 tiger-thirdparty / tiger-thirdparty-payment 有效"""
        game_projects = {"tiger-thirdparty", "tiger-thirdparty-payment"}
        targets = [p for p in self.projects if p.checked and p.name in game_projects]
        if not targets:
            messagebox.showinfo("提示", "請勾選 tiger-thirdparty 或 tiger-thirdparty-payment")
            return
        svc = self._make_gitlab()
        if not svc:
            return

        def worker():
            self.after(0, lambda: self.log_inf("── 開始同步 tiger-game 版本 ──"))
            ver = self._get_lib_version("tiger-game", svc)
            if not ver:
                self.after(0, lambda: self.log_err("tiger-game: 無法取得版本資訊，中止"))
                return
            self.after(0, lambda v=ver: self.log_inf(f"tiger-game: 採用版本 v{v}"))
            for p in targets:
                pom_path = os.path.join(p.local_path, "pom.xml")
                cur_ver  = self._parse_pom_version(pom_path, "tiger.game.version")
                if cur_ver is None:
                    self.after(0, lambda pn=p.name: self.log_err(
                        f"{pn}: pom.xml 找不到 <tiger.game.version>，跳過"))
                    continue
                if self._ver_tuple(cur_ver) == self._ver_tuple(ver):
                    self.after(0, lambda pn=p.name, v=cur_ver: self.log_inf(
                        f"{pn}: 已是 v{v}，無需更新"))
                    continue
                changed = self._update_pom_version(pom_path, "tiger.game.version", ver)
                if changed:
                    self.after(0, lambda pn=p.name, ov=cur_ver, nv=ver: self.log_ok(
                        f"{pn}: <tiger.game.version>  v{ov}  →  v{nv}"))
                else:
                    self.after(0, lambda pn=p.name: self.log_err(f"{pn}: 更新 pom.xml 失敗"))
            self.after(0, lambda: self.log_inf("同步 GAME 完成"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_sync_common(self):
        """同步 tiger-common 版本，對所有已勾選專案有效"""
        targets = [p for p in self.projects if p.checked]
        if not targets:
            messagebox.showinfo("提示", "請勾選至少一個專案")
            return
        svc = self._make_gitlab()
        if not svc:
            return

        def worker():
            self.after(0, lambda: self.log_inf("── 開始同步 tiger-common 版本 ──"))
            ver = self._get_lib_version("tiger-common", svc)
            if not ver:
                self.after(0, lambda: self.log_err("tiger-common: 無法取得版本資訊，中止"))
                return
            self.after(0, lambda v=ver: self.log_inf(f"tiger-common: 採用版本 v{v}"))
            for p in targets:
                pom_path = os.path.join(p.local_path, "pom.xml")
                cur_ver  = self._parse_pom_version(pom_path, "tiger.common.version")
                if cur_ver is None:
                    self.after(0, lambda pn=p.name: self.log_err(
                        f"{pn}: pom.xml 找不到 <tiger.common.version>，跳過"))
                    continue
                if self._ver_tuple(cur_ver) == self._ver_tuple(ver):
                    self.after(0, lambda pn=p.name, v=cur_ver: self.log_inf(
                        f"{pn}: 已是 v{v}，無需更新"))
                    continue
                changed = self._update_pom_version(pom_path, "tiger.common.version", ver)
                if changed:
                    self.after(0, lambda pn=p.name, ov=cur_ver, nv=ver: self.log_ok(
                        f"{pn}: <tiger.common.version>  v{ov}  →  v{nv}"))
                else:
                    self.after(0, lambda pn=p.name: self.log_err(f"{pn}: 更新 pom.xml 失敗"))
            self.after(0, lambda: self.log_inf("同步 COMMON 完成"))

        threading.Thread(target=worker, daemon=True).start()

    # ── GitLab helper ─────────────────────────
    def _make_gitlab(self) -> gl_svc.GitLabService | None:
        url   = self.var_url.get().strip()
        token = self.var_token.get().strip()
        group = self.var_group.get().strip()
        kw    = self.var_filter.get().strip() or DEFAULT_FILTER
        if not url or not token or not group:
            messagebox.showerror("缺少設定", "請填入 GitLab URL、Token、Group")
            return None
        return gl_svc.GitLabService(url, token, group, kw)

    # ── Actions ───────────────────────────────
    def _on_reload(self):
        svc = self._make_gitlab()
        if not svc:
            return
        self._save_config()
        self.log_inf("載入專案清單...")

        def worker():
            try:
                raw  = svc.get_projects()
                rows = []
                for p in raw:
                    name = p['name']
                    if name in EXCLUDED_PROJECTS:
                        continue
                    path = self._resolve_path(name)
                    row  = ProjectRow(name, p['id'], path)
                    row.refresh_status()
                    rows.append(row)
                self.projects = rows
                self.after(0, self._refresh_table)
                self.after(0, lambda: self.log_ok(f"載入完成，共 {len(rows)} 個專案"))
            except Exception as e:
                self.after(0, lambda: self.log_err(f"GitLab 連線失敗: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_fetch_tags(self):
        svc = self._make_gitlab()
        if not svc:
            return
        if not self.projects:
            self.log_err("請先載入專案清單")
            return
        self.log_inf(f"併發取得 Tags（{len(self.projects)} 個，最多 {FETCH_WORKERS} 併發）...")

        def fetch_one(p: ProjectRow):
            try:
                tags   = svc.get_tags(p.project_id)
                latest = vp.get_latest_tag(tags)
                if latest:
                    p.latest_tag = latest
                    p.new_branch = vp.suggest_next_branch(latest) or ""
                    self.after(0, lambda pr=p: self.log_ok(f"{pr.name}: {pr.latest_tag}"))
                else:
                    p.latest_tag = ""
                    self.after(0, lambda pr=p: self.log_err(f"{pr.name}: 無符合 release-*.*.* 格式之 tag"))
                p.refresh_status()
                self.after(0, lambda pr=p: self._update_row(pr))
            except Exception as e:
                self.after(0, lambda pr=p, ex=e: self.log_err(f"{pr.name}: {ex}"))

        def worker():
            with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
                futures = {pool.submit(fetch_one, p): p for p in self.projects}
                for _ in as_completed(futures):
                    pass
            self.after(0, lambda: self.log_inf("Tags 取得完成"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_auto_branch(self):
        branch = self.var_branch.get().strip()
        if not branch:
            for p in self.projects:
                if p.latest_tag:
                    p.new_branch = vp.suggest_next_branch(p.latest_tag) or ""
            self.log_inf("已自動帶出建議 Branch 名稱")
        else:
            if not vp.validate_branch_name(branch):
                messagebox.showerror("格式錯誤", "Branch 格式必須為 release/x.y.z")
                return
            for p in self.projects:
                p.new_branch = branch
            self.log_inf(f"已套用 Branch 名稱: {branch}")
        self._refresh_table()

    def _on_single_branch(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "請先點選一個專案")
            return
        proj = next((p for p in self.projects if p.name == sel[0]), None)
        if proj:
            self._do_create_branch([proj])

    def _on_batch_branch(self):
        targets = [p for p in self.projects if p.checked]
        if not targets:
            messagebox.showinfo("提示", "請勾選至少一個專案")
            return
        names = "\n".join(f"  {p.name}  →  {p.new_branch}" for p in targets)
        if not messagebox.askyesno("確認執行", f"即將對以下專案建立 Branch：\n\n{names}\n\n確定執行？"):
            return
        self._do_create_branch(targets)

    def _do_create_branch(self, targets: list):
        svc = self._make_gitlab()
        if not svc:
            return
        invalid = [p for p in targets if not p.new_branch or not vp.validate_branch_name(p.new_branch)]
        if invalid:
            messagebox.showerror("格式錯誤",
                "以下專案 Branch 名稱無效：\n" + "\n".join(p.name for p in invalid))
            return

        def worker():
            for p in targets:
                p.status = STATUS_WORKING
                self.after(0, lambda pr=p: self._update_row(pr))
                self.after(0, lambda pr=p: self.log_inf(f"{pr.name}: 開始建立 {pr.new_branch}"))

                # 1. 檢查遠端 branch 是否已存在
                try:
                    if svc.branch_exists(p.project_id, p.new_branch):
                        p.status = STATUS_ERROR
                        self.after(0, lambda pr=p: self._update_row(pr))
                        self.after(0, lambda pr=p: self.log_err(
                            f"{pr.name}: 遠端 branch 已存在，不可重複建立"))
                        continue
                except Exception as e:
                    p.status = STATUS_ERROR
                    self.after(0, lambda pr=p: self._update_row(pr))
                    self.after(0, lambda pr=p, ex=e: self.log_err(f"{pr.name}: 檢查 branch 失敗: {ex}"))
                    continue

                git = git_svc.GitService(p.local_path)

                # 2. 本地不存在 → 改用 GitLab API 建立
                if not git.exists():
                    self.after(0, lambda pr=p: self.log_inf(
                        f"{pr.name}: 本地路徑不存在，改用 GitLab API 建立"))
                    try:
                        svc.create_branch(p.project_id, p.new_branch, p.latest_tag)
                        p.status = STATUS_DONE
                        self.after(0, lambda pr=p: self._update_row(pr))
                        self.after(0, lambda pr=p: self.log_ok(
                            f"{pr.name}: branch {pr.new_branch} 建立成功 (via API)"))
                    except Exception as e:
                        p.status = STATUS_ERROR
                        self.after(0, lambda pr=p: self._update_row(pr))
                        self.after(0, lambda pr=p, ex=e: self.log_err(f"{pr.name}: API 建立失敗: {ex}"))
                    continue

                if not git.is_valid_repo():
                    p.status = STATUS_ERROR
                    self.after(0, lambda pr=p: self._update_row(pr))
                    self.after(0, lambda pr=p: self.log_err(f"{pr.name}: 本地路徑不是有效的 git repo"))
                    continue

                # 3. 本地 git 操作
                steps = [
                    (git.fetch_all_tags,
                     f"{p.name}: fetch tags"),
                    (lambda pr=p: git.create_branch_from_tag(pr.new_branch, pr.latest_tag),
                     f"{p.name}: checkout -b {p.new_branch} tags/{p.latest_tag}"),
                    (lambda pr=p: git.update_version_properties(pr.new_branch),
                     f"{p.name}: 更新 version.properties"),
                ]
                success = True
                for fn, desc in steps:
                    ok, out = fn()
                    if ok:
                        self.after(0, lambda d=desc, o=out: self.log_ok(f"{d}" + (f"  →  {o}" if o else "")))
                    else:
                        self.after(0, lambda d=desc, o=out: self.log_err(f"{d} 失敗: {o}"))
                        success = False
                        break

                p.status = STATUS_DONE if success else STATUS_ERROR
                self.after(0, lambda pr=p: self._update_row(pr))

            self.after(0, lambda: self.log_inf("操作完成"))

        threading.Thread(target=worker, daemon=True).start()


# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
