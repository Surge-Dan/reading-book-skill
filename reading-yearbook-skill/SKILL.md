---
name: reading-yearbook-skill
description: Turn one natural year of WeRead bookshelf, progress, reading statistics, highlights, and personal thoughts into an evidence-backed local reading atlas, editable 3:4 yearbook cards, book profiles, and optional deep distillation from user-provided legal full text. Use when the user asks for a 微信读书年报、年度阅读总结、单书卡、阅读图谱，或用某本书的方法继续分析；do not use it to download book contents or infer a full book from sparse reading traces.
---

# 年年阅

把年度微信读书记录整理成可收藏、可浏览、可追溯的阅读档案。书目事实、用户原话与系统推断必须分开；证据不足时缩短结论，不用模型记忆补成“读过整本书”。

## 路由

- 年度年报、阅读卡组：按“年度流程”执行。
- 单本书卡：读取已有 `yearbook-data.json` 和对应档案，只生成该书卡。
- 用户提供 PDF、EPUB、TXT、MD 并要求深挖：先读 [深度蒸馏](references/distillation-method.md)。
- 需要真实微信读书数据：先读 [微信读书接口](references/weread-api.md)。
- 需要调整 schema 或排查字段：读 [数据契约](references/data-contract.md)。
- 需要改视觉或新增版式：读 [卡片系统](references/card-system.md)。

## 年度流程

1. 明确年份，按自然年处理。没有年份时只问这一项。
2. 检查 `WEREAD_API_KEY`。只读取环境变量，不让用户把 Key 写进对话、参数、日志或文件。
3. 无 Key 时主动提供样例模式；任何样例产物都标记为 `sample_verified`，不得称为用户真实年报。
4. 有 Key 时采集书架、年度统计、阅读进度、笔记本、划线与个人想法。接口部分失败时标记 `partial_unverified`，不要发布最终结论。
5. 规范化并按 [证据规则](references/evidence-rules.md) 分为 E0–E3，再计算年度代表性分。
6. 先生成 `selection-preview.md`，让用户确认前 20% 精选和 3 本年度之书候选。用户选择覆盖默认评分。
7. 确认后生成全部书籍档案、`atlas.html`、卡片 HTML 和 PNG。
8. 再让用户确认文案和直接引用；未确认时保留“草稿”状态。
9. 运行验证并报告通过、降级、失败与未实测项。输出契约见 [交付与验收](references/output-contract.md)。

## 常用命令

在 Skill 目录执行。Windows 下使用 `python -X utf8`。

```powershell
# 完整样例
python -X utf8 scripts/run_yearbook.py --year 2026 --input assets/sample-data.json --output output/2026 --export-png

# 真实数据：先采集，再生成
python -X utf8 scripts/collect_weread_data.py --year 2026 --output private/2026-raw.json
python -X utf8 scripts/run_yearbook.py --year 2026 --input private/2026-raw.json --output output/2026 --export-png

# 深度蒸馏
python -X utf8 scripts/build_deep_distill.py .\book.txt --title "书名" --output output/2026/books/book/deep --create-skill

# 复核产物
python -X utf8 scripts/validate_yearbook.py output/2026
```

PNG 导出依赖本机 Python Playwright 与 Chromium。不可用时保留可编辑 HTML，并把 PNG 状态记录为 `unavailable`，不要把 HTML 成功说成 PNG 已完成。PDF 深度解析依赖 `pypdf`；TXT/MD 与 EPUB 使用标准库。

## 不可跨越的边界

- 不下载、抓取或导出整本书正文。
- 直接引用只能来自用户划线或用户提供文本，必须保留 `source_id`。
- E0 只做书目条目；E1 只做局部轻档案；E2 才生成完整轻蒸馏；E3 必须有用户合法提供的全文。
- 不把阅读主题写成人格诊断，不生成 MBTI 式标签或无证据鸡汤。
- 不把 `implemented_unverified`、`partial_unverified` 或样例结果写成真实账号验证成功。
- 不上传用户数据，不自动发布，不替用户做年度之书的最终选择。

## 视觉判断

默认使用“书籍年轮”作为唯一视觉签名：月份弧长来自阅读投入，重要书籍节点来自评分。其余排版保持档案式克制。禁止蓝紫科技渐变、玻璃拟态、套娃圆角卡片、无意义贴纸与装饰动画。
