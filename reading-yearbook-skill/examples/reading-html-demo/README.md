# 离线阅读年鉴示例

index.html由assets/sample-data.json生成，包含6本虚构示例书，页面已标记示例数据。文字封面不是实际出版物书封。

重新生成：

```powershell
python -X utf8 scripts/build_reading_html.py --input assets/sample-data.json --year 2026 --output examples/reading-html-demo/index.html
```

无需在线依赖；浏览器可筛选、展开详情、选择划线与导出。字体优先本机Noto字族，无该字体时回退系统中文字体。PDF通过打印保存，PNG／ZIP／Markdown／JSON通过下载保存。

图表适配lieflat-charts Basics B2/F2，完整PolyForm Noncommercial 1.0.0许可内嵌于页面数据来源区。商业用途需遵循该许可。
