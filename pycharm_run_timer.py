# -*- coding: utf-8 -*-
"""
PyCharm 运行结束提醒计时器（Windows）
====================================

功能
----
持续监控 PyCharm 中的 Python 运行（Run / Debug / 终端内运行）。
每当一次运行结束时：
  1. 在控制台显示基于系统时钟的倒计时（默认 60 秒）；
  2. 倒计时结束播放"结束提示铃声"，提醒你运行已结束。

用法
----
    python pycharm_run_timer.py             正常监控模式
    python pycharm_run_timer.py --selftest  自检模式（模拟运行结束 + 5 秒倒计时 + 铃声）

==================== 个性化修改指南 ====================
以下每一项都可以按你的喜好修改，代码中对应位置也标了相同的编号：

  ① COUNTDOWN_SECONDS  运行结束后的倒计时秒数（默认 60 秒 = 一分钟）
  ② POLL_INTERVAL      监控检测间隔（默认 1 秒，一般不用改）
  ③ ALARM_ROUNDS       铃声重复轮数（默认 3 轮，想要更响可以调大）
  ④ 铃声音调           响铃的频率和时长（在 ring() 函数中，见代码标记 ④）
=======================================================

其他说明
--------
- 仅使用 Python 标准库（winsound / ctypes），无需安装任何第三方包。
- 倒计时基于系统时钟 time.monotonic()，不会因系统负载而漂移；
  同时会显示预计响铃的墙钟时间。
- 请保持本窗口运行（可最小化）；按 Ctrl+C 退出监控。
- 倒计时期间按 Ctrl+C 可跳过本次响铃，直接继续监控下一次运行。
- 建议在普通命令行（或双击 .bat）中运行本程序，而不是在 PyCharm 里运行它；
  若一定要在 PyCharm 里运行，程序会自动排除自身进程，不影响检测。
"""

import ctypes
import os
import sys
import time
import winsound
from ctypes import wintypes
from datetime import datetime, timedelta

if sys.platform != "win32":
    sys.exit("该程序仅支持 Windows。")

# 统一以 UTF-8 输出，避免中文在管道/重定向时乱码（真实控制台窗口不受影响）
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ===================== 个性化修改区 =====================
# ① 可个性化修改：运行结束后的倒计时秒数（默认 60 秒 = 一分钟）
COUNTDOWN_SECONDS = 60
# ② 可个性化修改：监控检测间隔（秒，默认 1 秒，一般不用改）
POLL_INTERVAL = 1.0
# ③ 可个性化修改：铃声重复轮数（默认 3 轮，想更响可调大）
ALARM_ROUNDS = 3
# ========================================================

TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def process_snapshot():
    """枚举当前所有进程，返回 [(pid, ppid, exe_name), ...]（仅标准库 ctypes）。"""
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]

    h = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if h == INVALID_HANDLE_VALUE:
        return []
    try:
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        procs = []
        if kernel32.Process32FirstW(h, ctypes.byref(pe)):
            while True:
                procs.append((pe.th32ProcessID, pe.th32ParentProcessID, pe.szExeFile))
                if not kernel32.Process32NextW(h, ctypes.byref(pe)):
                    break
        return procs
    finally:
        kernel32.CloseHandle(h)


def any_pycharm_run_active():
    """当前是否有 PyCharm 启动的 Python 进程在运行。"""
    procs = process_snapshot()
    if not procs:
        return False
    pmap = {pid: (ppid, exe) for pid, ppid, exe in procs}
    my_pid = os.getpid()

    def under_pycharm(pid):
        seen = set()
        for _ in range(6):  # 沿父进程链向上最多 6 层
            if not pid or pid in seen:
                return False
            seen.add(pid)
            info = pmap.get(pid)
            if not info:
                return False
            ppid, exe = info
            if exe.lower().startswith("pycharm"):
                return True
            pid = ppid
        return False

    for pid, (_, exe) in pmap.items():
        if pid == my_pid:
            continue  # 排除自身进程
        if exe.lower().startswith("python") and under_pycharm(pid):
            return True
    return False


def countdown(seconds):
    """基于系统时钟倒计时，返回 True=正常倒数到 0，False=被 Ctrl+C 跳过。"""
    end = time.monotonic() + seconds
    ring_at = datetime.now() + timedelta(seconds=seconds)
    try:
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                break
            mm, ss = divmod(int(remaining), 60)
            sys.stdout.write(
                "\r运行结束！倒计时 %02d:%02d（预计 %s 响铃）… " % (mm, ss, ring_at.strftime("%H:%M:%S"))
            )
            sys.stdout.flush()
            time.sleep(0.2)
        sys.stdout.write("\r" + " " * 72 + "\r")
        return True
    except KeyboardInterrupt:
        sys.stdout.write("\r" + " " * 72 + "\r倒计时已跳过，继续监控下一次运行。\n")
        return False


def ring():
    """播放"结束提示铃声"：经典 叮-叮-叮——咚，重复多轮。"""
    try:
        ctypes.windll.kernel32.SetConsoleTitleW("运行结束提醒！")
    except Exception:
        pass
    # ④ 可个性化修改：铃声音调（(频率Hz, 时长毫秒) 序列，可自行增删、调整音高和节奏）
    pattern = [
        (880, 180), (880, 180), (880, 180), (1174, 550),  # 叮叮叮——咚
    ]
    for _ in range(max(1, ALARM_ROUNDS)):
        for freq, dur in pattern:
            try:
                winsound.Beep(freq, dur)
            except Exception:
                winsound.MessageBeep(-1)


def on_run_finished(seconds=COUNTDOWN_SECONDS):
    print("\n检测到 PyCharm 运行结束！")
    if countdown(seconds):
        print("时间到！运行已结束，请回到电脑前查看结果。")
        ring()
        print("铃声播放完毕，继续监控下一次运行…\n")
    else:
        print("继续监控下一次运行…\n")


def main():
    if "--selftest" in sys.argv[1:]:
        print("自检模式：模拟一次 PyCharm 运行结束…")
        time.sleep(1)
        on_run_finished(5)  # 自检用 5 秒倒计时，快速验证铃声
        print("自检完成。")
        return

    print("=" * 62)
    print("PyCharm 运行结束提醒计时器")
    print("监控中：检测到 PyCharm 运行结束后，倒计时 %d 秒并响铃提醒。" % COUNTDOWN_SECONDS)
    print("请保持本窗口运行（可最小化），按 Ctrl+C 退出。")
    print("=" * 62)

    prev = None
    try:
        while True:
            running = any_pycharm_run_active()
            if prev is None:
                prev = running
            elif prev and not running:
                on_run_finished()
            prev = running
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\n已退出监控。")


if __name__ == "__main__":
    main()
