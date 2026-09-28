# 微信读书官方 Agent Gateway

仅在真实数据采集、接口升级或排查字段时读取。以下契约核对自腾讯官方 `Tencent/WeChatReading` 仓库，版本 `1.0.4`；服务端可能升级，收到 `upgrade_info` 时停止并按官方提示更新。

## 通用请求

- URL：`POST https://i.weread.qq.com/api/agent/gateway`
- Header：`Authorization: Bearer $WEREAD_API_KEY`
- Header：`Content-Type: application/json`
- Body 必须平铺 `api_name`、业务字段与 `skill_version: "1.0.4"`，不要包在 `params`。

Key 绑定用户身份。不得把 Key 写入输出、日志、异常或命令参数。

## 年报使用的接口

- `/shelf/sync`：书架；电子书在 `books[]`，有声内容在独立 `albums[]`。
- `/book/info`：书籍元数据。
- `/book/getprogress`：`progress` 为 0–100，`recordReadingTime` 为秒。
- `/user/notebooks`：有笔记书籍；使用 `lastSort` 游标分页，下一页游标取本页最后一项的 `sort`。
- `/book/bookmarklist`：返回划线 `updated[]`，当前不导出书签正文。
- `/review/list/mine`：参数名是小写 `bookid`；使用 `synckey` 游标分页。
- `/readdata/detail`：年度请求使用 `mode: annually` 和目标年 1 月 1 日时间戳；`totalReadTime`、`readTimes` 均为秒。

默认只对书架年内更新时间、笔记本年内 `sort` 和年度 `readLongest` 命中的书逐本请求详情，避免对整个书架发起大量调用。候选明显缺失时可显式使用 `--scan-all-shelf`，但要向用户说明耗时和官方接口无法保证覆盖已移出书架且没有笔记的书。

官方资料：

- https://github.com/Tencent/WeChatReading
- https://github.com/Tencent/WeChatReading/blob/main/skills/shelf.md
- https://github.com/Tencent/WeChatReading/blob/main/skills/notes.md
- https://github.com/Tencent/WeChatReading/blob/main/skills/readdata.md
- https://github.com/Tencent/WeChatReading/blob/main/skills/book.md

## 停止条件

- 401、403：停止，提示检查 Key 或权限。
- 422、499：停止，提示检查业务参数或 Skill 版本。
- `upgrade_info`：停止，展示不含敏感信息的升级提示。
- 瞬时网络错误：最多重试两次。
- 分页游标不前进：立即停止，避免无限重复请求。

真实采集未在当前用户账号完成端到端验证前，只能标记 `implemented_unverified`。
