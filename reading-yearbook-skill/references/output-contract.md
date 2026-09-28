# 交付与验收

## 目录

```text
output/<year>/
├── atlas.html
├── yearbook-data.json
├── selection-preview.md
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
- 至少有一张可编辑 HTML 卡片。
- 没有 `wrk-...` 或包含 Key 的赋值文本。
- 每条直接引用有 `source_id`。
- PNG 导出状态单独报告，不用 HTML 成功替代。

## 状态语义

- `pass`：当前检查全部通过。
- `failed`：关键产物或约束未通过。
- `unavailable`：环境缺少可选依赖，保留可用降级产物。
- `sample_verified`：样例完整通过，不代表真实账号。
- `live_verified`：当前用户真实数据完成采集、生成和验证。
- `partial_unverified`：真实采集存在缺页或单书失败，不能发布最终版。
