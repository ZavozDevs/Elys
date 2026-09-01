"""Represents current userbot version"""

# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Hikka Userbot
# 🌐 https://github.com/hikariatama/Hikka
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# ©️ Codrago, 2024-2030
# This file is a part of Elys Userbot
# 🌐 https://github.com/ZavozDevs/Elys
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

__version__ = (0, 1, 1)

import os
import subprocess

NO_GIT = os.environ.get("ELYS_NO_GIT") == "1"


def get_branch() -> str:
    if NO_GIT:
        return os.environ.get("ELYS_BRANCH", "master")

    # 1. Direct .git/HEAD read (fast, zero external dependencies)
    try:
        git_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".git"))
        head_file = os.path.join(git_dir, "HEAD")
        if os.path.isfile(head_file):
            with open(head_file, "r", encoding="utf-8") as f:
                head_content = f.read().strip()
                if head_content.startswith("ref: refs/heads/"):
                    return head_content[len("ref: refs/heads/") :].strip()
    except Exception:
        pass

    # 2. Subprocess git branch --show-current
    try:
        proc = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
            capture_output=True,
            text=True,
            timeout=2,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except Exception:
        pass

    # 3. GitPython fallback
    try:
        import git

        with git.Repo(
            path=os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        ) as repo:
            if not repo.head.is_detached:
                return repo.active_branch.name
            for branch_ref in repo.branches:
                if branch_ref.commit == repo.head.commit:
                    return branch_ref.name
    except Exception:
        pass

    return os.environ.get("ELYS_BRANCH", "master")


class _BranchString(str):
    def __new__(cls):
        val = get_branch()
        return super().__new__(cls, val)

    def __str__(self):
        return get_branch()

    def __repr__(self):
        return repr(get_branch())

    def __eq__(self, other):
        return get_branch() == str(other)

    def __ne__(self, other):
        return get_branch() != str(other)

    def __hash__(self):
        return hash(get_branch())

    def __format__(self, format_spec):
        return format(get_branch(), format_spec)


branch = _BranchString()
