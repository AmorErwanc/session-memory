# Digest Schema

L1 产出的 digest 按 session 类型分级。type 字段决定有哪些字段。

## 公共字段(所有 type 都有)

| 字段 | 类型 | 含义 |
|---|---|---|
| `session_id` | string | 来源 session UUID |
| `source` | "claude" / "codex" | 原始 CLI |
| `file` | string | 原始 jsonl 绝对路径 |
| `started_at` | ISO 时间 | 第一条消息时间 |
| `ended_at` | ISO 时间 | 最后一条消息时间 |
| `cwd` | string | 工作目录 |
| `type` | enum | discussion / mixed / development / chitchat |
| `topics` | array of string | 3-4 个业务化短词 |

## 按 type 的额外字段

### `discussion` 纯讨论(重点记)

| 字段 | 含义 |
|---|---|
| `summary` | 长段叙事,产品语言。讲来龙去脉 |
| `decisions` | 拍板的策略/方案/原则 |
| `open_questions` | 还没拍板的问题 |
| `status` | done / in_progress / blocked / unclear |
| `open_threads` | 没收口的事 |
| `risks` | 业务方/用户能感知的风险 |

### `mixed` 讨论 + 落地

| 字段 | 含义 |
|---|---|
| `summary` | 主线讲讨论 + 一句话提落地 |
| `decisions` | 拍板的策略 |
| `actions_done` | 已完成的具体落地(跟 decisions 不重复) |
| `involved_modules` | 涉及的功能模块(业务名,不是文件名) |
| `status` / `open_threads` / `risks` | 同 discussion |

### `development` 纯开发(简单记)

| 字段 | 含义 |
|---|---|
| `one_line` | 一句话 40-60 字 |
| `involved_modules` | 涉及的功能模块 |
| `status` | 同上 |

### `chitchat` 项目下杂聊(简单记)

| 字段 | 含义 |
|---|---|
| `one_line` | 一句话讲在聊什么(不强求产品语言) |

## 三信号位

视图层会重点展示这三个字段(对应 V0.2 工作台的"三信号位"):

- **status** — 这件事做完没
- **open_threads** — 还挂着什么
- **risks** — 有什么风险

## 产品语言规则

写产品语言字段(summary/decisions/actions_done 等)时:
- ✅ 主语用业务角色:玩家 / 用户 / 运营 / 创作者 / 客户
- ✅ 描述能被业务方感知的体验/能力变化
- ✅ 通用技术名词可保留:WebSocket / API / 数据库 / 缓存 / 接口 / 测试
- ❌ 函数名 / 类名 / 内部模块名 / 文件路径 / 代码细节 / 变量名

详细见 [prompts/l1_extract.md](../prompts/l1_extract.md)。
