# session-memory

把 Claude Code / Codex CLI 的对话历史,转成产品视角的业务事件摘要。

## 它做什么

每天用 AI CLI 工具会产生几十上百个 session 文件,内容混杂(方案讨论 / 代码实施 / 工具调用 / 杂聊),
对产品视角的复盘很不友好。

session-memory 做的事:
- 把零散的原始 jsonl 转成干净的"业务事件 digest"
- 砍掉技术噪音(工具调用、函数名、文件路径),保留业务决策和影响
- 跨 session 合成事件卡(L2,待开发)

## 快速上手

```bash
# 1. 装项目(在项目根目录)
cd /Users/edy/program/session-memory
uv tool install --editable .

# 2. 看可用项目
sm list-projects

# 3. 跑某个项目
sm extract party       # L0.5 规则预处理(无 AI,几秒)
sm digest party        # L1 抽取(opus,约 60-100 分钟)
sm status party        # 看进度

# 4. 增量跑(只跑新出现的 session)
sm extract party       # 默认增量,跑过的跳过
# 用 --force 强制全跑
```

## 命令

| 命令 | 作用 |
|---|---|
| `sm extract <project>` | L0.5:扫所有 jsonl,提取干净对话(`--force` 重跑) |
| `sm digest <project>` | L1:opus 抽取 digest(`--stage generate/clean/all`) |
| `sm synthesize <project>` | L2:跨 session 合成事件卡(待开发) |
| `sm status <project>` | 看流水线进度(各阶段产出数量) |
| `sm list-projects` | 列所有 config.yaml 中定义的项目 |
| `sm clean-tmp` | 清理 tmp/ 下 7 天前的调试文件 |

## 加新项目

编辑 `config.yaml`,加一项:

```yaml
projects:
  my-project:
    root: /Users/edy/project/my-project
    description: 项目描述
```

然后 `sm extract my-project`。

## 文档

- [架构](docs/ARCHITECTURE.md) — 流水线各层做什么、为什么这么设计
- [Schema](docs/SCHEMA.md) — digest 各字段含义
- [开发](docs/DEVELOPMENT.md) — 改 prompt / 加模块 / 跑测试

## 项目结构

```
src/session_memory/
  extract/         L0.5 规则预处理
  digest/          L1 抽取(generate + clean)
  synthesize/      L2 合成(待)
  adapters/        外部命令封装(claude -p)
  utils/           共用工具(yaml/json)
  cli.py           CLI 入口(typer)

prompts/           AI prompts(可独立编辑)
config.yaml        项目配置
data/              产出(gitignore)
tmp/               调试临时文件(gitignore)
logs/              运行日志(gitignore)
```
