# 彩色纸本版验收

## 已验证

- 87项既有与新增回归通过，包含启用本地Node运行时的原组图浏览器用例。
- HTML浏览器流程26项通过：1440/768/390布局、中文输入法、状态与分类筛选、详情与键盘、失败恢复、3种比例PNG、ZIP、PDF、Markdown、JSON、恶意文本与离线网络。
- 对抗场景6项通过：空数据、长分类、特殊ID、坏书封替换、失败保留选择、其他页恢复导出。
- 动态艺术图表10项通过：3张图实际CSS动画对象及重播完成、连续12次重播的取消、缩放后细线完整、阶梯本数及分数刻度精确、减少动态效果、打印最终帧、素材离线加载与零网络请求。
- 既有真实数据另验书架展开/收起、分类合计与真实划线；实际导出8张PNG、所选组图ZIP、打印PDF、Markdown和JSON。实际网页1440/768/390无横向溢出、无坏图、无运行错误。
- 人工查看桌面首屏、移动端长页、实际3:4和1:1 PNG。发现并修复缩放时取消动画导致细线停在初始帧、Canvas花体与中文标题重叠；公开示例只含示例数据。

## 范围与限制

先运行全目录unittest发现旧`test_atlas_ui.py`依赖Python版Playwright，此脚本是独立旧atlas浏览器检查而非unittest，当前环境缺该包。因此采用5个实际unittest模块的完整87项回归；新HTML使用已有Node Playwright与Edge实测。没有安装新依赖，也不将旧atlas检查记为通过。

中文字体仍优先本机Noto并保留系统回退，未内嵌可再分发中文字体子集；两个固定英文花体字样已内嵌透明图片。完整正文书评仍遵循材料门槛，这轮设计修改不新增全文或虚构书评。PDF为浏览器打印流，已验证打印最终帧与生成PDF，不声称测试过每种用户浏览器。

## 复现

1. 用`tests/test_reading_html.py`的fixture生成测试HTML，并给两本书设置真实可核验的逐书秒数；至少留一本时长未知。
2. `python -X utf8 -m unittest discover -s tests -p test_reading_html.py`。
3. 在已有Playwright的Node运行时执行`tests/reading_html_browser.cjs fixture.html output-dir`和`tests/reading_html_art.cjs fixture.html report.json`。
4. 用empty/collision/broken三个年鉴执行`tests/reading_html_edge_cases.cjs output-dir`。
5. 浏览器保持离线，查看截图与实际下载文件。私有材料和证据留在ignored输出目录。
