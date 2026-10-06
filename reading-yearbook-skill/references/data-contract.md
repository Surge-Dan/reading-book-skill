# 数据契约

仅在调整字段、接新数据源或排查输出时读取。

本文件描述旧私人档案`schema_version: 1.0`，不作为HTML契约。默认HTML使用`reading-html/1.2`，其字段、null语义与历史笔记范围见[HTML年鉴操作](html-yearbook.md)。旧档案中缺逐书年度时长的0默认值不能当作已测得0秒传给新的HTML流程。

## 顶层

`yearbook-data.json` 必须包含：

- `schema_version`：当前为 `1.0`。
- `year`：自然年。
- `source_mode`：当前最终产物只允许 `sample` 或 `live`。
- `verification_status`：`sample_verified`、`live_verified`、`partial_unverified`、`implemented_unverified`。
- `summary`、`books`、`topics`、`thesis`、`profiles`。

## Book

每本书至少包含：

- `book_id`、`title`、`author`、`cover`、`category`。
- `progress`：当前累计进度 0–100；只有 100 表示读完，不等同于年内投入。
- `annual_reading_seconds` / `reading_seconds`：官方年度统计能明确归属到该书的秒数；无可靠数据时为 0。
- `lifetime_reading_seconds`：接口返回的累计阅读秒数，只作背景，不参与年度时长汇总。
- `months`：发生阅读或笔记行为的月份。
- `highlights`、`thoughts`：只包含目标自然年的逐条证据。
- `bookmark_count` / `lifetime_bookmark_count`：接口返回的累计书签数，只作背景，不参与年度评分或年度笔记数。
- `finished_in_year`：只有明确的目标年读完时间才为真。
- `topics`、`evidence_level`、`evidence_reason`。
- `score_parts`、`score`、`score_reason`、`selected`、`book_of_year_candidate`。

划线和想法必须有稳定 `source_id`。条件字段未知时保留空值，不猜测。

`progress` 是累计进度，只作背景。年度评分只使用可归属到目标年的阅读秒数、活跃月份、目标年读完信号、目标年划线与目标年想法；不能把累计进度或累计书签当作年度投入。

## 时间与单位

- 微信读书时间为 Unix 时间戳；同时兼容秒和毫秒输入。
- 所有阅读时长统一为秒。
- `readTimes` 只用于月份分布；总量优先使用 `totalReadTime`。
- 年度筛选依据该书阅读更新时间、读完时间、笔记本更新时间、年度排行以及划线和想法时间的并集；没有目标年信号的书不进入年报。
- 划线和想法先按目标年逐条过滤，不能因为一本书在目标年有活动就混入其他年份内容。

## 数据模式

样例与真实模式使用同一 schema。任何 UI、文案和验证报告都必须展示数据模式与验证状态。

最终状态必须满足：`sample` 对应 `sample_verified`；`live` 对应 `live_verified`。`implemented_unverified` 与 `partial_unverified` 只能用于预览，不能生成最终版。
