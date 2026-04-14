import os
import subprocess
from typing import Tuple


class GitService:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def exists(self) -> bool:
        return os.path.isdir(self.repo_path)

    def is_valid_repo(self) -> bool:
        return self.exists() and os.path.isdir(os.path.join(self.repo_path, '.git'))

    def _run(self, cmd: list) -> Tuple[bool, str]:
        try:
            result = subprocess.run(
                cmd, cwd=self.repo_path,
                capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0:
                return False, (result.stderr or result.stdout).strip()
            return True, result.stdout.strip()
        except subprocess.TimeoutExpired:
            return False, "Git command timed out (120s)"
        except FileNotFoundError:
            return False, "git executable not found in PATH"
        except Exception as e:
            return False, str(e)

    def fetch_all_tags(self) -> Tuple[bool, str]:
        # --force 強制更新本地已有但 SHA 不同的 tag
        # 不用 --all 避免 credential-cache 在 Windows 上的問題
        return self._run(["git", "fetch", "origin", "--tags", "--force", "--prune"])

    def create_branch_from_tag(self, branch_name: str, tag: str) -> Tuple[bool, str]:
        """一步完成：從指定 tag 建立新 branch，不需要先 checkout"""
        return self._run(["git", "checkout", "-b", branch_name, f"tags/{tag}"])

    def push_branch(self, branch_name: str) -> Tuple[bool, str]:
        return self._run(["git", "push", "origin", branch_name])

    def current_branch(self) -> str:
        ok, out = self._run(["git", "branch", "--show-current"])
        return out if ok else "unknown"

    def local_branch_exists(self, branch_name: str) -> bool:
        ok, out = self._run(["git", "branch", "--list", branch_name])
        return ok and bool(out.strip())

    def update_version_properties(self, branch_name: str) -> Tuple[bool, str]:
        """從 release/x.y.z 解析版本號，寫入 version.properties 並 commit"""
        import re
        m = re.match(r'^release/(\d+\.\d+\.\d+)$', branch_name)
        if not m:
            return False, f"無法從 branch 名稱解析版本號: {branch_name}"
        version_str = f"v{m.group(1)}"
        prop_path = os.path.join(self.repo_path, "src", "main", "resources", "version.properties")
        try:
            with open(prop_path, "w", encoding="utf-8") as f:
                f.write(f"version={version_str}\n")
        except Exception as e:
            return False, f"寫入 version.properties 失敗: {e}"
        ok, out = self._run(["git", "add", "src/main/resources/version.properties"])
        if not ok:
            return False, f"git add 失敗: {out}"
        ok, out = self._run(["git", "commit", "-m", f"bump version to {version_str}"])
        if not ok:
            return False, f"git commit 失敗: {out}"
        return True, f"version.properties 已更新為 version={version_str}"
