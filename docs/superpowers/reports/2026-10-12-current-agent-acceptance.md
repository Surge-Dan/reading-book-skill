# 当前 Agent 模式本地验收

日期：2026-10-12。范围：已确认设计的实现与受控测试；无新增模型 CLI / provider API 调用，未续跑旧整书任务。

## 已实现

- 默认 agent 模式，无 Codex / Claude Code 可启动上传。上传先本地解析，等待同一聊天接管；显式 CLI 模式保持原行为。
- 固定 ebook_agent.py 的 list / claim / next / submit / release，单持有者、单待回复阶段、独立尝试、身份和输入摘要、有限期限、幂等提交。
- 私有本机令牌与网页令牌分离；Host / Origin 校验、禁止代理和重定向、任务目录 JSON 校验、拒绝链接／重解析逃逸。
- 原仓颉规则与来源／契约／候选／覆盖门继续执行。无效回复不进入缓存或正式输出。
- 当前 Agent 方法与总体质量为 needs_review；同一聊天演练明确非隔离，不证明任务增益。任务审计、Markdown、HTML 与每页 PNG / ZIP 保留状态和局限。
- 网页等待、复制开始指令、取消、重试与范围确认；不自动唤醒 Agent，不自动换后端。

## 验证证据

- `python -X utf8 -m unittest discover -s tests -p test_ebook*.py`：98 通过，其中新模式 20；其余 78 为既有 core / runner / server / verification 回归。
- `test_skill_release.py`：6 通过；Skill quick_validate 通过；发布资源校验通过，版本 2026.10.12，共 181 个文件。
- `tests/ebook_agent_ui.py`：真实浏览器上传、等待、指令复制隐私、取消和重试通过；三种比例的全部分享页保留待核查／非隔离标识及覆盖缺口，并实际渲染 PNG。
- 既有 `ebook_browser.cjs`：离线阅读、注入安全、复制、MD / HTML / PNG / ZIP、375px、上传／取消／重试／范围确认／刷新／断连通过。
- `ebook_poll_race.cjs`：8 项乱序响应回归通过；`ebook_art.cjs`：三种比例、完整分页、PNG 几何回归通过。
- 完整发布包安装到独立临时目录后，从安装副本启动默认服务：独立页面、API、有效 TXT 上传等待领取及非法扩展名拒绝通过。
- 受控 ContractRunner 回复经过真实完整 pipeline 和私有 HTTP / helper 链路生成结果；该回复只作为测试 fixture，不是模型语义成功证明。
- 只读独立审查发现并修复：非法 EPUB 卡住队列、释放后发布、跨执行模式隐式接手、图像漏掉总体局限、旧释放请求影响新尝试。相关失败用例先 RED 后 GREEN；复审无剩余重要发现。

## 未验收边界

- 当前会话模型的真实小文本／整书蒸馏，以及原仓颉效果对照仍未验收。
- WorkBuddy / Trae 等宿主尚未实测；共享本地文件和脚本能力是前提，不等于所有 Agent 自动可用。
- 旧整书任务、运行中的旧预览和模型配置未改动。本次完整安装只使用临时目录，不声称已替换某个宿主的已安装 Skill。
- 未新增 OCR、DRM、书本 Skill 编译、MCP Sampling 或模型供应商接口。
