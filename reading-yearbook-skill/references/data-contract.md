# 数据契约

仅在调整字段、接新数据源或排查输出时读取。

## 顶层

`yearbook-data.json` 必须包含：

- `schema_version`：当前为 `1.0`。
- `year`：自然年。
- `source_mode`：`sample`、`live` 或明确命名的本地导入模式。
- `verification_status`：`sample_verified`、`live_verified`、`partial_unverified`、`implemented_unverified`。
- `summary`、`books`、`topics`、`thesis`、`profiles`。

## Book

每本书至少包含：

- `book_id`、`title`、`author`、`cover`、`category`。
- `progress`：0–100；只有 100 表示读完。
- `reading_seconds`：秒。
- `months`：发生阅读或笔记行为的月份。
- `highlights`、`thoughts`、`bookmark_count`。
- `topics`、`evidence_level`、`evidence_reason`。
- `score_parts`、`score`、`score_reason`、`selected`、`book_of_year_candidate`。

划线和想法必须有稳定 `source_id`。条件字段未知时保留空值，不猜测。

## 时间与单位

- 微信读书时间为 Unix 时间戳；同时兼容秒和毫秒输入。
- 所有阅读时长统一为秒。
- `readTimes` 只用于月份分布；总量优先使用 `totalReadTime`。
- 年度筛选依据该书阅读更新时间、读完时间、划线和想法时间的并集。

## 数据模式

样例与真实模式使用同一 schema。任何 UI、文案和验证报告都必须展示数据模式与验证状态。
