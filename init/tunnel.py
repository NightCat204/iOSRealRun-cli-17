import asyncio
import logging
import multiprocessing
import os
import queue as queue_mod
import signal
import time

from driver import connect

# 建立隧道的默认超时（秒）。QUIC 握手正常只需数秒，
# 超过该时长基本可判定为设备侧或驱动侧异常。
TUNNEL_TIMEOUT = 60


class TunnelError(RuntimeError):
    """隧道未能建立。携带面向用户的中文说明。"""


def tunnel_proc(queue: multiprocessing.Queue):
    # Ctrl+C 会发给整个前台进程组。子进程在此忽略 SIGINT，
    # 由主进程统一决定何时通过 terminate() 结束它——
    # 这样主进程无需屏蔽自己的 SIGINT，Ctrl+C 始终可用。
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    # 子进程有独立的 logging 状态，需单独配置，与主进程保持一致
    _debug = os.environ.get("DEBUG", False)
    _level = logging.DEBUG if _debug else logging.WARNING
    for _name in ("wintun", "quic", "asyncio", "urllib3.connectionpool"):
        logging.getLogger(_name).setLevel(_level)
    # zeroconf 在 macOS 上会产生已知的非致命 mDNS socket 警告（[Errno 55]），
    # 单独抑制到 ERROR 级别，DEBUG 模式下仍完整输出
    logging.getLogger("zeroconf").setLevel(logging.DEBUG if _debug else logging.ERROR)

    # get_serverrsd() 同样可能失败或 exit(1)，失败必须回传，
    # 否则主进程会一直等一个永远不会到来的结果
    try:
        server_rsd = connect.get_serverrsd()
    except BaseException as exc:
        queue.put((connect.TUNNEL_ERROR, type(exc).__name__, str(exc)))
        raise

    asyncio.run(connect.tunnel(server_rsd, queue))


def stop_tunnel(process: multiprocessing.Process, timeout=5):
    """逐级升级地结束隧道子进程：terminate -> join -> kill。

    子进程持有 tun 设备，必须确保它真正退出，否则会残留虚拟网卡。
    """
    if process is None or not process.is_alive():
        return
    process.terminate()
    process.join(timeout)
    if process.is_alive():
        process.kill()
        process.join(timeout)


def _fail(process, message):
    stop_tunnel(process)
    raise TunnelError(message)


def tunnel(timeout=TUNNEL_TIMEOUT):
    # start the tunnel in another process
    queue = multiprocessing.Queue()
    # daemon=True：主进程若被强制结束，子进程不会变成持有 tun 设备的孤儿进程
    process = multiprocessing.Process(target=tunnel_proc, args=(queue,), daemon=True)
    process.start()

    try:
        return _await_tunnel(process, queue, timeout)
    except BaseException:
        # 包括 Ctrl+C：不能留下仍持有 tun 设备的子进程
        stop_tunnel(process)
        raise


def _await_tunnel(process, queue, timeout):
    # 轮询等待而非无限阻塞：子进程崩溃、卡住都能被及时发现，
    # 且短超时让主进程始终有机会响应 Ctrl+C
    deadline = time.monotonic() + timeout
    notified = 0
    while True:
        try:
            message = queue.get(timeout=0.5)
        except queue_mod.Empty:
            if not process.is_alive():
                # 子进程是「先写错误消息、再退出」，此刻消息可能仍在队列的
                # 传输途中，再多取一次，以便拿到具体异常而不是笼统的退出提示
                try:
                    message = queue.get(timeout=1)
                except queue_mod.Empty:
                    _fail(process, "隧道子进程已退出，隧道未能建立（具体异常见上方 traceback）")
                break
            if time.monotonic() >= deadline:
                _fail(process, f"建立隧道超时（{timeout} 秒），已终止子进程")
            waited = int(timeout - (deadline - time.monotonic()))
            if waited // 10 > notified:
                notified = waited // 10
                print(f"正在建立隧道...（已等待 {notified * 10} 秒，超时 {timeout} 秒）")
            continue
        break

    if not message or message[0] != connect.TUNNEL_OK:
        kind = message[1] if len(message) > 1 else "未知错误"
        detail = message[2] if len(message) > 2 else ""
        _fail(process, f"隧道建立失败：{kind}{(' - ' + detail) if detail else ''}")

    _, address, port = message
    return process, address, port
