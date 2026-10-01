# 第二轮样张调整依据

用户反馈：第一轮太普通、太模板化；文字刻意。保留两页验证的范围，先重做作品，不扩建生成流程。

## 实际看过的参考

| 来源 | 本次看到的内容 | 可迁移的方法 |
|---|---|---|
| [Pinterest：book design collage](https://www.pinterest.com/search/pins/?q=book%20design%20collage) | 公开搜索里显示的书籍拼贴、人物与书页组合；随后出现登录弹窗 | 图片裁切、不同材料尺度的关系；不照搬拥挤剪贴，也不将无出处的 Pin 当成可用素材 |
| [OK-RM / A Meaningful Order](https://in-other-words.co.uk/products/a-meaningful-order-by-ok-rm) | 门的照片成为书籍封面；一张内页展示封面、书脊与局部图像，各自占据不同面积 | 让具体对象承担画面，图像比例与位置跟随对象，不必让所有元素等宽或居中 |
| [Flaneur 09: Paris](https://www.flaneur-magazine.com/) | 封面使用汽车尾灯局部，多次叠印，字形跨在图像上 | 从生活细节里选主角；图与字可以有层次，但先保证辨识；不复制字标、照片和颜色 |
| [Karel Martens / Cloakroom Tickets (1-250)](https://www.romapublications.org/?book=cloakroom-tickets-1-250-karel-martens) | 出版社页面说明：在保存多年的衣帽间票据上印制单版画；缩略图可见原有编号与不同色块的叠印 | 创意可以从现成材料产生，保留它的尺度与原有痕迹；缩略图不足以验证精细排版，不作此宣称 |

Pinterest 未登录，未取得完整结果或作品出处。未使用 Pinterest 官方 API：本机没有其访问凭据。研究截图留在本机临时目录，不作为作品素材。以上案例是设计参考，不是传播效果的实证。

## 为什么第一轮不够

- 只有大宋体、错位和强调色，材料换成其他主题后构图仍然成立，缺少具体对象。
- “给判断留一点空白”是为画面造的口号，远离日常分享语气。
- 原样引用的样例笔记也未必自然；忠于来源与语言好读需要同时考虑。可以换选材料，不能擅改引文。

## 第二轮的做法

- 一个方向，两页：照片主导的编辑设计。封面“今年的书，挑几本聊聊”，书目选《缓慢的城市》《看见选择》《重新学习提问》。标题说明这篇分享要做什么，不代替用户总结人生。
- 封面让照片越过文字的区域，用图像本身的墙面、人物与空间安排标题。内页用全景与人物局部，两种尺度对应“每天经过却没有看见的路”这条笔记。
- 内页笔记完整保留 `s2-r1`，简介仅据原有介绍缩写。不替用户新增读后经历。
- 采用一张核对过的公有领域照片；它是视觉配图，不是书封、书中插图或用户照片。
- 不为改稿增加生图或多 Agent；复用现有两页渲染器，先检查和展示实际图片。

## 文案清理与 Skill 管理

已按用户要求安装 [lieflat-less-ai-tone](https://github.com/larashero3-dotcom/lieflat-less-ai-tone)，读过完整 SKILL.md。安装目录为 `C:/Users/22585/.codex/skills/lieflat-less-ai-tone`。

本次使用其白名单清理规则：不虚立误解再翻案，不用无信息的提示语，不凭空补数字或经历；引文不改。新标题的创作与简介缩写来自用户的明确改稿要求，不冒称为这个 Skill 自动清理出来的结果。

该 Skill 约 28 KB；年年阅普通任务不默认再加载它的全文。后续只将本场景必要的短规则写进艺术指导，显式要求全文清理时才调用完整 Skill。未观测到真实 token 数据，不报告节省比例。

## 素材记录

通过芝加哥艺术博物馆公开 API 找到 Jean-Eugène-Auguste Atget 的 *Joueur d'orgue (Organ Player)*，1898/99，馆藏编号 55394，`is_public_domain=true`。保留 API 返回信息、图像链接与本地文件校验值。

- [馆藏作品](https://www.artic.edu/artworks/55394)
- [官方 API 查询](https://api.artic.edu/api/v1/artworks/search?q=Eugene%20Atget&limit=6&fields=id,title,image_id,is_public_domain,artist_title,date_display,credit_line,copyright_notice)
- [官方开放使用说明](https://www.artic.edu/open-access/open-access-images)（可供复核；本次许可判断依据是实际 API 的公有领域标记）

下一步：重做两张样张并展示，视觉确认后再集成正式 Skill。第一轮未获认可，不能当作通过样例复用。
