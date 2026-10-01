---
name: reading-yearbook-skill
description: Design shareable reading yearbooks, book-list images, and single-book cards from WeRead records or existing reading notes, especially 小红书年度阅读分享. Use for 阅读年报、书单图文、单书卡 or revisions to them; also supports a local reading atlas and legal-full-text distillation when explicitly requested. Do not infer a whole book from sparse notes or download book contents.
---

# 年年阅

把真实阅读材料做成愿意分享的图片。默认精选书单与个人理由；感受可跳过，不代写经历。风格由材料与用户偏好决定，不固定颜色、字体、图案或版式。

## 路由

- 新建年报、书单或单书分享：读 [艺术指导](references/art-direction.md) 和 [分享操作](references/share-workflow.md)。
- 改一页：只读现有简报、该页内容与分享操作的修订段，不重跑调研或采集。
- 真实数据尚未采集：才读 [微信读书接口](references/weread-api.md)。已有数据直接复用。
- 用户明确要完整私人档案或图谱：读 [档案交付](references/output-contract.md)，使用原 `run_yearbook.py`；不默认扩展分享任务。
- 用户提供合法全文并明确要深挖：读 [深度蒸馏](references/distillation-method.md)。
- 调整原始数据字段时才读 [数据契约](references/data-contract.md)；证据分级细节见 [证据规则](references/evidence-rules.md)。

## 默认分享流程

1. 复用材料，明确年份与分享范围。用脚本准备精简任务；只加载精选材料，研究全文、全书档案与其他 Skill 不默认加载。
2. 提出书目、短文与一个艺术方向，用户确认一次。用户原话、引用、编辑归纳、补充感受分别记录。助手维护文件，用户不用编辑 JSON。
3. 写一份静态 `deck.html`，先导出封面与代表内页的真实图片，用户再确认一次。
4. 完成剩余页并检查实际图像，交付编号 PNG、可编辑源与短发布文案。普通卡组建议 4–6 页，单书可更少，内容不足不凑页。

## 常用命令

在 Skill 目录执行。Windows 使用 `python -X utf8`。后续确认与导出命令见分享操作，不必读脚本源码。

```powershell
python -X utf8 scripts/run_share.py prepare --year 2026 --input assets/sample-data.json --output output/share-2026
python -X utf8 scripts/run_share.py status output/share-2026
```

分享 PNG 使用已有 Node Playwright 与 Chromium，可传入现有运行时路径；不自动安装，缺失时保留 HTML 并报告 `unavailable`。

## 不可跨越的边界

- 引用保留来源与原文；材料稀少时缩短表达，不凭模型记忆补全全书。
- 不下载整本书，不上传用户数据，不自动发布。Key 只来自环境变量，不进对话、参数或交付。
- 样例每页标明样例；本年记录标明截至日期。真实采集不完整只保留草稿。
- PNG 必须与当前内容、素材及页面版本一致。失败保留此前有效图片，不能借旧图或 HTML 成功宣称完成。

## 成本边界

默认一个方向、单个助手，不串联设计／头脑风暴／去 AI 味 Skill。确定性工作交给脚本；改一页只处理受影响页。素材检索、生图、多方向与更多页数需要说明增量成本；一次针对性修复仍失败时保留草稿并说明原因。只报告实测耗时和重绘数量，不编造 token 节省比例。
