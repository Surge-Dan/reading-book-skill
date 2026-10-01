# 分享样例

这两组作品演示内容怎样影响构图，不是运行时套用的主题。书目、划线与笔记来自仓库的虚构样例，每页都注明样例。

| 样例 | 内容与构图 | 成品 |
|---|---|---|
| 精选书单 | 城市观察用照片全景和人脸局部；决策笔记转为大幅文字；提问页用标点组织重心 | [四页预览](share-demo/overview.png) · [源文件](share-demo/deck.html) |
| 植物单书 | 杏色、暗红与原创植物剪影；只有简介和划线，不补写个人感受 | [两页预览](botanical-demo/overview.png) · [源文件](botanical-demo/deck.html) |

书单照片：[Atget, Joueur d'orgue, Art Institute of Chicago](https://www.artic.edu/artworks/55394)，1898/99；官方 API 标记 `is_public_domain=true`。它是配图，不是书封或书内插图。植物 SVG 为原创形态示意，不代表真实植物标本。

每组目录包含 `share-job.json`、`deck.html`、`assets/`、编号 PNG、`overview.png`、`caption.md` 与验证报告。确认记录使用 `sample-test`，不是用户对新增作品的确认。

重建时使用空目录，避免覆盖已有作品：

```powershell
python -X utf8 examples/build_share_demo.py --output output/share-demo
python -X utf8 examples/build_botanical_demo.py --output output/botanical-demo
```

然后按 [分享操作](../references/share-workflow.md) 记录样例技术确认并导出。这两个 builder 只重建对应实例；默认分享 CLI 不调用它们。

`visual-proof/` 保留被否定的第一轮试稿；`visual-proof-v2/` 保留获认可的第二轮两页试稿，供研究追溯。
