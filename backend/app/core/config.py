"""应用配置。所有密钥/口令经环境变量注入, 禁止硬编码、禁止提交 .env。

桌面打包模式: 数据目录自动解析到平台标准路径 (macOS/Windows/Linux)。
"""
import os as _os
import sys as _sys
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


def _app_data_dir() -> str:
    """返回平台标准应用数据目录, 不存在则自动创建。"""
    if _sys.platform == "darwin":
        base = _os.path.expanduser("~/Library/Application Support/SRS")
    elif _sys.platform == "win32":
        base = _os.path.join(_os.environ.get("APPDATA", _os.path.expanduser("~")), "SRS")
    else:
        base = _os.path.join(_os.environ.get("XDG_DATA_HOME",
                                             _os.path.expanduser("~/.local/share")), "SRS")
    _os.makedirs(base, exist_ok=True)
    return base


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "污染场地土壤生态-生产功能重构监管系统"
    api_v1_prefix: str = "/api/v1"

    # 服务器
    host: str = "127.0.0.1"
    port: int = 8000

    # 数据库: 桌面模式自动使用平台数据目录 (macOS: ~/Library/Application Support/SRS/)
    database_url: str = f"sqlite:///{_app_data_dir()}/srs.db"

    # 安全
    secret_key: str = "CHANGE_ME_IN_ENV"  # 必须在 .env 覆盖
    access_token_expire_minutes: int = 480
    algorithm: str = "HS256"

    # 本地文件存储 (桌面模式自动使用平台数据目录)
    file_storage_dir: str = _os.path.join(_app_data_dir(), "storage")

    # Redis (可选)
    redis_url: str = "redis://localhost:6379/0"

    # AI 网关 (OpenAI 兼容; 留空则前端 AI 助手降级为"未配置"提示)
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = "Qwen/Qwen2.5-7B-Instruct"
    ai_timeout: int = 60

    # 地图服务: 天地图 key 仅后端持有, 前端通过本地瓦片代理访问
    tianditu_key: str = ""

    # 桌面模式: 检测到打包环境时自动启用
    is_packaged: bool = getattr(_sys, "frozen", False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
