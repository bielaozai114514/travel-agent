# core/logger.py
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

# 日志目录
LOG_DIR = Path("logs") # 定义日志文件存储目录为项目根目录下的 logs 文件夹
LOG_DIR.mkdir(exist_ok=True) # 创建日志目录，exist_ok=True 表示目录已存在时不报错（避免重复创建异常）

# 判断是否为开发环境（根据 stdout 是否为终端）
IS_DEV = sys.stdout.isatty() # 检查标准输出（stdout）是否连接到终端（比如本地运行 python app.py 时返回 True，部署到服务器 / 容器时通常返回 False）；


class ColorFormatter(logging.Formatter):
    """
    彩色日志格式化器: 将开发环境彩色日志格式化。
    仅在开发环境（IS_DEV=True）生效，生产环境使用默认格式化器
    """
    COLORS = {
        "DEBUG": "\033[36m",    # Cyan 青色
        "INFO": "\033[32m",     # Green 绿色
        "WARNING": "\033[33m",  # Yellow 黄色
        "ERROR": "\033[31m",    # Red 红色
        "CRITICAL": "\033[35m", # Magenta 洋红
    }
    RESET = "\033[0m" # 重置颜色

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET) # 根据日志级别（record.levelname，如 DEBUG/INFO）获取对应颜色
        record.levelname = f"{log_color}{record.levelname}{self.RESET}" # 改写 record.levelname，给级别名称包裹颜色转义码
        return super().format(record) # 调用父类 format 方法完成最终日志格式化（保留原有格式，仅修改级别颜色）


class LoggerManager:
    """日志管理器：按需创建带日期命名的日志器"""
    
    # 加载常量，写的方便点
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

    _loggers = {} # 缓存已创建的日志器，key=日志器名称，value=Logger实例

    @staticmethod # 静态方法：无需实例化类，直接调用 LoggerManager.get_logger()
    def get_logger(
        name: str = "app",
        level: int = logging.INFO,
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB
        backup_count: int = 5,
        console_output: bool = True,
        file_output: bool = True
    ) -> logging.Logger:
        """
        获取配置好的日志器
        
        Args:
            name: 日志器名称（用于区分模块，如 "llm"、"api"），会显示在日志内容中
            level: 日志级别（DEBUG < INFO < WARNING < ERROR < CRITICAL），低于该级别的日志会被过滤
            max_bytes: 	单个日志文件的最大大小（字节），达到后自动切分（滚动日志）
            backup_count: 保留的旧日志文件数量（如 5 表示最多保留 5 个切分后的文件）
            console_output: 是否输出到控制台
            file_output: 是否输出到文件
        """

        # 缓存检查：如果日志器已创建，直接返回缓存实例
        if name in LoggerManager._loggers:
            return LoggerManager._loggers[name]

        # 创建日志器实例
        logger = logging.getLogger(name)
        logger.setLevel(level) # 设置日志器总级别（所有处理器都受此限制）
        logger.propagate = False  # 禁用日志传播：避免日志向上传递到根日志器，导致重复输出

        # 清理已有 handler（避免重复添加，比如重复调用 get_logger 时，例如多次调用 get_logger("api") 时，不会重复添加控制台 / 文件处理器）
        logger.handlers.clear()

        # 日志格式 日志时间+日志器名称+日志级别+日志所在文件:行号+日志内容
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"

        # 控制台处理器（开发环境彩色）
        if console_output:
            console_handler = logging.StreamHandler() # # 输出到标准输出（控制台）
            console_handler.setLevel(level)  # # 处理器级别（可单独设置，通常和日志器一致）
            if IS_DEV:
                # 开发环境：使用彩色格式化器
                formatter = ColorFormatter(fmt=log_format, datefmt=date_format)
            else:
                # 生产环境：使用默认格式化器（无颜色）
                formatter = logging.Formatter(fmt=log_format, datefmt=date_format)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        # 文件处理器（按日期命名 + 滚动备份）
        if file_output:
            today = datetime.now().strftime("%Y-%m-%d")  # 当天日期，如 2025-10-01
            log_file = LOG_DIR / f"{today}.{name}.log" # 日志文件路径：logs/2025-10-01.{日志器名称}.log

            # 滚动日志：使用 RotatingFileHandler，单个文件达到 max_bytes（10MB）时自动切分
            # 切分规则：2025-12-26.log → 2025-12-26.log.1 → 2025-12-26.log.2… 最多保留 backup_count=5 个文件
            file_handler = RotatingFileHandler(
                filename=log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8"
            )
            file_handler.setLevel(level)
            formatter = logging.Formatter(fmt=log_format, datefmt=date_format)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        # 缓存并返回日志器，下次如果遇到同名日志器，直接从缓存中获取，避免重复配置
        LoggerManager._loggers[name] = logger
        return logger


# 全局默认日志器，开箱即用的全局日志器，无需手动调用 get_logger 即可使用；
# 开发环境（IS_DEV=True）：日志级别为 DEBUG，显示所有级别日志（便于调试）；
# 生产环境（IS_DEV=False）：日志级别为 INFO，过滤 DEBUG 日志（减少日志量，提升性能）；
logger = LoggerManager.get_logger(
    name="backend",
    level=logging.DEBUG if IS_DEV else logging.INFO
)

# 使用方式：from core.logger import logger; logger.info("xxx")

# # 1. 使用全局默认日志器
# from core.logger import logger

# logger.debug("开发环境调试信息")
# logger.info("普通业务日志")
# logger.warning("非致命警告")
# logger.error("功能异常")
# logger.critical("严重错误，程序可能崩溃")

# # 2. 使用模块专属日志器
# llm_logger = LoggerManager.get_logger(name="llm", level=logging.DEBUG)
# llm_logger.info("调用大模型接口，参数：xxx")

# # 3. 记录异常（带栈信息）
# try:
#     1 / 0
# except Exception as e:
#     logger.error("除法运算异常", exc_info=e)  # exc_info=True 打印完整栈信息