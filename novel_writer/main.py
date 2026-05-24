"""Novel Writer CLI — 统一入口"""

import sys, argparse
from .config import config, validate
from .database import Database
from .scheduler import Scheduler


def cmd_init(args):
    """交互式创建新小说"""
    print("\n  ✧ 创建新小说\n")
    nid = input("  小说 ID (英文/拼音): ").strip().lower().replace(" ", "-")
    if not nid:
        print("  ❌ ID 不能为空")
        return
    title = input("  书名: ").strip()
    genre = input("  类型 [玄幻]: ").strip() or "玄幻"
    synopsis = input("  一句话简介: ").strip()
    world_name = input("  世界名称: ").strip()
    power = input("  修炼体系: ").strip()
    protag = input("  主角名: ").strip() or "主角"

    db = Database()
    if db.get_novel(nid):
        print(f"  ❌ '{nid}' 已存在")
        return
    db.create_novel(id=nid, title=title, genre=genre, synopsis=synopsis,
                    world_name=world_name, power_system=power,
                    char_key="protagonist", name=protag, role="主角")
    print(f"\n  ✅ '{title}' 创建成功！")
    print(f"  Web: http://localhost:5173/#/novels/{nid}")


def cmd_list(args):
    """列出所有小说"""
    db = Database()
    novels = db.list_novels()
    if not novels:
        print("  还没有小说。运行 'python -m novel_writer.main init' 创建")
        return
    print(f"\n  📚 我的小说 ({len(novels)} 本)\n")
    for n in novels:
        ch = n.get("latest_chapter")
        latest = f"第{ch['number']}章 {ch['title']}" if ch and ch.get("number") else "暂无章节"
        print(f"  {n['title']:<20} {n.get('total_chapters',0):>4}章 {'{:,}'.format(n.get('total_words',0)):>10}字  {latest}")


def cmd_run(args):
    """手动执行一次生成"""
    db = Database()
    novel_id = args.novel
    if not novel_id:
        novels = db.list_novels()
        if not novels:
            print("  还没有小说。先创建: python -m novel_writer.main init")
            return
        novel_id = novels[0]["id"]

    print(f"  ⏳ 正在为 '{novel_id}' 生成章节...")
    sched = Scheduler()
    result = sched.run_once(novel_id)
    print(f"  {'✅' if 'success' in result else '❌'} {result}")


def cmd_status(args):
    """查看进度"""
    db = Database()
    novels = db.list_novels()
    print(f"\n  📊 系统状态\n")
    total_ch = sum(n.get("total_chapters", 0) for n in novels)
    total_w = sum(n.get("total_words", 0) for n in novels)
    print(f"  小说: {len(novels)} 本 | 章节: {total_ch} | 字数: {total_w:,}")
    if novels:
        print()
        for n in novels:
            s = db.get_scheduler_state(n["id"])
            auto = "🔄 全自动" if s and s.get("is_running") else "✍️ 手动"
            print(f"  {n['title']:<20} {n.get('total_chapters',0):>4}章  {auto}")


def cmd_daemon(args):
    """启动守护进程"""
    missing = validate()
    if missing:
        print(f"  ❌ 缺少配置: {', '.join(missing)}")
        return
    sched = Scheduler()
    try:
        sched.run_daemon()
    except KeyboardInterrupt:
        print("\n  已停止")


def cmd_serve(args):
    """启动 Web 服务器"""
    import uvicorn
    print(f"  🌐 启动 Web 服务器: http://localhost:{args.port}")
    uvicorn.run("novel_writer.server:app", host="0.0.0.0", port=args.port, log_level="warning")


def main():
    parser = argparse.ArgumentParser(description="Novel Writer — AI 小说创作引擎")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="创建新小说")
    p_list = sub.add_parser("list", help="列出所有小说")
    p_run = sub.add_parser("run", help="手动执行一次生成+发布")
    p_run.add_argument("novel", nargs="?", help="小说 ID（可选，默认第一本）")
    sub.add_parser("status", help="查看进度")
    sub.add_parser("daemon", help="启动守护进程（全自动模式）")
    p_serve = sub.add_parser("serve", help="启动 Web 服务器")
    p_serve.add_argument("--port", type=int, default=8765, help="端口 (默认 8765)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    handlers = {"init": cmd_init, "list": cmd_list, "run": cmd_run,
                "status": cmd_status, "daemon": cmd_daemon, "serve": cmd_serve}
    handlers[args.command](args)


if __name__ == "__main__":
    main()
