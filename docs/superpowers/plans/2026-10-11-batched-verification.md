# 分批核验实施计划

用户已确认具体规格及调用预算；不再增加设计确认。基线 `a9c06c6`，沿用 `codex/ebook-web-distillation`。

## Global Constraints

以 `docs/superpowers/specs/2026-10-11-batched-verification-design.md` 为完整验收规格。不得减少候选、截断必要证据、强改冲突状态或把纸面演练当实际压力测试。前 7 阶段 VERSION、提示词、配置身份与缓存键不变。原始仓颉文件、解析、五类提取、模型配置、分享布局不在本轮范围。

## Task 1: 分批核验核心与集成

先读完整规格 `docs/superpowers/specs/2026-10-11-batched-verification-design.md`；它是本任务的要求与精确值。实现全局对齐、稳定分批 V1/V2/V3、全局收口和确定性旧接口组装，严格执行规格中的候选/出处/代表/覆盖/缺口门。

文件归属：新增 `reading-yearbook-skill/scripts/ebook_verification.py`；修改 `ebook_pipeline.py`；必要时窄修改 `serve_ebook.py` 与 `assets/ebook-app.js` 的进度/预算显示；新增 `tests/test_ebook_verification.py`；更新相关 `test_ebook_core.py` / `test_ebook_server.py` 及受影响控制测试。不要修改 README、发布清单、安装副本、验收文档、原始 vendor 或旧年鉴。不运行真实模型，不停止服务，不 push。

实现顺序：

1. 先用真实生产接口编写失败测试，记录 RED。对新契约使用模型边界测试替身，但调用真实分批/校验/缓存/合并逻辑；保留现有测试的含义，不删除回归断言。
2. helper 负责目录/证据包/切批/严格校验/合并；现有 pipeline 内 `call` 继续统一负责来源门、私有诊断、缓存和取消。新增阶段契约与 schema 必须显式区分 `batched-v1`，下游仍收到 `{candidates, task_audit, gaps}`。
3. 不改前 7 阶段任何提示词/key/runner_context。对照原源码和测试验证旧缓存键及内容；验证失败/取消/全局审计失败恢复仅重做缺失或无效当前阶段。
4. 动态总数、预算和中文进度沿现有 progress/BudgetRequired 协议完成。对齐/分批/收口均顺序调用，空候选不调用空对齐。成本说明包括共同概览与索引大小。必要时查询控制者接口决策，不能悄悄扩大范围。
5. 覆盖规格的 17/33/0 候选、完整末批、证据过大缩批及单候选确认、跨批重复与不同机制、未知/循环/被拒绝代表、漏项/重复/越批、伪造引文、布尔型伪验证、非法 reference、合并出处与缺口、原始任务恰好一次、无直接升级、重试/取消与缓存字节不变。
6. 迭代时只跑相关测试；完成后运行 core/verification/runner/server 相关 Python 套件一次。Python 为 `D:/Python/python.exe -X utf8`。PowerShell 使用 login:false。使用 apply_patch 编辑；只 stage 自己所属文件。
7. 提交并自审。报告记录 RED/GREEN 的命令、对应失败/成功输出、改动与边界；任何无法完成项显式升级，不声称整书验收成功。

报告 `.superpowers/sdd/batched-task-1-report.md`，最终仅返状态、提交、测试摘要、顾虑和报告路径。主控另行进行独立复核、资源打包和获批真实实测。

## Task 2: 复核、发布资源及真实验收

主控生成 Task 1 diff 包，独立审查规格与质量；有重要问题统一修复后复审。此前整分支已做广泛评审；本轮聚焦新增分批架构和跨阶段接口，不重做无关 vendor/UI 改动。

更新 Skill 参考说明和发布资源 REQUIRED/manifest，验证全新安装副本含新 helper。源码复核通过后，核对自己的旧服务 PID/任务边界，再启动新源码，恢复同一真实任务 `bec081cda4a7430da45de786fda731f9`。

保持原书与前 7 阶段缓存。先验证真实首批契约，再在 600 秒/阶段、60 分钟/本轮上限内顺序继续；不自动提高上限或重试。成功后核验原文/分块和真实复制/MD/离线 HTML/三比例 PNG/ZIP/刷新/375px。失败或预算用完停止长调用，保留缓存，准确更新验收状态。

提交并 push 已授权的 origin 功能分支，不改 main，不 force，不创建 PR。正式结果未过则保留 implemented_unverified；真实缺口不能被测试或文档抹去。
