# 交付与验收

本契约只用于用户明确要求的完整私人档案／图谱，保留旧 `run_yearbook.py` 的结构和兼容规则。普通年报图文、书单或单书分享使用 [分享操作](share-workflow.md)，不执行这里的全书档案与固定卡组要求。

## 目录

```text
output/<year>/
├── atlas.html
├── yearbook-data.json
├── selection-preview.md
├── selection.json
├── yearbook-data.draft.json
├── cards-manifest.json
├── validation-report.json
├── cards/
├── cards-html/
└── books/<book-slug>/
    ├── profile.md
    ├── evidence.json
    └── deep/
```

原始接口响应应放在 `private/` 或用户指定的非公开目录，不复制进最终输出。

## 自动验收

- `atlas.html`、数据 JSON 和精选预览存在。
- 单书档案数等于年度书籍数。
- 卡组包含封面、节律、主题、年度之书、精选单书与年度问题；HTML 与 PNG 一一对应。
- `cards-manifest.json` 的文件名必须与 `cards-html/` 完全一致、不可重复，且至少包含封面、节律、主题、年度之书和年度问题五类。
- `selection.json` 必须保持 `confirmed`，并与最终数据的年份、精选书、年度之书和确认时间完全一致；manifest 中恰好一张年度之书卡，其他精选单书卡与选择结果一一对应。
- 没有 `wrk-...` 或包含 Key 的赋值文本。
- 每条直接引用有 `source_id`。
- 年份、汇总、书籍、档案、选择关系与验证状态必须通过 schema 兼容检查；年度之书必须属于用户确认的精选书。
- 要求 PNG 时，导出失败、文件 stem 不对应、数量不一致或尺寸不是 900×1200，顶层验证状态必须失败。

## 状态语义

- `pass`：当前检查全部通过。
- `failed`：关键产物或约束未通过。
- `unavailable`：环境缺少可选依赖，保留可用降级产物。
- `sample_verified`：样例完整通过，不代表真实账号。
- `live_verified`：当前用户真实数据完成采集、生成和验证。
- `partial_unverified`：真实采集存在缺页或单书失败，不能发布最终版。
