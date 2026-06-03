/**
 * 章节组件 — 从 ChapterList.tsx 逐步拆分的子组件。
 *
 * 已独立组件（在 ../ 目录）:
 *   ChapterSearch.tsx     — 全文搜索
 *   ChapterDiff.tsx       — 版本对比
 *   AudioTextSync.tsx     — 音频文字同步
 *   MobileReadingMode.tsx — 手机阅读模拟
 *   SceneEditor.tsx       — 场景编辑器
 *   WordFrequency.tsx     — 词频分析
 *
 * 计划提取（仍在 ChapterList.tsx 内联）:
 *   ChapterEditMode.tsx   — 内联编辑 + 自动保存
 *   ChapterFocusMode.tsx  — 专注阅读模式
 *   ChapterProofread.tsx  — AI 校对面板
 *   ChapterTags.tsx       — 标签选择器 + 审批流转
 *   ChapterNotes.tsx      — 章节笔记
 *   useChapterState.ts    — 共享状态 hook
 */
