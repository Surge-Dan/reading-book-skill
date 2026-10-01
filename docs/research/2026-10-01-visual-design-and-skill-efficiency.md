# 视觉与 Skill 效率：第二轮研究

日期：2026-10-01。回应用户要求：视觉优先、可分享、风格开放、有艺术指导，同时控制运行时间与 token。

## 核实来源与应用

| 来源 | 实际方法 | 应用与边界 |
|---|---|---|
| [Pentagram：The Paris Review](https://www.pentagram.com/work/the-paris-review/story) | 研究历史，减少封面文案，把空间让给艺术；调整字标、开本和阅读体验 | 主角明确、周围克制，不能复制其具体艺术品和视觉身份 |
| [Butterick：排印关键规则](https://practicaltypography.com/summary-of-key-rules.html) | 字号、行距、行长、字体联动，减少多重强调 | 中文排印参与构图；英文参数不能直接套手机卡片 |
| [Anthropic frontend-design](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md) | 从题材找语言，大胆集中一处，结构承载信息，检查惯常默认 | 内容决定艺术方向；暖米色衬线、细线报纸、黑底亮色均不能成为通用答案 |
| [Baoyu cover-image](https://github.com/JimLiu/baoyu-skills/blob/main/skills/baoyu-cover-image/SKILL.md) | 分离封面类型、配色、媒介、文字密度与情绪 | 少量独立设计判断，不照搬庞大风格菜单 |
| [Baoyu xhs-images](https://github.com/JimLiu/baoyu-skills/blob/main/skills/baoyu-xhs-images/SKILL.md) | 故事、密集信息、视觉优先三策略；快速/详细路径；封面参考锚点 | 默认视觉优先，一个方向，成功页不重做；不复制固定封面到每页 |
| [Agent Skills 规范](https://agentskills.io/specification) | 元信息用于发现，入口激活时加载全文，资源按需加载，避免深引用链 | 入口短、路由精准、默认只读当前模式 |
| 本地 [skill-creator](C:/Users/22585/.codex/skills/.system/skill-creator/SKILL.md) | 只写影响决策的指导，渐进披露，执行脚本无需通读源码 | 自包含短指导，不设置一串外部 Skill 依赖 |
| 本地 [huashu-design](C:/Users/22585/.codex/skills/huashu-design/SKILL.md) | 从真实情境出发，每个元素有理由，重点细节精修，早看作品 | 采用艺术指导和批评方法；按用户成本约束缩减多方向、素材搜索流程 |

没有把第三方代码或资产复制进 Skill。网页与源文件可读不等于本机运行或传播效果已验证。Thinking with Type 页面读取超时，未作为已读依据。

## 真实版面观察

实际查看 Pentagram 页面中的封面与展开页：封面以红色樱桃画成为焦点，标题和背景让位；展开页让黑白图像与文字形成权重差异，没有切成同类卡框。

据此提炼“视觉主角、图文张力、周围克制”，不复制樱桃、字体、暖纸和对页形式。印刷展开页不能原样套手机竖图。两张案例图片只在临时目录用于观察，未纳入项目资产或用户作品。

## 蒸馏为短指导

1. 概念先于风格，从真实材料找值得看见的关系和情绪。
2. 集中一个主要视觉动作，其余元素降为配角。
3. 隐形网格、对齐和比例负责协调，构图变化负责节奏。
4. 字体、断句、行长和空白共同构图。
5. 整套有展开、停顿和收束，不强制每页不同。
6. 删除不影响理解、情绪或识别的装饰。
7. 换题后概念仍完全成立时检查泛化，不只替换书名。
8. 先用一张封面和一张内页证明品质，再完成整套。

规则、设计师姓名与自评分数不能保证伟大作品。艺术质量通过实际图像、手机尺度和用户选择验证。

## 成本取舍

普通任务只读短入口、艺术指导、交付规则。历史研究留在 docs，不进入运行上下文。模型只接收精选事实和必要片段；数据、来源核对、批量导出交给脚本，返回失败项摘要。

默认不串联研究 Skill、不启动多个设计/评审 Agent、不联网搜风格、不生成多个完整方向。共享样式复用，一次规划整套，其余页一次完成；修复只针对失败页。

复杂方向探索、生图、多页与全书分析按需选择并说明成本。没有真实 token 计数时，用读取量、调用、页数、修复与耗时代理指标，不能报告虚构节省百分比。

当前方案见 [修订改进说明](../superpowers/specs/2026-09-30-reading-yearbook-improvement-design.md)。
