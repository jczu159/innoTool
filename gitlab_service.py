import requests
from typing import List, Dict
from urllib.parse import quote


class GitLabService:
    def __init__(self, base_url: str, token: str, group: str, filter_keyword: str = "tiger"):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.group = group
        self.filter_keyword = filter_keyword
        self.headers = {"PRIVATE-TOKEN": token}

    def get_projects(self) -> List[Dict]:
        projects = []
        page = 1
        while True:
            url = f"{self.base_url}/api/v4/groups/{quote(self.group, safe='')}/projects"
            params = {
                "search": self.filter_keyword,
                "per_page": 100,
                "page": page,
                "order_by": "name",
                "sort": "asc",
                "include_subgroups": True,
            }
            resp = requests.get(url, headers=self.headers, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            filtered = [p for p in data if p['name'].startswith(self.filter_keyword)]
            projects.extend(filtered)
            if len(data) < 100:
                break
            page += 1
        return projects

    def get_tags(self, project_id: int) -> List[str]:
        """回傳所有 tag 名稱清單"""
        tags = []
        page = 1
        while True:
            url = f"{self.base_url}/api/v4/projects/{project_id}/repository/tags"
            params = {"per_page": 100, "page": page}
            resp = requests.get(url, headers=self.headers, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            tags.extend([t['name'] for t in data])
            if len(data) < 100:
                break
            page += 1
        return tags

    def branch_exists(self, project_id: int, branch_name: str) -> bool:
        url = f"{self.base_url}/api/v4/projects/{project_id}/repository/branches/{quote(branch_name, safe='')}"
        resp = requests.get(url, headers=self.headers, timeout=30)
        return resp.status_code == 200

    def create_branch(self, project_id: int, branch_name: str, ref: str) -> Dict:
        url = f"{self.base_url}/api/v4/projects/{project_id}/repository/branches"
        data = {"branch": branch_name, "ref": ref}
        resp = requests.post(url, headers=self.headers, json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()
