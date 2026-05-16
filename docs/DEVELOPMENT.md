# 开发指南

## 改 prompt

L1 抽取的 prompt 在 `prompts/`,可独立编辑:

- `prompts/l1_extract.md` — L1.1 generate 用
- `prompts/l1_review.md` — L1.2 clean 用
- `prompts/l2_synthesize.md` — L2(待开发)

改完不用重装项目,直接跑下一次 digest 就生效(prompt 是运行时读)。

## 加新项目

`config.yaml` 加一项:

```yaml
projects:
  my-project:
    root: /Users/edy/project/my-project
    description: ...
```

然后:
```bash
sm extract my-project
sm digest my-project
```

数据自动落在 `data/sessions/my-project/` 等子目录。

## 验证改动

改了 extract/digest 模块后,挑一个 session 跑单文件验证:

```bash
# 待办:目前还没单文件入口,只能跑整个项目
# 临时方案:在 tmp/ 下软链接 session yaml,改 config 加个临时小项目
```

未来加 `sm extract --file <path>` 单文件模式。

## 调试失败

L1.1 / L1.2 失败时,raw 输出会保存到 `tmp/l1_raw_*_<stem>_<reason>.txt`。
排查时直接打开看。

## 加新流水线层

例如加 L2 synthesize:
1. 在 `src/session_memory/synthesize/` 下加模块
2. `cli.py` 的 `synthesize` 命令改成实际调用
3. 在 `prompts/` 加 `l2_synthesize.md`

## 测试

V1 暂无单元测试。等核心流程稳定后会加 pytest。
