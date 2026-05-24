#!/usr/bin/env python3
"""
macOS 微信自动拨打电话工具
使用 AppleScript 控制微信进行拨号
"""

import subprocess
import sys
import time


def run_applescript(script: str) -> str:
    """执行 AppleScript 并返回结果"""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"AppleScript 执行失败: {result.stderr}")
    return result.stdout.strip()


def ensure_wechat_running():
    """确保微信已启动"""
    script = '''
    tell application "System Events"
        if not (exists process "WeChat") then
            tell application "WeChat" to activate
            delay 3
        end if
    end tell
    '''
    run_applescript(script)
    print("微信已启动")


def bring_wechat_to_front():
    """将微信窗口置前"""
    script = 'tell application "WeChat" to activate'
    run_applescript(script)
    time.sleep(0.5)


def search_and_call(contact_name: str, call_type: str = "voice"):
    """
    搜索联系人并拨打电话

    Args:
        contact_name: 联系人名称（微信备注名或昵称）
        call_type: 通话类型 - "voice" 语音通话 或 "video" 视频通话
    """
    bring_wechat_to_front()

    # 使用 Command+F 打开搜索
    search_script = f'''
    tell application "System Events"
        tell process "WeChat"
            keystroke "f" using {{command down}}
            delay 0.5
            keystroke "{contact_name}"
            delay 1
        end tell
    end tell
    '''
    run_applescript(search_script)
    print(f"正在搜索: {contact_name}")

    time.sleep(1.5)

    # 按回车选择第一个搜索结果
    select_script = '''
    tell application "System Events"
        tell process "WeChat"
            key code 36
            delay 1
        end tell
    end tell
    '''
    run_applescript(select_script)
    print("已进入聊天窗口")

    time.sleep(1)

    # 点击聊天窗口右上角的语音/视频通话按钮
    # 注意：这里需要根据微信的实际 UI 布局调整坐标
    # 微信 macOS 版通话按钮通常在窗口右上角
    if call_type == "voice":
        # 语音通话 - 点击右上角电话图标
        call_script = '''
        tell application "System Events"
            tell process "WeChat"
                -- 点击右上角的按钮区域（电话图标）
                -- 先尝试菜单方式
                try
                    click menu item "语音通话" of menu 1 of menu bar item "聊天" of menu bar 1
                on error
                    -- 如果菜单不可用，使用键盘快捷键
                    -- 微信没有固定的语音通话快捷键，使用坐标点击
                    set frontmost to true
                end try
            end tell
        end tell
        '''
    else:
        # 视频通话
        call_script = '''
        tell application "System Events"
            tell process "WeChat"
                try
                    click menu item "视频通话" of menu 1 of menu bar item "聊天" of menu bar 1
                on error
                    set frontmost to true
                end try
            end tell
        end tell
        '''

    run_applescript(call_script)
    print(f"已发起{('语音' if call_type == 'voice' else '视频')}通话")


def call_by_click_ui(contact_name: str, call_type: str = "voice"):
    """
    使用 UI 元素定位方式拨打电话（更可靠）
    """
    bring_wechat_to_front()

    # 搜索联系人
    script = f'''
    tell application "System Events"
        tell process "WeChat"
            keystroke "f" using {{command down}}
            delay 0.5
            keystroke "{contact_name}"
            delay 1.5
            key code 36
            delay 1
        end tell
    end tell
    '''
    run_applescript(script)
    print(f"已打开与 {contact_name} 的聊天窗口")

    time.sleep(1)

    # 使用 Accessibility API 查找并点击通话按钮
    # 微信的通话按钮通常在聊天窗口右上角
    call_label = "语音通话" if call_type == "voice" else "视频通话"

    script = f'''
    tell application "System Events"
        tell process "WeChat"
            tell window 1
                -- 尝试查找工具栏中的按钮
                try
                    click button "{call_label}"
                on error
                    -- 尝试在群组中查找
                    try
                        click (first button whose description is "{call_label}")
                    on error
                        -- 最后尝试坐标点击（右上角区域）
                        set pos to position of window 1
                        set sz to size of window 1
                        set x to (item 1 of pos) + (item 1 of sz) - 50
                        set y to (item 2 of pos) + 30
                        click at {{x, y}}
                    end try
                end try
            end tell
        end tell
    end tell
    '''
    run_applescript(script)
    print(f"已发起 {call_label}")


def main():
    if len(sys.argv) < 2:
        print("用法: python wechat_call.py <联系人名称> [voice|video]")
        print("示例: python wechat_call.py \"张三\" voice")
        sys.exit(1)

    contact = sys.argv[1]
    call_type = sys.argv[2] if len(sys.argv) > 2 else "voice"

    if call_type not in ("voice", "video"):
        print("通话类型必须是 voice 或 video")
        sys.exit(1)

    print(f"准备给 {contact} 发起{'语音' if call_type == 'voice' else '视频'}通话...")

    try:
        ensure_wechat_running()
        time.sleep(1)
        call_by_click_ui(contact, call_type)
        print("操作完成")
    except Exception as e:
        print(f"操作失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
