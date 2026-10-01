# 分享操作与交付

由助手执行，用户在对话里确认，不要求用户编辑文件。脚本不写创意文案、不选固定版式，也不代替用户授权。

## 1. 准备内容

```powershell
python -X utf8 scripts/run_share.py prepare --year 2026 --input assets/sample-data.json --output output/share-2026 --books sample-002 sample-001 sample-005
```

也接收已有 `yearbook-data.json`；不重复采集。省略 `--books` 只提出最多三本候选，不是用户的最终选择。零数据返回 `empty`，不拼凑年报。

读输出的 `share-job.json`，不读整份原始响应。每本默认最多保留两条划线与两条想法，每条最多 800 字；截断字段明确标记，只能作归纳，不能假装完整引文。需要其他条目时，从已有材料定向取出并保留来源，不重新请求所有数据。

助手填写短 `art_brief`、调整 `pages[].blocks` 与 `caption`，一次展示书目、文字与方向。得到用户确认后执行：

```powershell
python -X utf8 scripts/run_share.py approve-content output/share-2026
```

`--sample-test` 只用于开发样例；记录为技术测试，真实任务不能使用它。

## 2. 创作与两页预览

在输出目录写静态 `deck.html`，一份公共样式；每页是 `.page`，`id` 与任务相同，尺寸 900×1200。封面及代表内页先完成，其余页可在视觉确认后加入；公共样式尽量先确定。

- 每个内容块用 `data-block="块ID"` 标记，显示文字须与任务中的 `text` 相同，排版换行可不同。所有书名、作者、简介、引用与感受均须标记，不能绕过内容校对。
- 静态栏目／配图说明用 `data-label` 标记；每页 `data-status` 显示样例，或真实记录的截至日期。标记不显示技术 ID。
- `kind=fact/quote/thought` 绑定一个 `source_refs` 来源，文字原样保留。`editorial` 可归纳，其语义须人工核对。`user_input` 只用用户真实补充，设 `provided_by_user=true`，不得混入历史笔记。
- 素材置于目录内，用 `assets` 登记 `path/source/rights/sha256`。图片、字体、外部 CSS 须为登记的本地文件；系统本地字体可用。导出不联网取素材。注册一张图片不强迫所有页使用它。
- 相同简报内仍由每页材料决定构图；参考样例不复制成默认主题。

```powershell
python -X utf8 scripts/run_share.py preview output/share-2026
```

依赖未在 PATH 时，给 `preview/finalize` 传现有 `--node`、`--playwright-package`、`--browser` 路径。先检查现有环境；不自动下载运行时、浏览器或包。导出器等待图片解码与字体，检查文字边界、重叠和当前内容，生成两张 PNG 及 `overview.png`。

展示原图与 375px 阅读预览；视觉认可后记录：

```powershell
python -X utf8 scripts/run_share.py approve-visual output/share-2026
```

## 3. 完成与交付

补完其余 `.page`，顺序与任务一致。普通书单建议 4–6 页，单书可少；没有固定统计、年度之书或收尾栏目。两页确认绑定的是实际图片与艺术简报，加入其他页面不应改掉已确认页面。

```powershell
python -X utf8 scripts/run_share.py finalize output/share-2026
python -X utf8 scripts/run_share.py status output/share-2026
```

只有状态为 `ready/ready_sample` 才交付完整包：`share-job.json`、`deck.html`、`images/` 编号 PNG、`caption.md`、`validation-report.json`，以及实际使用的本地素材。研究全文、原始响应、Key 不复制进去。该状态不代表已发布，也不代表用户认可了开发样例里新增的文案。

## 局部修订

用户请求改字时，同步改该块 `text` 与对应 `data-block`，按照其明确请求记录新的内容确认。直接引文不能擅改；可换源或转为编辑归纳。若未改变艺术方向与确认样张，直接 `finalize`，未受影响页复用已有 PNG。任务的艺术简报或封面／代表内页改变时，先导出受影响的预览，按已有授权或用户新的认可记录视觉确认；技术修复不额外发起无必要的问答。

单页样式放在该页范围，避免为改一页改公共 CSS。公共样式、字体文件或依赖素材变了，脚本按实际影响失效缓存；不能保证仍只重绘一页。

校对失败写 `last-attempt.json`，此前有效 PNG 与报告保留；内容变动后旧图不算当前完成。成功变更把上一组图片放入 `revisions/`；纯缓存命中不额外存副本。用 `status` 复核内容、HTML、图片与发布文案，而不是相信旧的状态字段。

正常输出只给状态、重绘／复用页数和耗时。失败只读失败项，一次定向修复，不反复生成全套或长分析。技术检查不能自动判断照片选得好不好，也不能证明编辑归纳的语义或传播效果。
