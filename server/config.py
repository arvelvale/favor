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
        self.llm_base_url = (os.getenv("LLM_BASE_URL") or "https://api.deepseek.com").strip()
        self.llm_model = (os.getenv("LLM_MODEL") or "deepseek-flash").strip()
        self.llm_timeout = float(os.getenv("LLM_TIMEOUT") or "60")

        # 菜品配图（阿里云百炼）。不填密钥时 agent 不会看到生图工具。
        self.image_api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        self.image_base_url = os.getenv("IMAGE_BASE_URL", "https://dashscope.aliyuncs.com/api/v1").strip()
        self.image_model = os.getenv("IMAGE_MODEL", "z-image-turbo").strip()
        self.image_size = os.getenv("IMAGE_SIZE", "1024*1024").strip()
        self.image_daily_limit = int(os.getenv("IMAGE_DAILY_LIMIT", "10"))
        # MiniMax 生图（image-01）。IMAGE_PROVIDER 留空 = 自动：配了 MINIMAX_API_KEY 就用 MiniMax，否则用百炼；
        # 写 off 则关闭菜品配图（2026-11-18 起暂不做配图：image-01 常把番茄炒蛋画成面条，H3 准但一张约 3 分钟）
        self.minimax_api_key = (os.getenv("MINIMAX_API_KEY") or "").strip()
        self.minimax_base_url = (os.getenv("MINIMAX_BASE_URL") or "https://api.minimax.cn/v1").strip()
        self.minimax_image_model = (os.getenv("MINIMAX_IMAGE_MODEL") or "image-01").strip()
        self.image_provider = (os.getenv("IMAGE_PROVIDER") or "").strip().lower()
        if self.image_provider not in ("", "minimax", "dashscope", "off"):
            raise RuntimeError("IMAGE_PROVIDER must be minimax, dashscope or off (or empty for auto)")
        # 拍冰箱照片识别食材（DeepSeek 视觉模型，OpenAI 兼容接口，默认复用 LLM_API_KEY / LLM_BASE_URL）。
        # 如需单独指定识图服务，可填写 VISION_API_KEY / VISION_BASE_URL / VISION_MODEL；未配密钥时前端不显示「拍一张」
        self.vision_api_key = (os.getenv("VISION_API_KEY") or self.llm_api_key).strip()
        self.vision_base_url = (os.getenv("VISION_BASE_URL") or self.llm_base_url or "https://api.deepseek.com").strip()
        self.vision_model = (os.getenv("VISION_MODEL") or "deepseek-flash").strip()
        self.vision_timeout = float(os.getenv("VISION_TIMEOUT") or "60")
        self.vision_daily_limit = max(1, int(os.getenv("VISION_DAILY_LIMIT") or "20"))
        # 每人每天最多推荐几批菜谱（每批一次模型调用），控制费用
        self.recipe_daily_limit = max(1, int(os.getenv("RECIPE_DAILY_LIMIT") or "20"))

        # 知识库 RAG：开关与检索阈值。留空时用 or 兜底默认值（getenv 第二参数对空串无效）。
        self.rag_enabled = (os.getenv("RAG_ENABLED") or "true").strip().lower() in ("1", "true", "yes", "on")
        self.rag_top_k = max(1, int(os.getenv("RAG_TOP_K") or "4"))
        self.rag_min_abs_score = max(0.0, float(os.getenv("RAG_MIN_ABS_SCORE") or "12.0"))
        self.rag_kb_dir = os.getenv("RAG_KB_DIR") or str(BASE_DIR / "rag" / "kb")

        # 留空时用 or 兜底默认值（getenv 第二参数对空串无效，与 RAG 配置同理）。
        self.database_path = Path(os.getenv("DATABASE_PATH") or str(BASE_DIR / "data" / "favor.sqlite3"))
        self.debug = os.getenv("DEBUG", "false").lower() in ("1", "true", "t", "yes")
        self.port = int(os.getenv("PORT", "5000"))
        # 生产环境走 HTTPS 时设为 true，会话 Cookie 只经加密连接发送。
        self.secure_cookies = os.getenv("SECURE_COOKIES", "false").lower() in ("1", "true", "t", "yes")
        self.web_dist = Path(os.getenv("WEB_DIST", str(BASE_DIR.parent / "web" / "dist")))

    @property
    def image_backend(self) -> str | None:
        """实际使用的生图服务：minimax / dashscope / None（关闭或都没配）。"""
        if self.image_provider == "off":
            return None
        if self.image_provider == "minimax":
            return "minimax" if self.minimax_api_key else None
        if self.image_provider == "dashscope":
            return "dashscope" if self.image_api_key else None
        return "minimax" if self.minimax_api_key else ("dashscope" if self.image_api_key else None)

    @property
    def image_enabled(self) -> bool:
        return self.image_backend is not None

    @property
    def vision_enabled(self) -> bool:
        return bool(self.vision_api_key)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)
