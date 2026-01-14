import logging
import inspect
import os
from pathlib import Path
from datetime import datetime


class ModuleAwareLogger(logging.Logger):
    """自动识别调用模块的 Logger 类"""

    def _log(
        self,
        level,
        msg,
        args,
        exc_info=None,
        extra=None,
        stack_info=False,
        stacklevel=1,
    ):
        """重写 _log 方法，自动注入调用者模块名"""
        # 使用 inspect 获取调用者模块名
        frame = inspect.currentframe()
        try:
            # 回溯调用栈到用户代码
            # 栈结构：_log -> logger.info/debug/etc -> user code
            caller_frame = frame
            for _ in range(2):  # 回溯两层
                if caller_frame.f_back:
                    caller_frame = caller_frame.f_back
            module_name = caller_frame.f_globals.get("__name__", "unknown")
        finally:
            del frame  # 避免循环引用

        # 将模块名添加到 extra 字典
        if extra is None:
            extra = {}
        extra["module_name"] = module_name

        super()._log(level, msg, args, exc_info, extra, stack_info, stacklevel)


def _create_logger() -> logging.Logger:
    """创建并配置全局 logger"""
    # 读取环境变量
    verbose = os.environ.get("VERBOSE", "true").lower() in ("true", "1", "yes")

    # 设置自定义 Logger 类
    logging.setLoggerClass(ModuleAwareLogger)

    # 创建 logger
    logger = logging.getLogger("app")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # 如果禁用日志，直接返回
    if not verbose:
        logger.disabled = True
        return logger

    # 清除已有的 handlers（避免重复添加）
    logger.handlers.clear()

    # 创建日志目录和文件
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_filename = datetime.now().strftime("%Y-%m-%d.log")
    log_file = log_dir / log_filename

    # 检查文件是否已存在（用于决定是否需要添加分割线）
    file_exists = log_file.exists()

    # 日志格式（使用 module_name 而不是 name）
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(module_name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台 Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件 Handler (append 模式)
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 添加会话分割线
    separator = "=" * 80
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if file_exists:
        # 如果文件已存在，添加空行后再添加分割线
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("\n")

    # 使用 logger 记录会话开始（这样会触发我们的格式化）
    # 但为了分割线，我们直接写入文件
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{separator}\n")
        f.write(f"[{now}] New Session Started\n")
        f.write(f"{separator}\n")

    return logger


# 创建全局 logger 实例
logger = _create_logger()