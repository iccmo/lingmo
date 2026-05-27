"""
路由包 — 4 模块架构

模块：
  - novel.py     : 小说 CRUD、写作生成、质量分析、导出发布
  - audiobook.py : TTS 语音合成、音频播放
  - script.py    : 视觉圣经、AI 导演分镜、Prompt 生成
  - drama.py     : 画面生成、配音配乐、视频合成

共享依赖：deps.py (init_deps, get_db, set_status, get_status)
"""
