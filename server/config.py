"""运行配置。所有凭据只从环境变量 / server/.env 读取，没有任何硬编码回退值。"""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
# .env 相对本文件解析，与启动目录无关；部署环境里已有的变量优先。
load_dotenv(BASE_DIR / ".env")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("favor")


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


class Settings:
    def __init__(self) -> None:
        self.secret_key = _require("SECRET_KEY")
        if len(self.secret_key) < 32:
            raise RuntimeError("SECRET_KEY must contain at least 32 characters")

        # 模型服务是可选的：缺失时应用照常启动，只有对话接口返回 503。
        # 兼容旧变量名 DEEPSEEK_API_KEY。
        self.llm_api_key = (os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or "").strip()
        self.llm_base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com").strip()
        self.llm_model = os.getenv("LLM_MODEL", "deepseek-flash").strip()
        self.llm_timeout = float(os.getenv("LLM_TIMEOUT", "60"))

        # 菜品配图（阿里云百炼）。不填密钥时 agent 不会看到生图工具。
        self.image_api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        self.image_base_url = os.getenv("IMAGE_BASE_URL", "https://dashscope.aliyuncs.com/api/v1").strip()
        self.image_model = os.getenv("IMAGE_MODEL", "z-image-turbo").strip()
        self.image_size = os.getenv("IMAGE_SIZE", "1024*1024").strip()
        self.image_daily_limit = int(os.getenv("IMAGE_DAILY_LIMIT", "10"))

        self.database_path =Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "favor.sqlite3")))
        self.debug = os.getenv("DEBUG", "false").lower() in ("1", "true", "t", "yes")
        self.port = int(os.getenv("PORT", "5000"))
        # 生产环境走 HTTPS 时设为 true，会话 Cookie 只经加密连接发送。
        self.secure_cookies = os.getenv("SECURE_COOKIES", "false").lower() in ("1", "true", "t", "yes")
        self.web_dist = Path(os.getenv("WEB_DIST", str(BASE_DIR.parent / "web" / "dist")))

    @property
    def image_enabled(self) -> bool:
        return bool(self.image_api_key)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)
