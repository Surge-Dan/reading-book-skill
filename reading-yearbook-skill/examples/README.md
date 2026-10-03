# 分享样例

新版的材料驱动练习见[material-led-cases.json](material-led-cases.json)：同一本虚构书的两条不同笔记，以及一个陌生领域的长书名。它们展示材料如何改变主意象、字样与阅读路径，既不是分类映射，也不是成品。新工作流使用[艺术指导](../references/art-direction.md)的逐页`artwork`；以下旧实例保留兼容契约，不自动套用到新书。

这些作品演示内容怎样影响构图，不是运行时套用的主题。书目、划线与笔记来自仓库的虚构样例，每页都注明样例。最新的阅读展览演示逐页分镜、不同书卡结构和静态SVG校对；早期样例保留作过程参考。

| 样例 | 内容与构图 | 成品 |
|---|---|---|
| 阅读展览 | 六页分别组织书册陈列、记录轨迹、摄影观察、决策关系、提问路径与植物意象 | [六页预览](exhibition-demo/overview.png) · [源文件](exhibition-demo/deck.html) |
| 精选书单 | 城市观察用照片全景和人脸局部；决策笔记转为大幅文字；提问页用标点组织重心 | [四页预览](share-demo/overview.png) · [源文件](share-demo/deck.html) |
| 植物单书 | 杏色、暗红与原创植物剪影；只有简介和划线，不补写个人感受 | [两页预览](botanical-demo/overview.png) · [源文件](botanical-demo/deck.html) |

书单照片：[Atget, Joueur d'orgue, Art Institute of Chicago](https://www.artic.edu/artworks/55394)，1898/99；官方 API 标记 `is_public_domain=true`。它是配图，不是书封或书内插图。植物 SVG 为原创形态示意，不代表真实植物标本。

每组目录包含 `share-job.json`、`deck.html`、`assets/`、编号 PNG、`overview.png`、`caption.md` 与验证报告。确认记录使用 `sample-test`，不是用户对新增作品的确认。

重建时使用空目录，避免覆盖已有作品：

```powershell
python -X utf8 examples/build_share_demo.py --output output/share-demo
python -X utf8 examples/build_botanical_demo.py --output output/botanical-demo
python -X utf8 examples/build_exhibition_demo.py --output output/exhibition-demo
```

然后按 [分享操作](../references/share-workflow.md) 记录样例技术确认并导出。这些builder只重建对应实例；默认分享CLI不调用它们。阅读展览样例的年度是虚构完整年度，不代表用户截至目前的真实记录。

新版builder生成`share-3`任务，明确填写分镜、3:4比例和技术方向。重建时依次执行`approve-scope --sample-test`、`approve-content --sample-test`、`preview`、`approve-visual --sample-test`、`finalize`。旧成品保留为过程参考，不补写新版历史确认。

`workflow_fixture.py --output output/workflow-test --ratio 1:1`可建立年度三张样张与尺寸检查夹具。它是虚构材料的技术测试，不是视觉作品或默认模板；其方向字段也不冒充用户参考或认可。

`visual-proof/` 保留被否定的第一轮试稿；`visual-proof-v2/` 保留获认可的第二轮两页试稿，供研究追溯。
