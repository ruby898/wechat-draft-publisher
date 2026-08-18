# 排障与参考

## 报错对照

| 报错 | 原因 | 解决 |
| --- | --- | --- |
| 40164 | IP 不在白名单 | 先 `python3 wechat_draft.py --check-ip` 看当前公网 IP，去微信开发者平台「基础信息 → IP白名单」重新加。运营商 NAT 的出口 IP 会轮换，变了就重加 |
| 48001 | 接口未授权 | 公众号没认证，或「接口管理 → 接口权限与额度 → 服务端接口 → 草稿管理」未开通 |
| 40001 / 40125 | AppSecret 错误或已重置 | 重新生成 AppSecret 并更新 .env |
| 找不到封面图 | assets 里没有封面 | 放一张 `cover-wechat.png` / `cover.png`，或用 `--cover` 指定 |

## 排版参数（默认值，可命令行覆盖）

| 元素 | 参数 |
| --- | --- |
| 正文 | 字号 16px、段后距 24px、行高 1.75、字间距 1px |
| 标题 | 16px，蓝色加粗，靠段距分层级 |
| 引用 | 15px |
| 代码块 | 灰底、等宽字体、圆角、保留换行 |
| 表格 | 14px、单元格内边距 8px、细边框 |
| 图片 | 块级居中，上下留白 |
| 分割线 | 「写在最后」小节前自动加细灰线 |

命令行覆盖：`--font-size` / `--line-height` / `--letter-spacing` / `--para-margin`

## 微信开发者平台路径速查

- AppID / AppSecret / IP 白名单：微信开发者平台（developers.weixin.qq.com/platform）→ 我的业务和服务 → 选择公众号 → 基础信息
- 草稿箱接口权限：同上 → 接口管理 → 接口权限与额度 → 服务端接口 → 草稿管理

## 正文格式约定

- 图片占位：`【截图：说明 — assets/xxx.png】` / `【配图：说明 — assets/xxx.png】`，assets 相对 md 文件所在目录
- 封面：`assets/cover-wechat.png` 或 `assets/cover.png`，自动用作缩略图，不放进正文
- 代码块用 ```text 围栏，块内换行原样保留
