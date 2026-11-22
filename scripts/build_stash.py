#!/usr/bin/env python3
"""
自动拉取上游 QX / Surge 去广告模块并与本仓库 rewrite.conf 合并，
生成标准 Stash 覆写文件 stash.stoverride。
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_STASH_FILE = REPO_ROOT / "rewrite.stoverride"
OUTPUT_FILE = REPO_ROOT / "stash.stoverride"

MOJI_ENTRANCE_JS_URL = (
    "https://raw.githubusercontent.com/Nisesummer/MITM/main/scripts/moji-entrance.js"
)
BODY_REPLACE_JS_URL = (
    "https://raw.githubusercontent.com/Nisesummer/MITM/main/scripts/body-replace.js"
)

UPSTREAMS = [
    (
        "qx",
        "NeteaseAds",
        "https://raw.githubusercontent.com/ddgksf2013/Rewrite/master/AdBlock/NeteaseAds.conf",
    ),
    (
        "qx",
        "MoJiWeatherAds",
        "https://raw.githubusercontent.com/ddgksf2013/Rewrite/refs/heads/master/AdBlock/MoJiWeatherAds.conf",
    ),
    (
        "qx",
        "AmapAds",
        "https://raw.githubusercontent.com/ddgksf2013/Rewrite/master/AdBlock/AmapAds.conf",
    ),
    (
        "qx",
        "Applet",
        "https://raw.githubusercontent.com/ddgksf2013/Rewrite/master/AdBlock/Applet.conf",
    ),
    (
        "qx",
        "StartUpAds",
        "https://ddgksf2013.top/rewrite/StartUpAds.conf",
    ),
    (
        "sgmodule",
        "YouTube-HideShorts",
        "https://raw.githubusercontent.com/Aioneas/Surge/main/Module/youtube.aioneas.hide-shorts.sgmodule",
    ),
    (
        "sgmodule",
        "TiebaAds",
        "https://raw.githubusercontent.com/app2smile/rules/master/module/tieba.sgmodule",
    ),
]


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Quantumult%20X/1.5.5"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read().decode("utf-8", errors="replace")


class StashBuilder:
    def __init__(self) -> None:
        self.mitm: list[str] = []
        self.rules: list[str] = []
        self.rewrites: list[str] = []
        self.scripts: list[dict[str, Any]] = []
        self.providers: dict[str, dict[str, Any]] = {}
        self._url_to_provider: dict[str, str] = {}

    def add_mitm(self, hosts_str: str) -> None:
        cleaned = re.sub(r"^\s*%(APPEND|INSERT)%\s*", "", hosts_str.strip())
        for h in cleaned.split(","):
            h = h.strip()
            if h and h not in self.mitm:
                self.mitm.append(h)

    def add_rule(self, rule: str) -> None:
        rule = rule.strip()
        if rule and rule not in self.rules:
            self.rules.append(rule)

    def add_rewrite(self, line: str) -> None:
        line = line.strip()
        if line and line not in self.rewrites:
            self.rewrites.append(line)

    def register_provider(self, url: str, hint: str) -> str:
        if url in self._url_to_provider:
            return self._url_to_provider[url]
        stem = Path(url.split("?")[0]).stem
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", f"{hint}-{stem}").strip("-").lower()
        if not safe:
            safe = "script-" + hashlib.md5(url.encode()).hexdigest()[:8]
        name = safe
        idx = 2
        while name in self.providers:
            name = f"{safe}-{idx}"
            idx += 1
        self.providers[name] = {"url": url, "interval": 86400}
        self._url_to_provider[url] = name
        return name

    def add_script(self, entry: dict[str, Any]) -> None:
        if entry not in self.scripts:
            self.scripts.append(entry)

    def parse_qx(self, text: str, tag: str) -> None:
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith(("#", "//", ";")):
                continue

            # hostname = a, b
            m_host = re.match(r"^hostname\s*=\s*(.+)$", line, re.I)
            if m_host:
                self.add_mitm(m_host.group(1))
                continue

            # host-suffix / host / host-keyword
            m_rule = re.match(
                r"^(host-suffix|host-keyword|host|ip-cidr|ip6-cidr)\s*,\s*([^,]+)\s*,\s*(\S+)",
                line,
                re.I,
            )
            if m_rule:
                kind_map = {
                    "host-suffix": "DOMAIN-SUFFIX",
                    "host-keyword": "DOMAIN-KEYWORD",
                    "host": "DOMAIN",
                    "ip-cidr": "IP-CIDR",
                    "ip6-cidr": "IP-CIDR6",
                }
                k = kind_map[m_rule.group(1).lower()]
                val = m_rule.group(2).strip()
                act = m_rule.group(3).strip().upper()
                if act.startswith("REJECT"):
                    act = "REJECT"
                self.add_rule(f"{k},{val},{act}")
                continue

            # ^regex url <action> [arg]
            m_url = re.match(r"^(\S+)\s+url\s+(\S+)(?:\s+(.+))?$", line)
            if m_url:
                pattern, action, arg = (
                    m_url.group(1),
                    m_url.group(2).lower(),
                    (m_url.group(3) or "").strip(),
                )
                if action in (
                    "reject",
                    "reject-200",
                    "reject-dict",
                    "reject-img",
                    "reject-array",
                    "reject-no-drop",
                ):
                    stash_act = {
                        "reject": "reject",
                        "reject-200": "reject-200",
                        "reject-dict": "reject-dict",
                        "reject-img": "reject-img",
                        "reject-array": "reject-dict",
                        "reject-no-drop": "reject-200",
                    }[action]
                    self.add_rewrite(f"{pattern} - {stash_act}")
                elif action in ("302", "307") and arg:
                    self.add_rewrite(f"{pattern} {arg} {action}")
                elif action in ("script-response-body", "script-request-body", "script-response-header", "script-request-header") and arg:
                    prov = self.register_provider(arg, tag)
                    stype = "response" if "response" in action else "request"
                    req_body = "body" in action
                    entry: dict[str, Any] = {
                        "match": pattern,
                        "name": prov,
                        "type": stype,
                        "require-body": req_body,
                    }
                    if "proto" in arg.lower():
                        entry["binary-mode"] = True
                    self.add_script(entry)
                elif action == "response-body" and " response-body " in arg:
                    find_pat, rep_val = arg.split(" response-body ", 1)
                    prov = self.register_provider(BODY_REPLACE_JS_URL, "body-replace")
                    self.add_script(
                        {
                            "match": pattern,
                            "name": prov,
                            "type": "response",
                            "require-body": True,
                            "argument": json.dumps(
                                {"find": find_pat.strip(), "replace": rep_val.strip()},
                                ensure_ascii=False,
                            ),
                        }
                    )
                elif action == "jsonjq-response-body" and "entrance_region_res_list" in arg:
                    prov = self.register_provider(MOJI_ENTRANCE_JS_URL, "moji-entrance")
                    self.add_script(
                        {
                            "match": pattern,
                            "name": prov,
                            "type": "response",
                            "require-body": True,
                        }
                    )

    def _split_kv(self, s: str) -> dict[str, str]:
        """Parse Surge comma-separated k=v respecting quoted values."""
        res: dict[str, str] = {}
        parts: list[str] = []
        buf: list[str] = []
        in_quote = False
        for ch in s:
            if ch == '"':
                in_quote = not in_quote
                buf.append(ch)
            elif ch == "," and not in_quote:
                parts.append("".join(buf).strip())
                buf = []
            else:
                buf.append(ch)
        if buf:
            parts.append("".join(buf).strip())

        for p in parts:
            if "=" in p:
                k, v = p.split("=", 1)
                k = k.strip()
                v = v.strip()
                if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
                    v = v[1:-1]
                res[k] = v
        return res

    def parse_sgmodule(self, text: str, tag: str) -> None:
        section = ""
        arg_defaults: dict[str, str] = {}

        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#!arguments="):
                for item in line.split("=", 1)[1].split(","):
                    if ":" in item:
                        k, v = item.split(":", 1)
                        arg_defaults[k.strip()] = v.strip()
                continue
            if line.startswith(("#", "//", ";")):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip().lower()
                continue

            if section == "mitm":
                m = re.match(r"^hostname\s*=\s*(.+)$", line, re.I)
                if m:
                    self.add_mitm(m.group(1))

            elif section == "rule":
                if line.upper().startswith("RULE-SET,"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        rs_url, rs_act = parts[1], parts[2].upper()
                        if rs_act.startswith("REJECT"):
                            rs_act = "REJECT"
                        try:
                            rs_text = fetch_text(rs_url)
                            for rline in rs_text.splitlines():
                                rl = rline.strip()
                                if not rl or rl.startswith(("#", "//", ";")):
                                    continue
                                if re.match(
                                    r"^(DOMAIN|DOMAIN-SUFFIX|DOMAIN-KEYWORD|IP-CIDR|IP-CIDR6),",
                                    rl,
                                    re.I,
                                ):
                                    rparts = [x.strip() for x in rl.split(",")]
                                    if len(rparts) == 2:
                                        self.add_rule(f"{rparts[0].upper()},{rparts[1]},{rs_act}")
                                    elif len(rparts) >= 3 and rparts[2].lower() == "no-resolve":
                                        self.add_rule(
                                            f"{rparts[0].upper()},{rparts[1]},{rs_act},no-resolve"
                                        )
                        except Exception as exc:
                            print(f"WARN: failed to fetch rule-set {rs_url}: {exc}")
                else:
                    self.add_rule(line)

            elif section == "url rewrite":
                parts = line.split()
                if len(parts) >= 3:
                    pat, target, mode = parts[0], parts[1], parts[2].lower()
                    if mode in ("302", "307", "header"):
                        self.add_rewrite(f"{pat} {target} {mode}")
                    elif mode.startswith("reject"):
                        self.add_rewrite(f"{pat} - {mode}")
                elif len(parts) == 2 and parts[1].lower().startswith("reject"):
                    self.add_rewrite(f"{parts[0]} - {parts[1].lower()}")

            elif section == "map local":
                # Convert Surge Map Local empty/blank 200 responses to Stash reject-200
                pat = line.split()[0]
                self.add_rewrite(f"{pat} - reject-200")

            elif section == "script":
                if "=" not in line:
                    continue
                sname, rhs = line.split("=", 1)
                kv = self._split_kv(rhs)
                stype_raw = kv.get("type", "").lower()
                if stype_raw not in ("http-response", "http-request"):
                    continue
                pattern = kv.get("pattern", "")
                spath = kv.get("script-path", "")
                if not pattern or not spath:
                    continue
                prov = self.register_provider(spath, tag)
                entry: dict[str, Any] = {
                    "match": pattern,
                    "name": prov,
                    "type": "response" if stype_raw == "http-response" else "request",
                }
                if kv.get("requires-body", "").lower() in ("true", "1"):
                    entry["require-body"] = True
                if kv.get("binary-body-mode", "").lower() in ("true", "1"):
                    entry["binary-mode"] = True
                if "max-size" in kv:
                    try:
                        entry["max-size"] = int(kv["max-size"])
                    except ValueError:
                        pass
                if "timeout" in kv:
                    try:
                        entry["timeout"] = int(kv["timeout"])
                    except ValueError:
                        pass
                if "argument" in kv:
                    arg_val = kv["argument"]
                    for ak, av in arg_defaults.items():
                        arg_val = arg_val.replace(f"{{{{{{{ak}}}}}}}", av)
                    entry["argument"] = arg_val
                self.add_script(entry)

    def parse_local_stoverride(self, text: str) -> None:
        data = yaml.safe_load(text) or {}
        for r in data.get("rules") or []:
            self.add_rule(str(r))
        http = data.get("http") or {}
        for h in http.get("mitm") or []:
            self.add_mitm(str(h))
        for rw in (http.get("url-rewrite") or []) + (http.get("rewrite") or []):
            self.add_rewrite(str(rw))
        for sc in http.get("script") or []:
            if isinstance(sc, dict):
                self.add_script(sc)
        for pname, pval in (data.get("script-providers") or {}).items():
            if isinstance(pval, dict) and pname not in self.providers:
                self.providers[pname] = pval

    def build_yaml(self) -> str:
        doc: dict[str, Any] = {
            "name": "个人综合去广告与净化（自动同步）",
            "rules": self.rules,
            "http": {
                "mitm": self.mitm,
                "url-rewrite": self.rewrites,
                "script": self.scripts,
            },
            "script-providers": self.providers,
        }
        header = (
            "# 自动生成文件，请勿手动编辑（修改个人规则请改 rewrite.stoverride）\n"
            "# 由 GitHub Actions 定时同步上游并生成\n"
        )
        return header + yaml.safe_dump(
            doc, allow_unicode=True, sort_keys=False, width=1000
        )


def main() -> None:
    builder = StashBuilder()

    if LOCAL_STASH_FILE.exists():
        builder.parse_local_stoverride(LOCAL_STASH_FILE.read_text(encoding="utf-8"))

    for kind, tag, url in UPSTREAMS:
        print(f"Fetching [{tag}] {url}")
        text = fetch_text(url)
        if kind == "qx":
            builder.parse_qx(text, tag)
        elif kind == "sgmodule":
            builder.parse_sgmodule(text, tag)

    output = builder.build_yaml()
    OUTPUT_FILE.write_text(output, encoding="utf-8")
    print(
        f"Generated {OUTPUT_FILE}: "
        f"{len(builder.mitm)} mitm hosts, "
        f"{len(builder.rules)} rules, "
        f"{len(builder.rewrites)} rewrites, "
        f"{len(builder.scripts)} scripts, "
        f"{len(builder.providers)} script-providers."
    )


if __name__ == "__main__":
    main()
