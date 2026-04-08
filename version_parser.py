import re
from typing import Optional, List, Dict


def parse_release_tag(tag: str) -> Optional[tuple]:
    match = re.match(r'^release-(\d+)\.(\d+)\.(\d+)$', tag)
    if match:
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return None


def get_latest_tag(tags: List[Dict]) -> Optional[str]:
    """
    依語意版號 (X, Y, Z) 數值比較取最新 release tag。
    release-5.39.1 > release-5.37.14 因為 minor 39 > 37。
    同時過濾 major 版號異常偏高的假 tag（如 release-9.9.9）：
    以所有 release tag 的 major 眾數為基準，超過眾數 + 1 的 major 視為異常排除。
    """
    valid = []
    for tag in tags:
        name = tag if isinstance(tag, str) else tag.get("name", "")
        ver = parse_release_tag(name)
        if ver:
            valid.append((name, ver))

    if not valid:
        return None

    # 找 major 眾數
    from collections import Counter
    major_counts = Counter(v[0] for _, v in valid)
    dominant_major = major_counts.most_common(1)[0][0]

    # 只保留 major <= dominant_major + 1 的 tag（排除明顯假 tag）
    filtered = [(name, ver) for name, ver in valid if ver[0] <= dominant_major + 1]

    if not filtered:
        filtered = valid  # fallback

    return max(filtered, key=lambda x: x[1])[0]


def suggest_next_branch(latest_tag: str) -> Optional[str]:
    ver = parse_release_tag(latest_tag)
    if not ver:
        return None
    return f"release/{ver[0]}.{ver[1]}.{ver[2] + 1}"


def validate_branch_name(branch: str) -> bool:
    return bool(re.match(r'^release/\d+\.\d+\.\d+$', branch))
