import mysql.connector
import logging
from config import db_config, logger

def fix_database():
    """修复数据库结构问题"""
    logger.info("开始修复数据库结构...")
    
    try:
        # 连接数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # 1. 检查user_subscriptions表中是否有amount字段
        cursor.execute("""
        SELECT COUNT(*) as count
        FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = 'user_subscriptions' 
        AND column_name = 'amount'
        """)
        
        result = cursor.fetchone()
        has_amount_column = result[0] > 0
        
        if not has_amount_column:
            logger.info("添加amount字段到user_subscriptions表...")
            cursor.execute("""
            ALTER TABLE user_subscriptions 
            ADD COLUMN amount DECIMAL(10,2) NOT NULL DEFAULT 0.00 AFTER plan_type
            """)
            conn.commit()
            logger.info("amount字段添加成功!")
        else:
            logger.info("amount字段已存在，无需添加")
        
        # 2. 更新现有记录设置默认金额
        logger.info("更新现有订阅记录的金额...")
        cursor.execute("""
        UPDATE user_subscriptions 
        SET amount = CASE 
            WHEN plan_type = 'monthly' THEN 7.90 
            WHEN plan_type = 'annual' THEN 79.90 
            ELSE 0.00 
        END 
        WHERE amount = 0
        """)
        conn.commit()
        
        # 3. 检查user_visits表是否存在
        cursor.execute("""
        SELECT COUNT(*) as count
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
        AND table_name = 'user_visits'
        """)
        
        result = cursor.fetchone()
        has_user_visits_table = result[0] > 0
        
        if not has_user_visits_table:
            logger.info("创建user_visits表...")
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_visits (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                visit_date DATE NOT NULL,
                visit_count INT NOT NULL DEFAULT 1,
                last_visit_time DATETIME NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE KEY unique_user_date (user_id, visit_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            conn.commit()
            logger.info("user_visits表创建成功!")
        
        # 4. 检查visit_stats表是否存在
        cursor.execute("""
        SELECT COUNT(*) as count
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
        AND table_name = 'visit_stats'
        """)
        
        result = cursor.fetchone()
        has_visit_stats_table = result[0] > 0
        
        if not has_visit_stats_table:
            logger.info("创建visit_stats表...")
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS visit_stats (
                id INT AUTO_INCREMENT PRIMARY KEY,
                visit_date DATE NOT NULL,
                page_views INT DEFAULT 0,
                unique_visitors INT DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_date (visit_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            conn.commit()
            logger.info("visit_stats表创建成功!")
        
        logger.info("数据库修复完成!")
        return True
        
    except Exception as e:
        logger.error(f"数据库修复出错: {str(e)}")
        if 'conn' in locals() and conn.is_connected():
            conn.rollback()
        return False
        
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn.is_connected():
            conn.close()

if __name__ == "__main__":
    print("开始修复数据库结构...")
    result = fix_database()
    if result:
        print("数据库修复成功完成!")
    else:
        print("数据库修复过程中遇到错误，请查看日志了解详情。") 