import logging
from database import init_database

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("开始执行数据库初始化...")
    init_database()
    logger.info("数据库初始化完成！")
    print("数据库初始化已完成，请查看日志了解详情。") 