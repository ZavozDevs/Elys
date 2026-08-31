#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Brand Replacer Utility for Talvo (Heroku Userbot fork)
Created for Rooni by Rust.

Allows safely and cleanly replacing branding text across the codebase:
- Updates UI strings, docstrings, comments, translations (langpacks), README, banners, shell scripts
- Strictly preserves imports (herokutl, telethon fork), internal package structures, DB keys and technical constants
- Parameterized: can change to any new name or revert back at any time.

Usage:
    python replace_brand.py --dry-run
    python replace_brand.py
    python replace_brand.py --from-brand Talvo --to-brand OtherBrand
    python replace_brand.py --reverse
"""

import argparse
import io
import os
import re
import sys
import tokenize
from typing import List, Tuple, Dict, Set

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# System keywords/patterns that must NEVER be modified in code/strings to prevent breaking internals
PROTECTED_EXACT_STRINGS: Set[str] = {
    # Imports / libraries
    "herokutl",
    "herokutl.tl",
    "herokutl.network",
    "herokutl.events",
    "herokutl.errors",
    "herokutl.types",
    "herokutl.utils",
    "Heroku-TL-New",
    "heroku-tl-new",
    "heroku-tl",
    # Internal package prefixes & module routes
    "elys.modules.",
    "elys.modules",
    "elys.inline",
    "elys.main",
    "elys.security",
    "elys.forums",
    "elys.log",
    "elys.libraries.",
    "heroku.",
    "heroku",
    ".heroku",
    # Internal DB / cache keys & identifiers
    "elys-userbot",
    "elys_wait_channel_approve",
    "heroku_min",
    "elys_me",
    "elys_db",
    "elys_inline",
    "elys_grepped",
    "elys_caller",
    "elys_f",
    "elys_cmd",
    "elys_meta_pic",
    "elys_talks",
    "elys_watchers",
    "elys_ref",
    "elys_installation",
    "elys_overwritten",
    "elys_repo_url",
    "elys_venv_dir",
    "elys_started",
    "heroku_client_id_logging_tag",
    "_elys_client_id_logging_tag",
    "elys_entity_cache",
    "elys_perms_cache",
    "elys_fullchannel_cache",
    "elys_fulluser_cache",
    "elys_callback_handlers",
    "elys_inline_handlers",
    "elys_no_git",
    "ELYS_NO_GIT",
    "ELYS_DO_NOT_RESTART",
    "ELYS_DO_NOT_RESTART2",
    # Callback / routing keys
    "/start elys init",
    "elys/backupall/restore",
    "elys/backupall/restore/confirm",
    "elys/update",
    "elys/ignore_upd",
    "elys/lang/",
    "show_elys",
    "this_is_elys",
    "elys-logs.txt",
    "user@elys:~$",
    r"# ?scope: ?heroku_min",
    r"# ?scope: ?heroku_min ((?:\d+\.){2}\d+)",
    r"# ?scope: ?heroku_min ((\d+\.){2}\d+)",
    r"# ?scope: ?talvo_min",
    r"# ?scope: ?talvo_min ((?:\d+\.){2}\d+)",
    r"# ?scope: ?talvo_min ((\d+\.){2}\d+)",
    r"# ?scope: ?elys_min",
    r"# ?scope: ?elys_min ((?:\d+\.){2}\d+)",
    r"# ?scope: ?elys_min ((\d+\.){2}\d+)",
    "^[.] ?heroku$",
}


class BrandReplacer:
    def __init__(
        self,
        root_dir: str,
        from_brand: str = "Talvo",
        to_brand: str = "Elys",
        from_repo: str = "ZavozDevs/Talvo",
        to_repo: str = "ZavozDevs/Elys",
        dry_run: bool = False,
    ):
        self.root_dir = os.path.abspath(root_dir)
        self.from_brand = from_brand
        self.to_brand = to_brand
        self.from_repo = from_repo
        self.to_repo = to_repo
        self.dry_run = dry_run

        self.skip_dirs = {".git", "__pycache__", ".pytest_cache", "tmp", "venv", ".venv"}
        self.skip_extensions = {
            ".pyc", ".png", ".jpg", ".jpeg", ".webp", ".ico",
            ".woff", ".woff2", ".ttf", ".zip", ".tar", ".gz", ".7z"
        }

        # Build replacement mapping
        self.text_replacements = [
            # Full repos / links
            (self.from_repo, self.to_repo),
            (f"github.com/{self.from_repo}", f"github.com/{self.to_repo}"),
            # Russian name variations
            ("Талво", "Элис"),
            ("талво", "элис"),
            ("Хероку", "Элис"),
            ("хероку", "элис"),
            ("херуку", "элис"),
            ("Херуку", "Элис"),
            # Brand cases
            (self.from_brand.upper(), self.to_brand.upper()),
            (self.from_brand, self.to_brand),
        ]


    def _replace_text_safely(self, text: str) -> str:
        """Applies text replacements in order with protection for herokutl / HerokuTL."""
        # Temporary mask protected library names with neutral tokens
        mask_map = {
            "HerokuTL": "HerokuTL",
            "herokutl": "herokutl",
            "heroku-tl": "heroku-tl",
            "Heroku-TL": "Heroku-TL",
        }
        res = text
        for orig, mask in mask_map.items():
            res = res.replace(orig, mask)

        for old, new in self.text_replacements:
            res = res.replace(old, new)

        # Restore masked library names
        for orig, mask in mask_map.items():
            res = res.replace(mask, orig)

        return res



    def process_python_file(self, filepath: str) -> Tuple[bool, int, List[str]]:
        """
        Processes a Python file using tokenize to ensure code integrity.
        Only modifies docstrings, comments and non-protected UI strings.
        """
        with open(filepath, "rb") as fp:
            content_bytes = fp.read()

        try:
            tokens = list(tokenize.tokenize(io.BytesIO(content_bytes).readline))
        except Exception as e:
            return False, 0, [f"Tokenize error in {filepath}: {e}"]

        modified = False
        changes_count = 0
        logs = []

        # We will reconstruct source using token replacements
        # To avoid offset issues with token untokenize, we can modify token strings and use untokenize
        new_tokens = []
        for tok in tokens:
            tok_type, tok_string, start, end, line = tok
            new_string = tok_string

            if tok_type == tokenize.COMMENT:
                # Replace branding in comments
                replaced = self._replace_text_safely(tok_string)
                if replaced != tok_string:
                    new_string = replaced
                    modified = True
                    changes_count += 1
                    logs.append(f"Line {start[0]} [COMMENT]: {tok_string.strip()[:60]} -> {replaced.strip()[:60]}")

            elif tok_type == tokenize.STRING:
                # Check if it's a protected internal string
                raw_eval = None
                try:
                    raw_eval = eval(tok_string)
                except Exception:
                    pass

                is_protected = False
                if raw_eval is not None and isinstance(raw_eval, str):
                    if raw_eval in PROTECTED_EXACT_STRINGS:
                        is_protected = True
                    # Also check if it's an internal module key like "elys.modules.something"
                    elif raw_eval.startswith("heroku.") or raw_eval.startswith("herokutl"):
                        is_protected = True

                if not is_protected:
                    # Perform safe replacement on the string literal
                    replaced = self._replace_text_safely(tok_string)
                    # Extra protection: do not introduce corrupted herokutl
                    if replaced != tok_string:
                        # Make sure we didn't replace inside herokutl by accident
                        if "herokutl" not in tok_string or "herokutl" in replaced:
                            new_string = replaced
                            modified = True
                            changes_count += 1
                            logs.append(f"Line {start[0]} [STRING]: {tok_string.strip()[:60]} -> {replaced.strip()[:60]}")

            new_tokens.append((tok_type, new_string, start, end, line))

        if modified and not self.dry_run:
            try:
                new_code = tokenize.untokenize(new_tokens)
                with open(filepath, "wb") as fp:
                    fp.write(new_code)
            except Exception as e:
                return False, 0, [f"Untokenize error in {filepath}: {e}"]

        return modified, changes_count, logs

    def process_langpack_file(self, filepath: str) -> Tuple[bool, int, List[str]]:
        """
        Processes a YAML langpack file line-by-line.
        Protects top-level module keys (e.g. `elys_security:`) while translating all UI values.
        """
        with open(filepath, "r", encoding="utf-8") as fp:
            lines = fp.readlines()

        new_lines = []
        modified = False
        changes_count = 0
        logs = []

        for idx, line in enumerate(lines, 1):
            # Check if line is a top-level module key like "elys_info:" or "elys_security:"
            if re.match(r"^heroku_[a-z0-9_]+:\s*$", line):
                new_lines.append(line)
                continue

            replaced = self._replace_text_safely(line)
            if replaced != line:
                modified = True
                changes_count += 1
                logs.append(f"Line {idx}: {line.strip()[:60]} -> {replaced.strip()[:60]}")
                new_lines.append(replaced)
            else:
                new_lines.append(line)

        if modified and not self.dry_run:
            with open(filepath, "w", encoding="utf-8") as fp:
                fp.writelines(new_lines)

        return modified, changes_count, logs

    def process_generic_file(self, filepath: str) -> Tuple[bool, int, List[str]]:
        """
        Processes Markdown, shell scripts, Dockerfile, etc.
        """
        with open(filepath, "r", encoding="utf-8", errors="ignore") as fp:
            content = fp.read()

        replaced = self._replace_text_safely(content)
        if replaced != content:
            # Count changes
            changes_count = content.count(self.from_brand) + content.count(self.from_repo)
            logs = [f"Replaced branding in {os.path.basename(filepath)}"]
            if not self.dry_run:
                with open(filepath, "w", encoding="utf-8") as fp:
                    fp.write(replaced)
            return True, changes_count, logs

        return False, 0, []

    def run(self) -> Dict[str, any]:
        total_files = 0
        modified_files = 0
        total_changes = 0
        detailed_logs = []

        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            dirnames[:] = [d for d in dirnames if d not in self.skip_dirs]

            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext in self.skip_extensions or filename == "replace_brand.py":
                    continue

                filepath = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(filepath, self.root_dir)
                total_files += 1

                if ext == ".py":
                    mod, count, logs = self.process_python_file(filepath)
                elif "langpacks" in dirpath and ext in [".yml", ".yaml", ".json"]:
                    mod, count, logs = self.process_langpack_file(filepath)
                else:
                    mod, count, logs = self.process_generic_file(filepath)

                if mod:
                    modified_files += 1
                    total_changes += count
                    detailed_logs.append((rel_path, count, logs))

        return {
            "total_files": total_files,
            "modified_files": modified_files,
            "total_changes": total_changes,
            "detailed_logs": detailed_logs,
        }


def main():
    parser = argparse.ArgumentParser(description="Brand Replacer for Talvo")
    parser.add_argument("--from-brand", default="Heroku", help="Brand name to replace (default: Heroku)")
    parser.add_argument("--to-brand", default="Talvo", help="Target brand name (default: Talvo)")
    parser.add_argument("--from-repo", default="coddrago/Heroku", help="Original GitHub repo")
    parser.add_argument("--to-repo", default="ZavozDevs/Talvo", help="Target GitHub repo")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying files")
    parser.add_argument("--reverse", action="store_true", help="Reverse replacement (Talvo -> Heroku)")
    parser.add_argument("--path", default=".", help="Root directory of the project")

    args = parser.parse_args()

    from_b = args.to_brand if args.reverse else args.from_brand
    to_b = args.from_brand if args.reverse else args.to_brand
    from_r = args.to_repo if args.reverse else args.from_repo
    to_r = args.from_repo if args.reverse else args.to_repo

    print(f"=== Brand Replacer ===")
    print(f"Path: {os.path.abspath(args.path)}")
    print(f"Replacing: '{from_b}' -> '{to_b}'")
    print(f"Repo: '{from_r}' -> '{to_r}'")
    print(f"Dry run: {args.dry_run}\n")

    replacer = BrandReplacer(
        root_dir=args.path,
        from_brand=from_b,
        to_brand=to_b,
        from_repo=from_r,
        to_repo=to_r,
        dry_run=args.dry_run,
    )

    results = replacer.run()

    print(f"Scanned {results['total_files']} files.")
    print(f"Modified {results['modified_files']} files with {results['total_changes']} changes.\n")

    for rel_path, count, logs in results["detailed_logs"]:
        print(f"\n[{rel_path}] ({count} changes):")
        for log in logs[:10]:
            print(f"  - {log}")
        if len(logs) > 10:
            print(f"  ... and {len(logs) - 10} more changes")

    print("\n[OK] Completed successfully.")


if __name__ == "__main__":
    main()
