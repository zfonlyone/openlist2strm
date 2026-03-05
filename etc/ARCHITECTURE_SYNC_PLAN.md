# OpenList2STRM 多项目迭代方案（v1）

## 目标
1. 定时任务交互更友好：支持“苹果闹钟式”时间/日期滚动选择体验（移动端原生 picker + 周期选择器）。
2. STRM 生成优化：识别同名字幕（srt/ass/ssa/vtt/sub）并生成本地 sidecar，提升 Emby 本地字幕识别。
3. 跨项目每周回传：将 Emby 侧产生的 info/nfo 与补齐字幕同步回 OpenList 网盘，降低 API 压力。

## 架构策略
- **调度层（openlist2strm）**
  - TaskConfig 扩展 recurrence（daily/weekly/monthly/once/custom）。
  - 前端任务表单改为：
    - 时间 picker（`input[type=time]`，移动端原生滚动）
    - 日期 picker（`input[type=date]`）
    - 周期选择（每天/每周/每月 + 星期多选）
  - 后端统一转换为 CronTrigger，确保可观测与兼容旧任务。

- **STRM + 字幕层（openlist2strm）**
  - 扫描目录时把视频与字幕按 basename 分组。
  - 对每个视频旁路输出字幕 sidecar（同目录同名 .srt/.ass...）。
  - 缓存中记录字幕清单 hash，变化才更新，减少写盘。

- **周同步层（新增 sync-manifest）**
  - 每周任务生成 manifest：
    - 收集 strm 目录新增/变更的 `.nfo/.info/.srt/.ass/.vtt`。
    - 计算 sha256，只有 diff 才入队。
  - 调用 OpenList 上传 API 批量回传（按目录批次 + 并发限流）。
  - 失败重试 + 指数退避 + 下周续传。

## 降低 OpenList API 请求方案
1. 扫描阶段维持增量缓存（mtime/size/both 可配）。
2. 同步阶段使用 manifest diff（只传变化文件）。
3. 批次上传（默认 20 文件/批）+ QoS 限流（共享现有 limiter）。
4. 周期性任务，不在每次扫描后立即回传。

## 实施顺序
- Phase 1: 任务调度 UX + recurrence 结构改造
- Phase 2: 字幕识别与 sidecar 输出
- Phase 3: 周同步任务 + OpenList 上传模块 + 重试队列
- Phase 4: TG 命令增强（任务向导式创建/编辑）

## 默认决策（超时自动执行）
- 周同步执行时间：每周一 03:30 Asia/Shanghai。
- 回传目标路径：与 STRM 相对路径镜像到 OpenList 源目录同级 `_emby_meta` 子目录。
- API 并发：2；每批 20；失败重试 3 次。
