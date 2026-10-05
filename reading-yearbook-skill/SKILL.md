---
name: reading-yearbook-skill
description: Create offline HTML reading yearbooks with real reading statistics, book distribution, timeline, notes, highlights, personal notes and share-image exports. Use for 阅读年报、年度阅读档案、小红书读书组图、书单 or 单书卡. Keep excerpts and personal notes distinct; adapt gracefully to empty or incomplete records.
---

# 年年阅

把真实阅读材料整理成可浏览、可探索、可导出的HTML年鉴；精选组图是分享出口。用户只要组图或单卡时按其范围交付。风格由材料与偏好决定，不把示例字体、配色或布局设成唯一风格。

## 路由

- 默认交付HTML阅读年鉴：用户安装Skill并接入有效微信读书接口后，助手完成采集、材料核查、视觉制作和导出验证，给出完整单文件网页；不让用户准备JSON或执行脚本。只读[HTML年鉴操作](references/html-yearbook.md)，运行`generate_reading_html.py`；已有材料先复用。年份未指定默认本年并说明，已有认可方向直接实现；用户提出新的视觉要求时才集中对齐。独立组图／单书卡按其明确范围交付。
- HTML图表按数据问题从lieflat-charts真实gallery选型，不只模仿外观。当前示例含细线、分类阶梯、逐书刻度与滚入／重播动画；用户指定参考图时连同字体、原创素材、纸面层次和实际导出一起还原。缺少逐日数据不制作每日热力图。
- 没有划线或个人笔记是正常阅读状态，不阻止网页交付。仅有笔记时展示个人想法；都没有时展示书架、真实统计及温和提示，分享转为书封与阅读信息卡。请求失败必须标为未取得，不能伪装成零记录。缺时间数据不猜测时间线，零书目也有可用的空年鉴。生成书评与自动全文检索已从HTML流程移除。
- 完整HTML先补齐每本已确认书籍的真实封面、当前进度、完整划线和个人想法；组图中的精选摘录不能代替完整采集。正式生成用`--require-all-covers`。核查后为零与采集失败分开显示；年度汇总和当前阅读进度分别保留口径。
- 只做书单或单书分享：读 [艺术指导](references/art-direction.md) 和 [分享操作](references/share-workflow.md)。
- 用户选择拼贴时才读[拼贴方法](references/collage-method.md)；需要选字或换字时读[字体方法](references/typography.md)。不一次加载字体库或所有风格说明。
- 改一页：只读现有简报、该页内容与分享操作的修订段，不重跑调研或采集。
- 真实数据尚未采集：才读 [微信读书接口](references/weread-api.md)。已有数据直接复用。
- 用户明确要完整私人档案或图谱：读 [档案交付](references/output-contract.md)，使用原 `run_yearbook.py`；不默认扩展分享任务。
- 调整原始数据字段时才读 [数据契约](references/data-contract.md)；证据分级细节见 [证据规则](references/evidence-rules.md)。

## 三个确认点

以下适用于独立组图任务；HTML走自己的数据与视觉校准流程，导出组图前仍须确认图片比例。已明确或本次已认可的信息不重复询问。

1. **范围**：复用材料，集中确认发布场景、时间范围、产物、比例、候选书目及张数。助手提出选书理由，用户选择；建议3–5本，不按阅读时长推断喜爱程度。比例须在本次任务明确，提供1:1、3:4、4:5或自定义；“做张年报图”等含糊表达先问单图还是组图。已明确的信息不再问。
2. **内容与方向**：展示全部分镜：每页阅读任务、证据、主视觉及含义、辅助内容和取舍，再给逐页文字。用少量参考提出两个具体视觉方向，说明字体和图文关系，用户选一个。原话、引文、编辑归纳和补充想法区分记录；只有划线不能冒写个人收获。缺少观点时集中追问，或确认换书／转为摘录表达。未确认前不制作正式样张。
3. **实际样张**：按选定方向导出封面、年度概览和内容结构不同的代表书卡，展示原图及375px宽阅读预览，确认实际字体、图表、构图和密度。通常选两种书卡；材料只有一种结构或单书／单图时减少，不能为凑样张扩页。未认可不扩展剩余页。

确认后完成其余页，检查整组实际图片，交付编号PNG、组图预览、可编辑源与实际素材；发布文案按需附上。用户明确只要单图或单书卡时遵循其范围。内容不足不凑页，比例改变重新组织版面，不机械裁切。

每个确认绑定本次已展示版本与用户实际回复。历史审美偏好不能代替当前方案的认可，“继续”只适用于用户已见且明确同意的范围；脚本不能自行推断同意。助手维护文件，用户不用编辑JSON。

需要统计或内容图解时，才读[视觉能力索引](references/visual-capabilities.md)，定向使用静态SVG。图解依据片段组织关系，不加虚构分值；每本书的版式随问题和材料变化，不按书籍类别套版。书籍物件、证据、图解与旁注共同形成层次，不能只换色或放大一句话。

新任务使用`material-led`：从精选材料提出逐页主意象、实际素材、字样和阅读路径，写入`artwork`；脚本只整理材料与校验，不按书名分类选模板。任意书目都可走这条流程；缺少照片可用原创物件或字样，缺少观点则收窄表达。换书不能只替换标题；同一本书的不同笔记也可能形成不同视觉方向。

## 常用命令

在 Skill 目录执行。Windows 使用 `python -X utf8`。后续确认与导出命令见分享操作，不必读脚本源码。

```powershell
python -X utf8 scripts/generate_reading_html.py --year 2026 --output output/reading-2026/index.html
python -X utf8 scripts/run_share.py prepare --year 2026 --input assets/sample-data.json --output output/share-2026
python -X utf8 scripts/run_share.py status output/share-2026
python -X utf8 scripts/art_direction.py --job output/share-2026/share-job.json --output output/share-2026/design-packet.json
```

分享 PNG 使用已有 Node Playwright 与 Chromium，可传入现有运行时路径；不自动安装，缺失时保留 HTML 并报告 `unavailable`。

## 不可跨越的边界

- 引用保留来源与原文；材料稀少时缩短表达，不凭模型记忆补全全书。
- 不上传用户数据，不自动发布。Key只来自环境变量，不进对话、参数或交付。完整正文仅从有访问依据的来源取得，存放私人目录，不嵌入HTML、JSON或Markdown。
- 样例明确标注；年鉴时间范围说明一次，采集日期集中放数据来源。真实采集不完整须标明覆盖；不能把已载入书目等同全年总量。
- PNG 必须与当前内容、素材及页面版本一致。失败保留此前有效图片，不能借旧图或 HTML 成功宣称完成。

## 成本边界

默认单个助手，不串联设计／头脑风暴／去AI味Skill。只加载当前流程需要的参考和精选材料；已有数据不重采。两个方向用有范围的参考与短说明，选定后只做一套样张，不生成两套成品。确定性工作交给脚本，修订只处理受影响页；生图、扩大调研或增加版本先说明成本。一次有依据的技术修复仍失败就报告阻碍；用户明确的设计反馈可继续处理，不自行循环重设计。只报告实测耗时和重绘数量，不编造token节省比例。
