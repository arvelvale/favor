import os
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API密钥
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# API基础URL
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

# 代理设置
# 设置为None表示不使用代理
# 设置为字符串如 "http://127.0.0.1:7890" 表示使用代理
HTTP_PROXY = "http://127.0.0.1:10090"
HTTPS_PROXY = "http://127.0.0.1:10090"

# 超时设置
API_TIMEOUT = 60.0

# 应用设置
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")
PORT = int(os.getenv("PORT", "5000"))

# 获取代理配置
def get_proxies():
    """获取代理配置"""
    proxies = None
    if HTTP_PROXY or HTTPS_PROXY:
        proxies = {}
        if HTTP_PROXY:
            proxies["http"] = HTTP_PROXY
        if HTTPS_PROXY:
            proxies["https"] = HTTPS_PROXY
    return proxies

# 数据库连接配置
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'recipe_app',
    'port': 3306,
    'charset': 'utf8mb4',
    'use_unicode': True
} 
