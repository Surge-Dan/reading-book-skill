# 年年阅优化：参考资料与借鉴判断

检索日期：2026-09-30。当前项目基线：`d6bdd29`。本文件记录研究依据，不是已确认的实施方案。

## 已确认的产品目标

- 首要价值：记录与分享，优先改善年报视觉、卡片和生成体验。
- 首要场景：小红书图文，一套封面与内页，面向陌生读者讲清年度阅读亮点。
- 完整私人档案继续保留。

## 检索边界

已检索 GitHub 的微信读书 Skill、小红书卡片 Skill、年度回顾项目，并读取下列源文件。另通过公开搜索检索小红书年度读书总结，但未获得可核实的具体笔记正文或互动数据；不能据此判断用户偏好、传播效果或平台推荐规律。GitHub 项目存在、源文件可读，不等于已在本机验证可运行。

只借鉴方法与接口约定，不直接复制第三方代码或视觉资产。若后续需要复用代码，另行核对文件许可证。GitHub 星标和安装量不作为方案有效性的证明。

## 参考与取舍

### 1. 腾讯官方微信读书 Skills：数据来源与版本契约

- 来源：[Tencent/WeChatReading README](https://github.com/Tencent/WeChatReading/blob/main/README.md)。
- 已读事实：提供搜索、书架、笔记、统计等能力，API Key 通过环境变量配置；当前公开 README 版本为 `1.0.4`，接口通过 `upgrade_info` 提示升级。
- 可借鉴：持续以官方契约核对年度指标的来源与单位；保留真实、样例、不完整状态。
- 不宜扩展：本轮不新增账号、云端同步或全文抓取。当前项目已有数据适配器，优先修复分享链路。

### 2. 花叔微信读书顾问：先确定发布场景，再组织复盘

- 来源：[SKILL.md](https://github.com/alchaincyf/huashu-weread/blob/main/SKILL.md)、[review.md](https://github.com/alchaincyf/huashu-weread/blob/main/workflows/review.md)。
- 已读事实：交叉使用书架与笔记；按平台确定文章形态；用具体数字反差和少数代表书组织复盘；按数据稀疏情况降级。
- 可借鉴：每张分享卡回答一个读者能理解的问题；用有证据的阅读亮点组织故事，而不是直接展示内部评分。
- 不照搬：原文件中的“笔记数代表真读过”、95% 完成阈值、周期示例参数和“9 图为佳”属于该项目规则或建议，不是已验证事实。本项目继续保留严格年度归属，阅读少不等于没有价值，页数按素材决定。

### 3. 小红书文章卡片：结构、视觉与渲染验收分开

- 来源：[SKILL.md](https://github.com/qianjiazheng2023/xiaohongshu-article-cards/blob/main/SKILL.md)、[图片生成规范](https://github.com/qianjiazheng2023/xiaohongshu-article-cards/blob/main/references/image-generation.md)、[拆分规则](https://github.com/qianjiazheng2023/xiaohongshu-article-cards/blob/main/references/content-fidelity.md)、[布局检查脚本](https://github.com/qianjiazheng2023/xiaohongshu-article-cards/blob/main/scripts/check_card_layout.mjs)。
- 已读事实：先确认逐页结构；先试做封面与内容页；HTML 渲染前等待字体、图片；通过元素边界检查溢出与裁切，配合实际 PNG 目检。
- 可借鉴：新增逐页内容清单、封面与典型内页预览、渲染布局验收；局部修改只重做受影响页面。
- 不照搬：100% 保留原文不适用于精选年报；异常空白比例不是普适审美标准；其多阶段确认会增加操作成本，本项目应合并确认。

### 4. 小红书概念卡片：整套视觉一致、每页一个重点

- 来源：[create-xiaohongshu-concept-cards/SKILL.md](https://github.com/MUZI-LYY/create-xiaohongshu-concept-cards/blob/main/SKILL.md)。
- 已读事实：使用 3:4 页面；每页一个视觉想法；统一字体、页边距、角标与强调色；保留修改版本。
- 可借鉴：建立全套卡片的文字层级与边距规则，封面突出主题，内页逐页推进，保留确认版本。
- 不照搬：AI 概念题材、固定银灰橙配色、个人品牌角标与图片生成工作流。年年阅继续优先用可编辑 HTML 生成有准确文字的卡片。

### 5. Wrapperr：年度回顾的数据与呈现分离

- 来源：[aunefyren/wrapperr README](https://github.com/aunefyren/wrapperr/blob/main/README.md)。
- 已读事实：把指定时段的 Plex 使用统计加工为互动回顾，支持可配置文字、外观、结果，以及预缓存。
- 可借鉴：稳定数据层与分享呈现分离；预检依赖、缓存中间产物，减少等待与重跑。
- 不照搬：服务端部署、Plex 认证、管理员后台、公开分享链接，以及其推测用户年龄的功能。

### 6. grill-me / grilling：逐层查清关键决策

- 来源：[mattpocock grill-me](https://github.com/mattpocock/skills/blob/main/skills/productivity/grill-me/SKILL.md)、[grilling](https://github.com/mattpocock/skills/blob/main/skills/productivity/grilling/SKILL.md)。另读取了 [RobMitt 版本](https://github.com/RobMitt/grill-me-skill/blob/main/SKILL.md)，其采用一次一问。
- 已读事实：当前 mattpocock 版本的 grill-me 是 grilling 的入口；grilling 要求沿决策树追问，把可查证事实留给工具调查，把方案取舍交给用户。
- 本轮应用：先确定核心价值、分享场景，再确定内容重点、视觉方向和可接受的操作成本，最后比较方案与确定实施边界。结合 brainstorming 保持问题逐个推进。

## 对当前项目的直接启发

1. 从“内部阅读档案自动排版”转向“完整档案 + 精选分享卡组”，两者共享同一份可信数据。
2. 卡片先明确读者、页序与一个重点，再选择版式。按书籍类别分配三种版式不足以决定分享故事。
3. `E0–E3`、来源 ID、内部评分保留在私人档案与验证报告；分享图呈现自然语言信息与必要的样例/草稿标记。
4. Skill 运行于宿主 AI Agent；语义编排可以由宿主模型完成，不必先增加独立模型 API、密钥和调用成本。问题在于目前缺少明确的内容编排指令、输入输出契约与验证闭环。
5. 优先补齐字体与图片等待、长书名和长引用适配、实际图像验收，避免“PNG 文件存在且尺寸正确”被当作视觉质量合格。
6. 将人工编辑 `selection.json` 转为 Agent 根据用户明确选择写入确认记录，降低生成摩擦，同时保留审计信息。

## 2026-09-30 头脑风暴确认的取舍

以下记录当时决定。2026-10-01 用户进一步要求视觉优先、风格开放与 Skill 成本管理；固定暖纸与年轮不再作为普遍要求，完整档案按需执行。当前判断见 [第二轮研究](2026-10-01-visual-design-and-skill-efficiency.md) 和修订后的改进说明。

- 内容主线：精选书单 + 我的理由；年度数据负责开场，代表书和真实感受承载主要内容。
- 个人感受选填：先整理已有笔记，缺少时邀请补一句；用户可跳过，不代写其感受。
- 视觉：现代阅读杂志，有创意、不规律、不模板化；好看优雅，排版自然、合理、协调。
- 设计方法：统一纸张、字体、墨色与年轮的品牌语言；内容决定构图，允许非对称、跨栏、错位、大小对比和疏密变化。
- 默认两次确认：先确认精选书、个人感受和逐页内容，再确认封面 + 一张典型内页的视觉，之后完成整套。
- 本轮先用文字确定方向；视觉样张安排在改进方案确认后的实施阶段。

页数、具体交付规格、工程机制和验收目标作为改进说明中的建议提交审阅，尚不视为已确认的实施要求。

改进说明：[2026-09-30-reading-yearbook-improvement-design.md](../superpowers/specs/2026-09-30-reading-yearbook-improvement-design.md)。
