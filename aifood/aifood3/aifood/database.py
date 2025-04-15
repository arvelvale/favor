import mysql.connector
import logging
import traceback
from config import db_config, logger

# Database initialization function
def init_database():
    """
    Initialize database, automatically create required table structures
    """
    # First try to connect to MySQL server (without specifying database)
    connection_config = db_config.copy()
    connection_config.pop('database', None)  # Remove database name
    try:
        # Connect to MySQL server
        conn = mysql.connector.connect(**connection_config)
        cursor = conn.cursor()
        
        # 创建数据库（如果不存在）
        logger.info("Checking if database exists...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_config['database']} DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        logger.info(f"Ensuring database {db_config['database']} exists")
        
        # 使用指定的数据库
        cursor.execute(f"USE {db_config['database']}")
        
        # 创建users表
        logger.info("Checking if users table exists...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            email VARCHAR(100) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at DATETIME NOT NULL,
            last_login DATETIME,
            profile_image MEDIUMBLOB,
            bio TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            INDEX idx_username (username),
            INDEX idx_email (email)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        logger.info("Ensuring users table exists")
        
        # 创建user_recipes表
        logger.info("Checking if user_recipes table exists...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_recipes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            recipe_name VARCHAR(100) NOT NULL,
            recipe_content TEXT NOT NULL,
            ingredients TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            is_favorite BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        logger.info("Ensuring user_recipes table exists")
        
        # 创建user_subscriptions表
        logger.info("Checking if user_subscriptions table exists...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_subscriptions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            plan_type VARCHAR(20) NOT NULL,
            amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            start_date DATETIME NOT NULL,
            end_date DATETIME NOT NULL,
            transaction_id VARCHAR(100),
            is_active BOOLEAN DEFAULT TRUE,
            created_at DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_user_id (user_id),
            INDEX idx_is_active (is_active)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        logger.info("Ensuring user_subscriptions table exists")
        
        # 创建usage_limits表
        logger.info("Checking if usage_limits table exists...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage_limits (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            date DATE NOT NULL,
            usage_count INT DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE KEY unique_user_date (user_id, date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        logger.info("Ensuring usage_limits table exists")

        # 创建email_verification_codes表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_verification_codes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                code VARCHAR(10) NOT NULL,
                created_at DATETIME NOT NULL,
                expires_at DATETIME NOT NULL,
                is_used BOOLEAN DEFAULT FALSE,
                INDEX email_code_idx (email(100), code)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        # 创建管理后台统计表
        # 访问统计表
        logger.info("Creating visit_stats table...")
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
        
        # 销售统计表
        logger.info("Creating sales_stats table...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales_stats (
            id INT AUTO_INCREMENT PRIMARY KEY,
            sale_date DATE NOT NULL,
            amount DECIMAL(10,2) NOT NULL DEFAULT 0,
            transaction_count INT DEFAULT 0,
            store_id INT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_sale_date (sale_date),
            INDEX idx_store_id (store_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        # 门店表
        logger.info("Creating stores table...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS stores (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            address VARCHAR(255),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        # 检查是否有默认门店数据，如果没有则插入
        cursor.execute("SELECT COUNT(*) FROM stores")
        store_count = cursor.fetchone()[0]
        
        if store_count == 0:
            logger.info("Inserting default store data...")
            stores = [
                ('北京店', '北京市海淀区中关村大街1号'),
                ('上海店', '上海市徐汇区淮海中路999号'),
                ('广州店', '广州市天河区天河路385号'),
                ('深圳店', '深圳市南山区科技园路1号'),
                ('成都店', '成都市锦江区红星路三段1号')
            ]
            
            cursor.executemany(
                "INSERT INTO stores (name, address) VALUES (%s, %s)",
                stores
            )
            
            conn.commit()
            logger.info(f"Inserted {len(stores)} default stores")

        # 提交事务
        conn.commit()
        logger.info("Database initialization completed")
        
        # 添加用户访问量统计和会员管理相关表
        logger.info("创建用户访问统计表...")
        
        # 创建user_visits表（如果不存在）
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
        
        # 添加示例会员数据（如果表为空）
        cursor.execute("SELECT COUNT(*) FROM user_subscriptions")
        subscription_count = cursor.fetchone()[0]
        
        if subscription_count == 0:
            logger.info("添加示例会员数据...")
            # 添加月度会员
            cursor.execute("""
            INSERT INTO user_subscriptions (user_id, plan_type, amount, start_date, end_date, is_active, created_at)
            SELECT 
                id, 
                'monthly', 
                7.90, 
                DATE_SUB(CURRENT_DATE, INTERVAL FLOOR(RAND() * 30) DAY), 
                DATE_ADD(CURRENT_DATE, INTERVAL FLOOR(RAND() * 30) DAY), 
                TRUE, 
                DATE_SUB(CURRENT_DATE, INTERVAL FLOOR(RAND() * 30) DAY)
            FROM users
            WHERE MOD(id, 3) = 0
            LIMIT 5
            """)
            
            # 添加年度会员
            cursor.execute("""
            INSERT INTO user_subscriptions (user_id, plan_type, amount, start_date, end_date, is_active, created_at)
            SELECT 
                id, 
                'annual', 
                79.90, 
                DATE_SUB(CURRENT_DATE, INTERVAL FLOOR(RAND() * 90) DAY), 
                DATE_ADD(CURRENT_DATE, INTERVAL FLOOR(RAND() * 270) DAY), 
                TRUE, 
                DATE_SUB(CURRENT_DATE, INTERVAL FLOOR(RAND() * 90) DAY)
            FROM users
            WHERE MOD(id, 5) = 0
            LIMIT 3
            """)
            
            conn.commit()
        
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close() 