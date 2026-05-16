# 架构

## 流水线

```
L0   原始 session 文件
     ~/.claude/projects/<project>/<sid>.jsonl
     ~/.codex/sessions/YYYY/MM/DD/rollout-...jsonl
                  ↓
L0.5 规则预处理(无 AI,纯 Python)
     · 找所有 cwd 在指定项目下的 session
     · 砍 tool_use / tool_result / thinking / attachment / 等噪音
     · 保留 user 输入 + AI 最终回复(Claude 看 stop_reason=end_turn
       Codex 看 task_started~task_complete 配对识别 final)
     · 输出:data/sessions/<project>/<时间>-<source>-<sid前8>.yaml
                  ↓
L1.1 抽取 generate(opus,并行)
     · 把 session yaml 整段塞 opus(prompt 见 prompts/l1_extract.md)
     · 类型分级:discussion / mixed / development / chitchat
     · 输出 JSON 强约束(避免 yaml 引号歧义),Python 端转 yaml
     · 字段:topics / summary / decisions / actions_done /
              involved_modules / status / open_threads / risks
     · 输出:data/digests/raw/<project>/<同名>.digest.yaml
                  ↓
L1.2 清洁 clean(opus,并行)
     · 第二次调用 opus,专做"翻译技术词→业务语言"
     · prompt 见 prompts/l1_review.md
     · 输入:L1.1 的 raw digest
     · 输出:data/digests/cleaned/<project>/<同名>.digest.yaml
                  ↓
L2   项目合成(待开发)
     · 把同项目所有 cleaned digest 喂 opus 一次
     · 跨 session 合成业务事件卡(M 张卡,涉及 N 个 session)
     · 输出:data/events/<project>/
```

## 关键设计

### 为什么 L1 拆两次调用(generate + clean)

实测发现:
- 一次调用同时背"业务总结 + 语言清洁"两个目标会两边不到位
- generate 让 opus 专心信息完整;clean 专心翻译技术词
- 单次质量 8.5/10,双调用 9/10

### 为什么 L0.5 砍工具调用

用户视角不关心 AI 跑了哪些命令,关心"做了什么决策、有什么业务影响"。
工具调用占原文件 60-80% 体积,砍掉后约 2-5% 留存率。

### 为什么 LLM 输出 JSON 而非 YAML

YAML 太宽容,LLM 写时容易出现引号歧义(`- "A"B,C"` 这种)、缩进不一致等。
JSON 严格,LLM 偶尔忘转义 `\"` 容易调试。中文引号用全角 `「」` 规避。

### 为什么 cwd 既要保留又要去重

cwd 是项目识别的关键信号(Claude 的 worktree 切换、Codex 的 turn_context.cwd)。
但每条 message 都印 cwd 太冗余,所以顶层 initial_cwd + 只在变化时标。

## 文件大小参考(以 party 项目为例)

| 阶段 | 大小 | 文件数 |
|---|---|---|
| L0 原始 jsonl | ~360 MB | 306 个 |
| L0.5 sessions/ | ~7 MB(2%) | 283 个 yaml |
| L1.1 digests/raw/ | ~2 MB | 283 个 |
| L1.2 digests/cleaned/ | ~2 MB | 283 个 |

## 模型选择

L1 默认用 opus(详细完整,产品语言较好)。
sonnet 也可以(快一些,但泄漏稍多)。
通过 `sm digest --model sonnet` 切换。
