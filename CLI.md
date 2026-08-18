# CLI：直接跑脚本（不装 Skill）

不用 AI 工具的话，可以单独用 `wechat_draft.py`。零依赖，纯 Python 标准库，Python 3.9+。

前置条件与 README 里的[首次配置]相同：已认证公众号、AppID/AppSecret、IP 白名单、`.env`。

## 使用

```bash
# 本地预览（不联网、不进草稿箱）
python3 wechat_draft.py --file 文章.md --dry-run

# 正式进草稿箱
python3 wechat_draft.py --file 文章.md

# 进草稿箱后直接发布（会二次确认，发布后不可撤回）
python3 wechat_draft.py --file 文章.md --publish
```

## 参数

| 参数 | 说明 |
| --- | --- |
| `--file` | 指定要发布的 markdown 文件（图片、封面按文件所在目录解析） |
| `--title` | 覆盖标题（默认取 frontmatter 的 title） |
| `--cover` | 封面图路径（默认 `assets/cover-wechat.png`，回退 `cover.png`） |
| `--dry-run` | 只生成预览 HTML，不联网 |
| `--force` | 有图片占位但找不到文件时也继续 |
| `--publish` | 进草稿箱后直接发布（二次确认） |
| `--comment 0\|1` / `--only-fans 0\|1` | 评论设置，默认 0 |
| `--font-size` / `--line-height` / `--letter-spacing` / `--para-margin` | 排版参数，默认 16px / 1.75 / 1px / 24px |
| `--keep-h1` | 保留正文开头与标题重复的 H1（默认去掉） |
| `--check-ip` | 只打印本机公网 IP |

## 正文格式约定

- 图片用占位写在正文里：`【截图：说明 — assets/xxx.png】`，assets 相对文章所在目录
- 封面放 `assets/cover-wechat.png` 或 `assets/cover.png`，只用作缩略图，不会出现在正文里
- 代码块用 ```text 围栏，块内换行会原样保留

## 常见问题

| 报错 | 原因 | 解决 |
| --- | --- | --- |
| 40164 | IP 不在白名单 | 先 `--check-ip` 看当前公网 IP，去微信开发者平台「基础信息 → IP白名单」重新加。运营商 NAT 的 IP 会轮换，变了就重加 |
| 48001 | 接口未授权 | 公众号没认证，或「接口管理 → 接口权限与额度 → 服务端接口 → 草稿管理」未开通 |
| 40001 / 40125 | AppSecret 错误或已重置 | 重新生成 AppSecret 并更新 .env |
| 找不到封面图 | assets 里没有封面 | 放一张 `cover-wechat.png` / `cover.png`，或用 `--cover` 指定 |
