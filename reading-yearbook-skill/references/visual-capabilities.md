# 按材料选择视觉能力

> 历史独立组图的设计资料。当前年鉴、组图和单书卡统一使用[HTML年鉴流程](html-yearbook.md)及网页内分享渲染器；不把本文的artwork、deck或确认命令作为默认要求。仅在用户明确要修改旧工程或改变当前艺术方向时定向参考。

只读需要的条目。这里是能力索引，不是版式菜单；同一种关系图可以有不同的构图。

| 材料 | 能力 | 需要什么 | 不能表达什么 |
|---|---|---|---|
| 有出处的观点、步骤、对照 | `relations` | 本页文字块、节点位置、连接依据 | 喜爱分、虚构权重、无证据的人物关系 |
| 已提供的月度时长记录 | `monthly-trace` | 数值和实际记录标记、截至日期 | 没记录的月份不能算零，也不能代表每日连读 |
| 真实逐日记录 | `calendar` | ISO日期→秒数、来源、截至日期 | 月总量或累计天数不能推导每日格子 |
| 片段、物件、个人批注 | 独立HTML/CSS编排 | 原话及真实素材 | 不强制转成图表；不需要安装图库 |

实现：[static_graphics.py](../scripts/static_graphics.py)，独立编写，没有复制Lieflat源码。方法参考Lieflat Charts的单位对应、内容旁注和静态SVG组织；原库提交`eace082a317b696c5570c25826a53a7fa113e984`采用PolyForm Noncommercial 1.0.0，如另行复制代码需遵循原许可。

## 接入

在本页`graphics`登记规格。解释性图解的节点用`block_id`绑定本页内容块，连接用`source_refs`记录依据。节点由助手针对材料设置`x/y/width/height`，位置和大小只是编排，不代表数值。

```json
{"id":"decision-path","kind":"relations","font_size":36,
 "nodes":[{"id":"a","block_id":"hypothesis","x":12,"y":16,"width":300,"height":160},
          {"id":"b","block_id":"counter-evidence","x":432,"y":160,"width":330,"height":190}],
 "edges":[{"from":"a","to":"b","source_refs":["book-id/highlight/source-id"]}]}
```

这是字段示意，必须替换成当前真实内容。节点文字不重复放进HTML；SVG里的`data-block`已参与校对。图解需配可见的“依据所选片段整理”等说明，不冒充全书结论。

统计图通过`source_ref`读取`job.sources[ref].value`。月度来源是`{"seconds":[12个数值],"observed":[12个布尔值]}`；标记只说明提供过记录，不承诺完整覆盖。日历来源是`{"2026-01-01":3600,"2026-01-02":0}`；未提供的日期为缺失，null也是缺失。`period.as_of`之后为未到日期，不允许带未来数值。

在builder里调用：

```python
from static_graphics import render_graphic
svg = render_graphic(job, page_id, graphic_id, 780, 420)
```

也可用CLI产生片段，再内联进`deck.html`：

```powershell
python -X utf8 scripts/static_graphics.py --job output/share/share-job.json --page overview --graphic monthly-track --width 780 --height 420 --output output/share/monthly.svg
```

图形沿用本次艺术简报的`--chart-ink/muted/accent/paper/line`颜色角色。可以传hex色值的`palette`字典，不提供固定主题。字体继承本页，轴与注释起点28px；900px画布的主要图解节点建议36–42px，实际查看375px预览。图形不能再缩小塞进窄栏；放不下先重排或删减。

## 静态完成协议

SVG内联在本页，用`data-graphic="规格ID" data-ready="true"`登记。就绪表示图形已经画完，不能提前标记。动态生成时实现`window.renderForExport(ids)`，主动绘制指定页并返回Promise；结束时设置就绪。导出会调用它，再等待字体、图片和两帧布局，并检查图形是否有可见形状。只关动画不保证滚动图已画完。

所有SVG可见文字都须有`data-block`或`data-label`（继承带标记的SVG容器也可）。数值仍要核对单位、比例和来源；技术校验不证明解释性关系正确或作品好看。
