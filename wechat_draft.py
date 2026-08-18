#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 content/<content_id>/master.md 发布到微信公众号草稿箱（官方 draft/add 接口）。

用法
----
    python3 _scripts/wechat_draft.py <content_id> [选项]

常用示例
--------
    # 仅进草稿箱（默认，不会群发）
    python3 _scripts/wechat_draft.py 2026-08-13-wechat-recommendation-zero-review

    # 直接指定任意 markdown 文件（不依赖知识库结构，适合单独使用）
    python3 _scripts/wechat_draft.py --file 文章.md

    # 本地预览 HTML，不联网不调用接口
    python3 _scripts/wechat_draft.py <content_id> --dry-run

    # 进草稿箱后直接发布（会先二次确认）
    python3 _scripts/wechat_draft.py <content_id> --publish

    # 查本机公网 IP（用于加白名单）
    python3 _scripts/wechat_draft.py --check-ip

选项
----
    --cover PATH      封面图路径（默认 assets/cover-wechat.png，回退 assets/cover.png）
    --title TEXT      覆盖标题（默认取 frontmatter 的 title）
    --keep-h1         保留正文开头的 H1（默认去掉与标题重复的 H1）
    --publish         进草稿箱后调用发布接口直接发布（会二次确认）
    --dry-run         只生成 HTML 预览文件，不联网
    --force           正文有【截图/配图/图片】占位但找不到图片文件时也继续
    --comment 0|1     是否打开评论，默认 1（默认打开）
    --only-fans 0|1   是否仅粉丝可评论，默认 0
    --env PATH        .env 文件路径（默认仓库根目录 .env）
    --token TEXT      手动提供 access_token（跳过自动获取）
    --preview PATH    --dry-run 时预览文件输出路径（默认 content/<id>/draft_preview.html）
    --font-size       正文字号，默认 16px（如 18px）
    --line-height     行高，默认 1.75
    --letter-spacing  字间距，默认 1px
    --para-margin     段后距，默认 24px

前置条件
--------
1. 公众号已认证，微信开发者平台（developers.weixin.qq.com/platform）里「接口管理 → 接口权限与额度 → 服务端接口 → 草稿管理」已开通；
2. 微信开发者平台 → 我的业务和服务 → 选择公众号 → 基础信息，拿到 AppID / AppSecret（IP 白名单也在同一页）；
3. 本机公网 IP 已加入微信开发者平台「基础信息 → IP白名单」（用 --check-ip 查看本机公网 IP）；
4. 密钥配置二选一（不会写进仓库文件）：
   - 环境变量：export WECHAT_APPID=xxx / export WECHAT_SECRET=xxx
   - 仓库根目录 .env（已 gitignore）：
       WECHAT_APPID=xxx
       WECHAT_SECRET=xxx

接口顺序
--------
1. GET  /cgi-bin/token                  拿 access_token
2. POST /cgi-bin/media/uploadimg        正文图片 → 微信 CDN URL
3. POST /cgi-bin/material/add_material  封面 → thumb_media_id
4. POST /cgi-bin/draft/add              新增草稿（进草稿箱）
5. (可选) POST /cgi-bin/freepublish/submit  直接发布

安全说明
--------
AppID / AppSecret 只从环境变量或 .env 读取，不写进任何仓库文件；
.env 已在 .gitignore 中，Git 永不提交。
"""

import argparse
import html
import json
import os
import re
import sys
import uuid
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.weixin.qq.com/cgi-bin"
ROOT = Path(__file__).resolve().parent.parent  # 仓库根目录

MARKER_RE = re.compile(r"【(截图|配图|图片)：(.+?)】", re.S)
IMG_TOKEN_RE = re.compile(r"\x00IMG(\d+)\x00")


# ---------------------------------------------------------------- 基础工具

def eprint(*a):
    print(*a, file=sys.stderr)


def http_get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def http_post_json(url, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def http_post_form(url, fields=None, files=None):
    boundary = "----PyWeChat" + uuid.uuid4().hex
    body = b""
    for k, v in (fields or {}).items():
        body += (f"--{boundary}\r\n"
                 f'Content-Disposition: form-data; name="{k}"\r\n\r\n'
                 f"{v}\r\n").encode("utf-8")
    for k, (filename, content, ctype) in (files or {}).items():
        body += (f"--{boundary}\r\n"
                 f'Content-Disposition: form-data; name="{k}"; filename="{filename}"\r\n'
                 f"Content-Type: {ctype}\r\n\r\n").encode("utf-8") + content + b"\r\n"
    body += f"--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def content_type(path):
    ext = Path(path).suffix.lower()
    return {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    }.get(ext, "application/octet-stream")


def check_api(resp, what):
    if resp.get("errcode"):
        code = resp.get("errcode")
        msg = resp.get("errmsg", "")
        hint = {
            40001: "AppSecret 错误或已重置，请在后台核对",
            40013: "AppID 错误，请核对",
            40125: "AppSecret 错误，请核对",
            40164: "IP 不在白名单：请在微信开发者平台「基础信息 → IP白名单」加入本机公网 IP",
            40165: "IP 不在白名单：请在后台加入本机公网 IP",
            41001: "access_token 缺失或失效",
            42001: "access_token 过期，请重新获取",
            48001: "接口未授权：微信开发者平台「接口管理 → 接口权限与额度 → 服务端接口」里没有「草稿管理」（通常需要公众号认证）",
            45009: "接口调用频率超限，请稍后再试",
            53010: "该接口需要公众号认证才能使用",
        }
        raise RuntimeError(
            f"{what}失败: errcode={code} errmsg={msg}。" + (hint.get(code, "") or "").rstrip()
        )
    return resp


def get_public_ip():
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip", "https://ipv4.icanhazip.com"):
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                return r.read().decode("utf-8").strip()
        except Exception:
            continue
    return "无法获取公网 IP（请检查网络）"


# ---------------------------------------------------------------- 密钥

def load_env_file(path):
    env = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def get_secrets(env_path):
    env = load_env_file(env_path)
    appid = os.environ.get("WECHAT_APPID") or env.get("WECHAT_APPID")
    secret = os.environ.get("WECHAT_SECRET") or env.get("WECHAT_SECRET")
    if not appid or not secret:
        raise RuntimeError(
            "未找到 WECHAT_APPID / WECHAT_SECRET。配置方式二选一：\n"
            "  1) 环境变量：export WECHAT_APPID=xxx; export WECHAT_SECRET=xxx\n"
            "  2) 仓库根目录 .env 文件（已 gitignore）：\n"
            "     WECHAT_APPID=xxx\n"
            "     WECHAT_SECRET=xxx"
        )
    return appid, secret


def get_token(appid, secret):
    url = (f"{API}/token?grant_type=client_credential"
           f"&appid={urllib.parse.quote(appid)}&secret={urllib.parse.quote(secret)}")
    resp = check_api(http_get(url), "获取 access_token")
    return resp["access_token"]


# ---------------------------------------------------------------- frontmatter

def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm = text[3:end]
    body = text[end + 4:].lstrip("\n")
    meta = {}
    for line in fm.splitlines():
        m = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
        if m:
            meta[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return meta, body


# ---------------------------------------------------------------- 图片占位

def collect_markers(body, content_dir, upload_inline, live, force, warnings):
    """把【截图/配图/图片：说明 — assets/xxx】替换成 IMG token；返回 (new_body, imgs)
    封面文件（cover-wechat.png / cover.png）只作缩略图，不放进正文。"""
    imgs = []
    COVER_NAMES = ("cover-wechat.png", "cover.png")

    def repl(m):
        kind, rest = m.group(1), m.group(2)
        mm = re.search(r"\s—\s+(assets/[^\s]+)$", rest.strip())
        if mm:
            rel, desc = mm.group(1), rest[:mm.start()].strip()
        else:
            rel, desc = None, rest.strip()
        if rel:
            if Path(rel).name in COVER_NAMES:
                return ""  # 封面不进正文
            fpath = content_dir / rel
            if fpath.exists():
                src = upload_inline(fpath) if (live and upload_inline) else rel
                imgs.append((desc, src))
                return f"\x00IMG{len(imgs)-1}\x00"
            warnings.append(f"文件不存在: {rel}（{desc[:24]}…）")
            return m.group(0)
        warnings.append(f"占位缺少图片文件: {m.group(0)[:36]}…")
        return m.group(0)

    new_body = MARKER_RE.sub(repl, body)
    if warnings and live and not force:
        raise RuntimeError(
            "存在未配图的【截图/配图/图片】占位，已中止，请先补图：\n"
            + "\n".join("  - " + w for w in warnings)
            + "\n确认要发布请加 --force"
        )
    return new_body, imgs


def restore_imgs(html_text, imgs, tp):
    def repl(m):
        i = int(m.group(1))
        if i < len(imgs):
            desc, src = imgs[i]
            return (f'<img style="{tp.img()}" '
                    f'src="{html.escape(src, quote=True)}" '
                    f'alt="{html.escape(desc, quote=True)}" />')
        return m.group(0)

    return IMG_TOKEN_RE.sub(repl, html_text)


# ---------------------------------------------------------------- Markdown → HTML

class Typo:
    """公众号排版参数，命令行可覆盖（默认 字号16px / 段后距24px / 行高1.75 / 字间距1px）"""

    def __init__(self, font_size="16px", line_height="1.75",
                 letter_spacing="1px", para_margin="24px"):
        self.font_size = font_size
        self.line_height = line_height
        self.letter_spacing = letter_spacing
        self.para_margin = para_margin

    def body(self):
        return (f"font-size:{self.font_size};letter-spacing:{self.letter_spacing};"
                f"line-height:{self.line_height};margin:0 0 {self.para_margin};")

    def list_item(self):
        return (f"font-size:{self.font_size};letter-spacing:{self.letter_spacing};"
                f"line-height:{self.line_height};margin-bottom:12px;")

    def heading(self, size, mt, mb, color="#3b7cff"):
        return (f"font-size:{size};font-weight:bold;color:{color};letter-spacing:{self.letter_spacing};"
                f"line-height:1.5;margin:{mt} 0 {mb};")

    def quote(self):
        return (f"font-size:15px;letter-spacing:{self.letter_spacing};"
                f"line-height:{self.line_height};margin:0 0 {self.para_margin};")

    def code(self):
        return ("background:#f7f7f7;border-radius:6px;padding:14px 16px;"
                "font-family:Menlo,Consolas,monospace;font-size:14px;line-height:1.6;"
                "white-space:pre-wrap;word-break:break-all;margin:0 0 24px;")

    def cell(self):
        return "font-size:14px;line-height:1.5;padding:8px;border:1px solid #ddd;"

    def img(self):
        return "max-width:100%;display:block;margin:12px auto 24px;"


def inline(text):
    codes = []

    def _code(m):
        codes.append(html.escape(m.group(1), quote=False))
        return f"\x00C{len(codes)-1}\x00"

    text = re.sub(r"`([^`\n]+)`", _code, text)
    text = html.escape(text, quote=False)
    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img src="\2" alt="\1" />', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+?)\*", r"<em>\1</em>", text)
    for i, c in enumerate(codes):
        text = text.replace(f"\x00C{i}\x00", f"<code>{c}</code>")
    return text


def split_row(row):
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [c.strip() for c in row.split("|")]


def is_table_sep(line):
    s = line.replace("|", "").strip()
    if not s or "-" not in s:
        return False
    return all(ch in ":- " for ch in s)


def _aligned(tag, align, inner, extra_style=""):
    parts = []
    if align:
        parts.append(f"text-align:{align}")
    if extra_style:
        parts.append(extra_style)
    attr = f' style="{";".join(parts)}"' if parts else ""
    return f"<{tag}{attr}>{inner}</{tag}>"


def parse_table(lines, i, tp):
    header = split_row(lines[i])
    sep = split_row(lines[i + 1])
    aligns = []
    for c in sep:
        c = c.strip()
        left, right = c.startswith(":"), c.endswith(":")
        aligns.append("left" if left and not right
                      else "right" if right and not left
                      else "center" if left and right else "")
    i += 2
    rows = []
    while i < len(lines) and lines[i].strip().startswith("|"):
        rows.append(split_row(lines[i]))
        i += 1
    ncol = max(len(header), max((len(r) for r in rows), default=0))

    def cell(cells, idx):
        return inline(cells[idx].strip()) if idx < len(cells) else ""

    th = "".join(_aligned("th", aligns[j], cell(header, j), tp.cell()) for j in range(ncol))
    tbody = "".join(
        "<tr>" + "".join(_aligned("td", aligns[j], cell(r, j), tp.cell()) for j in range(ncol)) + "</tr>"
        for r in rows
    )
    return f'<table style="width:100%;border-collapse:collapse;"><thead><tr>{th}</tr></thead><tbody>{tbody}</tbody></table>', i


def is_list_line(line):
    return bool(re.match(r"^\s*([-*+]|\d+\.)\s+", line))


def list_to_html(lines, tp):
    parsed = []
    for l in lines:
        m = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", l)
        if m:
            indent = len(m.group(1))
            ordered = m.group(2).rstrip(".").isdigit()
            parsed.append([indent, ordered, m.group(3)])
        else:
            if parsed:
                parsed[-1][2] += " " + l.strip()
    if not parsed:
        return ""

    li_style = f' style="{tp.list_item()}"'

    def build(start, level):
        out = []
        i = start
        tag = None
        while i < len(parsed):
            ind, ordered, text = parsed[i]
            if ind == level:
                if tag is None:
                    tag = "ol" if ordered else "ul"
                out.append("<li" + li_style + ">" + inline(text))
                i += 1
            elif ind > level:
                sub, i = build(i, ind)
                out[-1] += sub
            else:
                break
        if tag is None:
            return "", i
        return f"<{tag}>" + "".join(x + "</li>" for x in out) + f"</{tag}>", i

    html_str, _ = build(0, parsed[0][0])
    return html_str


def md_to_html(text, tp):
    lines = text.split("\n")
    out = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        # 代码块
        if s.startswith("```"):
            buf = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # 跳过闭合 ```
            code_style = f' style="{tp.code()}"'
            code_text = "<br/>".join(html.escape(line, quote=False) for line in buf)
            out.append("<pre" + code_style + "><code>" + code_text + "</code></pre>")
            continue
        # 标题
        hm = re.match(r"^(#{1,6})\s+(.*)$", s)
        if hm:
            lv = len(hm.group(1))
            heading_text = hm.group(2).strip()
            # 「写在最后」之前加分割线
            if heading_text.startswith("写在最后"):
                out.append('<hr style="border:none;border-top:1px solid #e5e5e5;margin:32px 0;" />')
            size = "16px"  # 标题与正文统一字号，靠加粗和颜色区分
            mt = {1: "0", 2: "32px", 3: "24px"}.get(lv, "16px")
            mb = {1: "24px", 2: "16px", 3: "12px"}.get(lv, "8px")
            h_style = f' style="{tp.heading(size, mt, mb)}"'
            out.append(f"<h{lv}{h_style}>{inline(hm.group(2))}</h{lv}>")
            i += 1
            continue
        # 表格
        if s.startswith("|") and i + 1 < n and is_table_sep(lines[i + 1]):
            tbl, i = parse_table(lines, i, tp)
            out.append(tbl)
            continue
        # 分隔线
        if re.match(r"^(-{3,}|\*{3,}|_{3,})\s*$", s):
            out.append('<hr style="border:none;border-top:1px solid #e5e5e5;margin:32px 0;" />')
            i += 1
            continue
        # 引用
        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].lstrip())
                i += 1
            quote_style = f' style="{tp.quote()}"'
            out.append("<blockquote" + quote_style + ">" + md_to_html("\n".join(buf), tp) + "</blockquote>")
            continue
        # 列表
        if is_list_line(line):
            start = i
            while i < n:
                l = lines[i]
                if not l.strip():
                    break
                if is_list_line(l) or re.match(r"^\s{2,}", l):
                    i += 1
                else:
                    break
            out.append(list_to_html(lines[start:i], tp))
            continue
        # 普通段落
        buf = [line]
        i += 1
        while i < n:
            l = lines[i]
            if not l.strip():
                break
            ls = l.strip()
            if re.match(r"^(#{1,6})\s", ls) or ls.startswith("```") or ls.startswith(">") or is_list_line(l):
                break
            if ls.startswith("|") and i + 1 < n and is_table_sep(lines[i + 1]):
                break
            buf.append(l)
            i += 1
        p_style = f' style="{tp.body()}"'
        out.append("<p" + p_style + ">" + inline(" ".join(x.strip() for x in buf)) + "</p>")
    return "\n".join(out)


def strip_leading_h1(body, title, keep):
    if keep or not title:
        return body
    lines = body.split("\n")
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx < len(lines):
        m = re.match(r"^#\s+(.*)$", lines[idx].strip())
        if m and m.group(1).strip() == title.strip():
            lines = lines[idx + 1:]
    return "\n".join(lines).lstrip("\n")


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(
        description="把 content/<content_id>/master.md 发布到公众号草稿箱",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：python3 _scripts/wechat_draft.py 2026-08-13-wechat-recommendation-zero-review --dry-run",
    )
    ap.add_argument("content_id", nargs="?", help="内容包 ID，如 2026-08-13-wechat-recommendation-zero-review")
    ap.add_argument("--file", help="直接指定 markdown 文件（替代 content_id，不依赖知识库结构，图片/封面按文件所在目录解析）")
    ap.add_argument("--cover", help="封面图路径（默认 assets/cover-wechat.png，回退 cover.png）")
    ap.add_argument("--title", help="覆盖标题（默认取 frontmatter 的 title）")
    ap.add_argument("--keep-h1", action="store_true", help="保留正文开头与标题重复的 H1")
    ap.add_argument("--publish", action="store_true", help="进草稿箱后直接发布（会二次确认）")
    ap.add_argument("--dry-run", action="store_true", help="只生成 HTML 预览，不联网")
    ap.add_argument("--force", action="store_true", help="有占位但找不到图片文件时也继续")
    ap.add_argument("--comment", type=int, choices=[0, 1], default=1, help="是否打开评论（默认 1，即打开）")
    ap.add_argument("--only-fans", type=int, choices=[0, 1], default=0, help="是否仅粉丝可评论（默认 0）")
    ap.add_argument("--env", help=".env 文件路径（默认仓库根目录 .env）")
    ap.add_argument("--token", help="手动提供 access_token（跳过自动获取）")
    ap.add_argument("--preview", help="--dry-run 时预览文件路径（默认 content/<id>/draft_preview.html）")
    ap.add_argument("--check-ip", action="store_true", help="只打印本机公网 IP 后退出")
    ap.add_argument("--font-size", default="16px", help="正文字号，默认 16px")
    ap.add_argument("--line-height", default="1.75", help="行高，默认 1.75")
    ap.add_argument("--letter-spacing", default="1px", help="字间距，默认 1px")
    ap.add_argument("--para-margin", default="24px", help="段后距，默认 24px")
    args = ap.parse_args()

    if args.check_ip:
        print(get_public_ip())
        return

    if not args.content_id and not args.file:
        ap.error("需要 content_id 或 --file（或用 --check-ip 查看公网 IP）")

    if args.publish and args.dry_run:
        ap.error("--publish 和 --dry-run 不能同时使用")

    if args.file:
        master = Path(args.file)
        if not master.exists():
            sys.exit(f"找不到文件: {master}")
        base_dir = master.parent  # 图片/封面按文章所在目录解析，不依赖知识库结构
    else:
        base_dir = ROOT / "content" / args.content_id
        if not base_dir.is_dir():
            sys.exit(f"找不到内容包: {base_dir}")
        master = base_dir / "master.md"
        if not master.exists():
            sys.exit(f"找不到 master.md: {master}")

    meta, body = parse_frontmatter(master.read_text(encoding="utf-8"))
    title = args.title or meta.get("title", "")
    author = meta.get("author", "")
    digest = (meta.get("description", "") or "")[:120]
    source = meta.get("source", "").strip()
    if source and not source.startswith("http"):
        source = ""
    if not title:
        m = re.search(r"^#\s+(.+)$", body, re.M)
        title = m.group(1).strip() if m else "未命名"

    if args.dry_run:
        token, live = None, False
    else:
        if args.env:
            env_path = Path(args.env)
        else:
            env_path = Path.cwd() / ".env"
            if not env_path.exists():
                env_path = ROOT / ".env"
        appid, secret = get_secrets(env_path)
        token = args.token or get_token(appid, secret)
        live = True

    assets_dir = base_dir / "assets"

    def upload_inline(fpath):
        url = f"{API}/media/uploadimg?access_token={token}"
        resp = check_api(http_post_form(url, files={"media": (fpath.name, fpath.read_bytes(), content_type(str(fpath)))}), "上传正文图片")
        return resp["url"]

    warnings = []
    body2, imgs = collect_markers(body, base_dir, upload_inline if live else None, live, args.force, warnings)
    for w in warnings:
        eprint("[警告]", w)

    body2 = strip_leading_h1(body2, title, args.keep_h1)
    tp = Typo(args.font_size, args.line_height, args.letter_spacing, args.para_margin)
    html_body = restore_imgs(md_to_html(body2, tp), imgs, tp)

    if args.dry_run:
        preview = Path(args.preview) if args.preview else base_dir / "draft_preview.html"
        preview.write_text(html_body, encoding="utf-8")
        print(f"[dry-run] 预览已生成: {preview}")
        print(f"标题: {title}")
        print(f"作者: {author or '(默认公众号名)'}")
        print(f"摘要: {digest or '(空)'}")
        print(f"正文图片: {len(imgs)} 张（预览用本地相对路径，正式发布时会上传）")
        if warnings:
            print(f"警告: {len(warnings)} 处占位没有图片文件，正式发布会被中止")
        return

    # 封面
    cover = None
    if args.cover:
        cover = Path(args.cover)
        if not cover.is_absolute():
            cover = base_dir / args.cover
    else:
        for cand in ("cover-wechat.png", "cover.png"):
            p = assets_dir / cand
            if p.exists():
                cover = p
                break
    if not cover or not cover.exists():
        sys.exit("找不到封面图（默认 assets/cover-wechat.png 或 assets/cover.png），可用 --cover 指定")
    resp = check_api(http_post_form(
        f"{API}/material/add_material?access_token={token}&type=image",
        files={"media": (cover.name, cover.read_bytes(), content_type(str(cover)))},
    ), "上传封面")
    thumb_media_id = resp["media_id"]

    article = {
        "title": title,
        "author": author,
        "digest": digest,
        "content": html_body,
        "content_source_url": source,
        "thumb_media_id": thumb_media_id,
        "need_open_comment": int(args.comment),
        "only_fans_can_comment": int(args.only_fans),
    }
    resp = check_api(http_post_json(f"{API}/draft/add?access_token={token}", {"articles": [article]}), "新增草稿")
    draft_id = resp["media_id"]
    print(f"✅ 已进入草稿箱: media_id={draft_id}")
    print(f"   标题: {title}")
    print(f"   正文图片: {len(imgs)} 张")
    print("   请到「草稿箱」预览确认后再手动发布。")

    if args.publish:
        ans = input("即将直接发布（发布后无法撤回，只能删除），继续？[y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("已取消发布，草稿保留在草稿箱。")
            return
        resp = check_api(http_post_json(f"{API}/freepublish/submit?access_token={token}", {"media_id": draft_id}), "发布")
        print(f"✅ 已提交发布: publish_id={resp.get('publish_id')}")
        print("   可在后台「发布记录」查看状态。")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        eprint("错误:", e)
        sys.exit(1)
    except urllib.error.URLError as e:
        eprint("网络错误:", e)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
