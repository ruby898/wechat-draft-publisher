# wechat-draft-publisher

把 Markdown 文章一键送进微信公众号草稿箱，排版自动套用。装成 Skill 之后不用敲命令，直接对 AI 说「发布到草稿箱」就行。

## 这是什么

一份标准 agent-skill，Codex、Claude Code、DeepSeek Harness 三个生态通用。装好后 AI 会帮你：

- 把 Markdown 转成公众号草稿箱要的 HTML（标题、表格、列表、代码块、加粗、引用）
- 自动上传正文图片，封面自动作为缩略图
- 自动套排版：正文 16px / 段后距 24px / 行高 1.75 / 字间距 1px，标题蓝色加粗，引用 15px，代码块灰底等宽
- 发布前先 dry-run 预览给你看，图片缺了会提醒你补，不会硬推

环境要求：Python 3.9+（脚本零依赖，只用标准库，macOS / Linux 自带）。

## 仓库结构

- `skill/wechat-draft-publisher/`：三生态通用的 skill 包（SKILL.md + scripts/ + references/），复制整个目录去安装
- `wechat_draft.py`：底层发布脚本（skill 和 CLI 共用）
- `CLI.md`：不装 skill、直接跑脚本的命令行说明
- `.env.example`：密钥配置模板

## 安装

三生态共用同一份 `skill/wechat-draft-publisher/`，只是放的地方不同。

> `mkdir -p` 只是确保目录存在：不存在就创建，已存在就跳过，**不会删除或覆盖任何已有文件**，可以放心执行。

### Codex

```bash
mkdir -p ~/.codex/skills
cp -r skill/wechat-draft-publisher ~/.codex/skills/
```

重启 Codex 后可用。

### Claude Code

```bash
mkdir -p ~/.claude/skills
cp -r skill/wechat-draft-publisher ~/.claude/skills/
```

### DeepSeek Harness

```bash
mkdir -p ~/.dsh/skills
cp -r skill/wechat-draft-publisher ~/.dsh/skills/
```

默认装在用户级目录，所有工作区可用；也可以放项目级 `<项目根>/.dsh/skills/`（项目根 = 最近的 .git 目录），仅该项目可用。放进去后 DSH 会自动发现，无需重启。

> 重复安装或升级：先删除旧目录再复制（如 `rm -rf ~/.dsh/skills/wechat-draft-publisher`），避免嵌套。三个生态都一样。

## 首次使用前的一次性配置

不管装到哪个生态，都要先做一次，三分钟：

1. **确认权限**：微信开发者平台（developers.weixin.qq.com/platform）→ 我的业务和服务 → 选择公众号 → 接口管理 → 接口权限与额度 → 服务端接口 → 草稿管理，确认已开通（需要公众号已认证，个人认证订阅号也可以）
2. **拿密钥 + 加白名单**：同一平台「基础信息」里复制 AppID / AppSecret，再把本机公网 IP 加进「IP白名单」（先跑 `python3 wechat_draft.py --check-ip` 查当前公网 IP）
3. **建 .env**（参考 `.env.example`）：

   ```
   WECHAT_APPID=你的AppID
   WECHAT_SECRET=你的AppSecret
   ```

## 怎么用

装好之后，在 AI 对话里说：

- 「发布到草稿箱 文章.md」
- 「把 文章.md 发布到草稿箱」
- 「把这篇发到公众号」

AI 会先做 dry-run 预览给你看，你确认后它才正式推送。默认只进草稿箱、不会自动群发，发布前记得自己到草稿箱预览一眼再点发布。

装好后建议先拿一篇没有正文图的 md 试一句「发布到草稿箱 xxx.md」，确认能触发，再正式用。

## 常见问题

| 问题 | 处理 |
| --- | --- |
| 报 40164 | 出口 IP 轮换了，去「基础信息 → IP白名单」重加（`--check-ip` 查当前公网 IP） |
| 报 48001 | 公众号没认证，或「草稿管理」权限没开通 |
| 报 40001 / 40125 | AppSecret 错误或已重置，重新生成并更新 .env |
| 说触发词没反应 | 检查 skill 装没装对目录，重启 AI 工具 |

## 安全

- 密钥只放 `.env`（已被 .gitignore 忽略），别发进任何聊天、文档或截图
- AppSecret 等于公众号的 API 控制权，泄露后立刻在平台重置

## 已知限制

- 需要公众号已认证，未认证号没有草稿箱接口权限
- 默认只进草稿箱，不自动群发
- 微信接口偶尔调整，如遇异常以官方文档为准

## License

MIT（见 [LICENSE](LICENSE) 文件）

---

不用 AI 工具、想直接跑脚本？见 [CLI.md](CLI.md)。
