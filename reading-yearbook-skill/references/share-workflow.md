# 分享操作与交付

由助手执行，用户在对话里确认，不要求用户编辑文件。脚本管理来源、范围、确认版本与画布，不选固定版式，也不代替用户授权。

## 1. 准备候选与范围确认

```powershell
python -X utf8 scripts/run_share.py prepare --year 2026 --input assets/sample-data.json --output output/share-3026 --books sample-002 sample-001 sample-005
```

也接收已有`yearbook-data.json`，不重复采集。省略`--books`只提出最多三本候选，优先有个人笔记的书，不是喜爱排名或用户最终选择。零数据返回`empty`。

默认`--format annual`，计划包含封面、年度概览和精选书卡。其他选择为`book-list`、`single-book`、`single-image`；按已确认范围选择，含糊的“年报图”先澄清。候选变化较大时在新目录复用已有输入重建，不覆盖旧任务或重新采集全量材料。

初始`canvas=null`，不替用户默认确认比例。第一轮集中确认发布场景、时间范围、产物、比例、书目和张数。根据本次选择设置，例如：

```powershell
python -X utf8 scripts/run_share.py configure output/share-3026 --ratio 3:4 --platform 小红书
```

支持1:1（900×900）、3:4（900×1200）、4:5（900×1125）；`--width`可调整分辨率并保持比例。自定义用`--ratio custom --width 1000 --height 1400`，宽高375–4096整数，更大尺寸先讨论成本。比例变更重新组织版面，不裁切或拉伸。`brief.focus`默认`reading-takeaways`，改成摘录等表达也须确认。

读输出的 `share-job.json`，不读整份原始响应。每本默认最多保留两条划线与两条想法，每条最多 800 字；截断字段明确标记，只能作归纳，不能假装完整引文。需要其他条目时，从已有材料定向取出并保留来源，不重新请求所有数据。

### 记录真实确认

用户认可当前简报后，助手写一份短JSON文件，包含实际回复或忠实摘要`reply`、可定位的用户消息ID或描述`context_ref`。不能原样写“用户已同意”作为证据，不复制完整对话或密钥。用户不用编辑文件。

```json
{"reply":"当前用户实际回复或忠实摘要","context_ref":"对应用户消息的ID或可定位描述"}
```

这是字段说明，不能直接充当确认。脚本只检查记录与版本，无法独立证明回复真实性，主持助手负责如实记录。

```powershell
python -X utf8 scripts/run_share.py approve-scope output/share-3026 --confirmation-file output/share-3026/confirm-scope.json
```

## 2. 内容与两个视觉方向

每页填写`storyboard`，完整分镜须先展示，不只展示一张封面：

```json
{"reading_task":"读者看完能理解的具体问题",
 "evidence_refs":["已登记的来源ID"],
 "main_visual":{"structure":"当前内容的结构标识","description":"主视觉及其位置、连接的含义"},
 "supporting_blocks":["本页内容块ID"],"omit":"为什么舍弃重复或不足以支持的材料"}
```

`structure`用于选取代表样张，不是书籍分类或固定模板名称；不能给相同构图改名冒充结构差异。不要机械填满辅助层次。需要图解时再读[视觉能力索引](visual-capabilities.md)，在本页`graphics`登记规格。节点、连接和统计数据均需来源；编辑归纳的语义仍须人工核对。

默认预览封面、已有概览和最多两种不同书卡结构。可用`preview_page_ids`明确选页，仍须覆盖基础角色及不同书卡；全组分镜及选页变化使内容确认失效。单图或单书不扩大范围。

助手填写`art_brief`、逐页文字和顺序，同时提出两个有参考依据的视觉方向。`directions`中每个方向包含`id`、名称`label`、具体策略`concept`、`fonts`（每项含`family/role`）、`references`（每项含实际`source/lesson`）；`selected_direction`为用户所选ID。参考与字体须实际核对，不能只填“高级、优雅”。两个方向不能仅换颜色。

新建任务保留`art_brief.workflow="material-led"`。先整理精选材料，不让脚本按书名选择风格：

```powershell
python -X utf8 scripts/art_direction.py --job output/share-3026/share-job.json --output output/share-3026/design-packet.json
```

材料包每页至多四段、每段280字；截短内容不用于直接引文。助手据此提出方向，用户选择后逐页写`artwork`，再确认完整内容。以下为字段示意，来源、块ID、字体名均要换成本页实际值，不直接充当方案或认可：

```json
{"concept":"同一对象的全景与局部并置",
 "rationale":"笔记谈到观察尺度，所以裁切服务于这个问题",
 "voice":"安静的摄影编辑与短旁注",
 "basis_refs":["本页已登记的来源ID"],
 "reading_path":["标题块","笔记块"],
 "primary":{"medium":"原创物件／照片／字样等实际形式",
            "description":"主素材、位置与裁切策略",
            "origin":"typography","asset_paths":[]},
 "layers":[{"id":"words","role":"text","purpose":"主阅读区域",
             "block_ids":["标题块","笔记块"],"asset_paths":[]}],
 "fonts":[{"family":"实际平台字族名","role":"正文与标题",
            "use_basis":"字形与当前材料的关系",
            "block_ids":["标题块","笔记块"],"fallbacks":[]}]}
```

`voice`自由描述，不是风格枚举。`basis_refs`必须属于本页内容或分镜来源。主素材的`origin`为`original/registered-assets/typography/evidence-graphic`；登记素材要写实际路径。`layers.role`为`text/material/decoration/data`，非空且与HTML一一对应。阅读路径的块要同时有图层和字体绑定；字体职责不能重复绑定同一个块。无文字素材可声明`allow_bleed=true`并写`bleed_reason`，文字和数据不可出血。

旧share-3没有这个工作流或`artwork`时保留原有契约，不补造设计决策。新的创作不通过删字段绕过材料设计。任意书名进入同一链路；材料不足就补问或收窄表达，没有照片可选原创物件或纯字体。

书卡主角是个人阅读所得时，须有真实想法、用户补充或绑定想法来源的归纳。只有划线时先追问／换书，或经确认将`brief.focus`改为`excerpts`等表达。不能将引文改写成用户经历。

用户认可逐页文字及所选方向后执行：

```powershell
python -X utf8 scripts/run_share.py approve-content output/share-3026 --confirmation-file output/share-3026/confirm-content.json
```

三个确认命令都要求各自的实际回复记录；“选方向1”不代表其他文案也认可。`--sample-test`只用于开发样例，不代表用户认可，真实任务不能用。

旧`share-1`任务保留原文件，不能补写历史认可；用已有原始／规范化输入在新目录创建`share-3`任务并重新确认范围，不重采。

## 3. 创作与真实样张

在输出目录写静态`deck.html`，一份公共样式；每页是`.page`，`id`与任务相同，宽高与`canvas`一致。年度先完成封面、概览和两种结构不同的代表书卡；其他模式按角色减少样张，其余页在视觉确认后加入。

- 每个内容块用 `data-block="块ID"` 标记，显示文字须与任务中的 `text` 相同，排版换行可不同。所有书名、作者、简介、引用与感受均须标记，不能绕过内容校对。
- 静态栏目／配图说明用 `data-label` 标记；每页 `data-status` 显示样例，或真实记录的截至日期。SVG可见文字也须标记，图形用`data-graphic/data-ready`静态完成协议；详见视觉能力索引。标记不显示技术 ID。
- `kind=fact/quote/thought` 绑定一个 `source_refs` 来源，文字原样保留。`editorial` 可归纳，其语义须人工核对。`user_input` 只用用户真实补充，设 `provided_by_user=true`，不得混入历史笔记。
- 素材置于目录内，用 `assets` 登记 `path/source/rights/sha256`。图片、字体、外部 CSS 须为登记的本地文件；系统本地字体可用。导出不联网取素材。注册一张图片不强迫所有页使用它。
- 相同简报内仍由每页材料决定构图；参考样例不复制成默认主题。
- 新工作流给实际图层加`data-layer="图层ID"`，按计划包住内容块／物件。注册了素材还要在正确图层实际使用；出血图层内不得放核心文字或图表。

```powershell
python -X utf8 scripts/run_share.py preview output/share-3026
```

依赖不在PATH时，给`preview/finalize`传现有`--node`、`--playwright-package`、`--browser`路径。先检查环境，不自动下载依赖。导出等待图片、字体就绪，检查尺寸、文字边界和当前内容；按分镜结构生成样张及375px宽的`overview.png`。按分镜选取，年度通常四张，单书通常两张，单图一张。

材料驱动页额外检查声明图层、正文绑定、计划出血、实际平台字体以及最多80个字符中心的遮挡抽样。透明图片按像素alpha检查，`pointer-events:none`不能绕过；图层、SVG、旋转／遮罩和复杂背景仍可能需要目检，报告会列出已遇到的疑点。实际图片尺寸与明显放大作为警告记录；警告不是美学结论，也不证明所有遮挡都检出。逐字内容、文字边界与数据图形仍按原规则检查。检查器版本与实际字体证据进入缓存指纹，修改检查或字形会失效旧图。

展示原图与 375px 阅读预览；视觉认可后记录：

```powershell
python -X utf8 scripts/run_share.py approve-visual output/share-3026 --confirmation-file output/share-3026/confirm-visual.json
```

历史审美偏好、HTML可打开或技术检查通过，不能代替用户对当前实际图片的认可。

## 4. 完成与交付

补完其余`.page`，顺序与任务一致。年度精选建议3–5本，加封面和概览通常5–7张，不凑页、不写死平台张数限制。其他模式按实际内容规划。样张认可绑定当前图片与艺术简报，不能在扩展时偷偷改变样张。

```powershell
python -X utf8 scripts/run_share.py finalize output/share-3026
python -X utf8 scripts/run_share.py status output/share-3026
```

只有`ready/ready_sample`才交付完整包：编号PNG、整组预览、`deck.html`、实际素材、精简任务与验证报告。需要发布文案时使用`caption.md`。不额外复制确认文件、研究全文、原始响应或密钥；技术记录中的确认摘要不用于公开发布。状态不代表已发布或用户认可技术样例。

## 局部修订

范围、画布、书目或页序变更使范围确认失效；内容或方向变更使第二个确认失效；样张或公共字体／素材改变时按实际影响更新视觉确认。

用户请求改字时同步`text`与`data-block`，将实际修改请求记录为对应内容确认，不扩大到其他未授权改动。引文不擅改；可换源或明确转为归纳。艺术方向和样张没变时可直接`finalize`，未受影响页复用。样张或艺术简报改变先展示当前图片，不能推断新的视觉认可。

单页样式放在该页范围，避免为改一页改公共 CSS。公共样式、字体文件或依赖素材变了，脚本按实际影响失效缓存；不能保证仍只重绘一页。

校对失败写 `last-attempt.json`，此前有效 PNG 与报告保留；内容变动后旧图不算当前完成。成功变更把上一组图片放入 `revisions/`；纯缓存命中不额外存副本。用 `status` 复核内容、HTML、图片与发布文案，而不是相信旧的状态字段。

报告状态、重绘／复用页数和实测耗时。失败只读失败项，一次有依据的技术修复仍失败就说明阻碍；用户明确的设计反馈可继续处理，不由助手自行循环生成全套。技术检查不能证明审美、归纳语义或传播效果。
