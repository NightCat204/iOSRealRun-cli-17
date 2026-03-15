import logging
import os
import shlex
import signal
import sys

try:
    import coloredlogs
except ModuleNotFoundError:
    coloredlogs = None


debug = os.environ.get("DEBUG", False)

def install_logging(level: int):
    if coloredlogs is not None:
        coloredlogs.install(level=level)
    else:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
            force=True,
        )


install_logging(logging.INFO)
logging.getLogger("wintun").setLevel(logging.DEBUG if debug else logging.WARNING)
logging.getLogger("quic").setLevel(logging.DEBUG if debug else logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.DEBUG if debug else logging.WARNING)
logging.getLogger("zeroconf").setLevel(logging.DEBUG if debug else logging.WARNING)
logging.getLogger("parso.cache").setLevel(logging.DEBUG if debug else logging.WARNING)
logging.getLogger("parso.cache.pickle").setLevel(logging.DEBUG if debug else logging.WARNING)
logging.getLogger("parso.python.diff").setLevel(logging.DEBUG if debug else logging.WARNING)
logging.getLogger("humanfriendly.prompts").setLevel(logging.DEBUG if debug else logging.WARNING)
logging.getLogger("blib2to3.pgen2.driver").setLevel(logging.DEBUG if debug else logging.WARNING)
logging.getLogger("urllib3.connectionpool").setLevel(logging.DEBUG if debug else logging.WARNING)


def ensure_macos_root():
    if sys.platform != "darwin" or os.geteuid() == 0:
        return

    script_path = os.path.abspath(__file__)
    print("需要 root 权限创建 tun 设备，正在使用当前 Python 解释器重新启动...")
    os.execvp("sudo", ["sudo", sys.executable, script_path, *sys.argv[1:]])


def explain_missing_dependency(exc: ModuleNotFoundError):
    missing = exc.name or "unknown"
    interpreter = sys.executable
    project_dir = os.path.dirname(os.path.abspath(__file__))
    requirements = os.path.join(project_dir, "requirements.txt")
    script_path = os.path.join(project_dir, "main.py")

    print(f"当前解释器 {interpreter} 缺少依赖: {missing}")
    if sys.platform == "darwin" and os.geteuid() == 0:
        print("你很可能使用了 `sudo python3 main.py`，sudo 切到了系统 Python，虚拟环境里的依赖不会被带上。")
        print("请先激活虚拟环境，再直接运行 `python main.py`，程序会自动请求 sudo。")
        print(
            "如果你想手动提权，请使用当前环境的解释器，例如: "
            f"`sudo {shlex.quote(interpreter)} {shlex.quote(script_path)}`"
        )
    else:
        print(
            "请在当前解释器对应的环境里安装依赖，例如: "
            f"`{shlex.quote(interpreter)} -m pip install -r {shlex.quote(requirements)}`"
        )

    raise SystemExit(1) from exc


def load_runtime_modules():
    try:
        from driver import location
        from init import init
        from init import route
        from init import tunnel
        from pymobiledevice3.cli.developer import DvtSecureSocketProxyService
        from pymobiledevice3.cli.remote import RemoteServiceDiscoveryService

        import config
        import run
    except ModuleNotFoundError as exc:
        explain_missing_dependency(exc)

    return {
        "RemoteServiceDiscoveryService": RemoteServiceDiscoveryService,
        "DvtSecureSocketProxyService": DvtSecureSocketProxyService,
        "config": config,
        "init": init,
        "location": location,
        "route": route,
        "run": run,
        "tunnel": tunnel,
    }



def main():
    ensure_macos_root()
    runtime = load_runtime_modules()
    init_module = runtime["init"]
    tunnel_module = runtime["tunnel"]
    route_module = runtime["route"]
    location_module = runtime["location"]
    run_module = runtime["run"]
    config_module = runtime["config"]
    remote_service = runtime["RemoteServiceDiscoveryService"]
    dvt_service = runtime["DvtSecureSocketProxyService"]

    # set level
    logger = logging.getLogger(__name__)
    install_logging(logging.INFO)
    logger.setLevel(logging.INFO)
    if debug:
        logger.setLevel(logging.DEBUG)
        install_logging(logging.DEBUG)

    init_module.init()
    logger.info("init done")

    # start the tunnel in another process
    logger.info("starting tunnel")
    original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    process, address, port = tunnel_module.tunnel()
    signal.signal(signal.SIGINT, original_sigint_handler)
    logger.info("tunnel started")
    try:
        logger.debug(f"tunnel address: {address}, port: {port}")

        # get route
        loc = route_module.get_route()
        logger.info(f"got route from {config_module.config.routeConfig}")


        with remote_service((address, port)) as rsd:
            with dvt_service(rsd) as dvt:
                try:
                    print(f"已开始模拟跑步，速度大约为 {config_module.config.v} m/s")
                    print("会无限循环，按 Ctrl+C 退出")
                    print("请勿直接关闭窗口，否则无法还原正常定位")
                    run_module.run(dvt, loc, config_module.config.v)
                except KeyboardInterrupt:
                    logger.debug("get KeyboardInterrupt (inner)")
                    logger.debug(f"Is process alive? {process.is_alive()}")
                finally:
                    logger.debug(f"Is process alive? {process.is_alive()}")
                    logger.debug("Start to clear location")
                    location_module.clear_location(dvt)
                    logger.info("Location cleared")


    except KeyboardInterrupt:
        logger.debug("get KeyboardInterrupt (outer)")
    finally:
        # stop the tunnel process
        logger.debug(f"Is process alive? {process.is_alive()}")
        logger.debug("terminating tunnel process")
        process.terminate()
        logger.info("tunnel process terminated")
        print("Bye")
    

    
if __name__ == "__main__":
    main()
