import mysql.connector
import traceback
from datetime import datetime, timedelta
from config import db_config, logger

def record_user_visit(user_id):
    """记录用户访问数据"""
    if not user_id:
        return False
        
    try:
        # 连接数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # 获取当前日期
        today = datetime.now().strftime('%Y-%m-%d')
        current_time = datetime.now()
        
        # 更新用户的last_login
        cursor.execute(
            "UPDATE users SET last_login = %s WHERE id = %s",
            (current_time, user_id)
        )
        
        # 检查今天是否已有该用户的访问记录
        cursor.execute("""
            SELECT id, visit_count FROM user_visits 
            WHERE user_id = %s AND visit_date = %s
        """, (user_id, today))
        
        visit_record = cursor.fetchone()
        
        if visit_record:
            # 已有记录，更新访问计数和时间
            cursor.execute("""
                UPDATE user_visits 
                SET visit_count = visit_count + 1, last_visit_time = %s
                WHERE id = %s
            """, (current_time, visit_record['id']))
        else:
            # 没有记录，创建新记录
            cursor.execute("""
                INSERT INTO user_visits (user_id, visit_date, visit_count, last_visit_time)
                VALUES (%s, %s, 1, %s)
            """, (user_id, today, current_time))
        
        # 更新全站访问统计
        cursor.execute("""
            SELECT id FROM visit_stats WHERE visit_date = %s
        """, (today,))
        
        stats_record = cursor.fetchone()
        
        if stats_record:
            # 已有记录，更新page_views
            cursor.execute("""
                UPDATE visit_stats 
                SET page_views = page_views + 1,
                unique_visitors = (
                    SELECT COUNT(DISTINCT user_id) 
                    FROM user_visits 
                    WHERE visit_date = %s
                )
                WHERE visit_date = %s
            """, (today, today))
        else:
            # 没有记录，创建新记录，unique_visitors设为1
            cursor.execute("""
                INSERT INTO visit_stats (visit_date, page_views, unique_visitors)
                VALUES (%s, 1, 1)
            """, (today,))
        
        conn.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error recording user visit: {str(e)}")
        logger.error(traceback.format_exc())
        return False
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def get_visit_stats(days=7):
    """获取过去几天的访问统计数据"""
    try:
        # 连接数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # 获取日期范围
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days-1)
        
        # 准备日期列表（包含所有日期，即使没有数据）
        date_range = []
        current_date = start_date
        while current_date <= end_date:
            date_range.append(current_date.strftime('%Y-%m-%d'))
            current_date += timedelta(days=1)
        
        # 获取访问数据
        cursor.execute("""
            SELECT visit_date, page_views, unique_visitors
            FROM visit_stats
            WHERE visit_date BETWEEN %s AND %s
            ORDER BY visit_date
        """, (start_date, end_date))
        
        results = cursor.fetchall()
        
        # 将结果转换为字典，以日期为键
        stats_dict = {record['visit_date'].strftime('%Y-%m-%d'): record for record in results}
        
        # 构建完整的统计数据（包含所有日期）
        stats = []
        for date_str in date_range:
            if date_str in stats_dict:
                record = stats_dict[date_str]
                stats.append({
                    'date': date_str,
                    'page_views': record['page_views'],
                    'unique_visitors': record['unique_visitors']
                })
            else:
                # 对于没有数据的日期，设为0
                stats.append({
                    'date': date_str,
                    'page_views': 0,
                    'unique_visitors': 0
                })
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting visit stats: {str(e)}")
        logger.error(traceback.format_exc())
        return []
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def get_member_stats():
    """获取会员统计数据"""
    try:
        # 连接数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # 获取当前日期
        today = datetime.now().date()
        
        # 获取会员总数
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) as total_members
            FROM user_subscriptions
            WHERE is_active = TRUE AND end_date >= %s
        """, (today,))
        
        total_members = cursor.fetchone()['total_members']
        
        # 获取月度会员数
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) as monthly_members
            FROM user_subscriptions
            WHERE plan_type = 'monthly' AND is_active = TRUE AND end_date >= %s
        """, (today,))
        
        monthly_members = cursor.fetchone()['monthly_members']
        
        # 获取年度会员数
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) as annual_members
            FROM user_subscriptions
            WHERE plan_type = 'annual' AND is_active = TRUE AND end_date >= %s
        """, (today,))
        
        annual_members = cursor.fetchone()['annual_members']
        
        # 获取即将到期的会员数（7天内）
        expiry_date = today + timedelta(days=7)
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) as expiring_soon
            FROM user_subscriptions
            WHERE is_active = TRUE AND end_date BETWEEN %s AND %s
        """, (today, expiry_date))
        
        expiring_soon = cursor.fetchone()['expiring_soon']
        
        # 获取会员总收入
        cursor.execute("""
            SELECT ROUND(SUM(amount), 2) as total_revenue
            FROM user_subscriptions
        """)
        
        total_revenue = cursor.fetchone()['total_revenue'] or 0
        
        return {
            'total_members': total_members,
            'monthly_members': monthly_members,
            'annual_members': annual_members,
            'expiring_soon': expiring_soon,
            'total_revenue': total_revenue
        }
        
    except Exception as e:
        logger.error(f"Error getting member stats: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'total_members': 0,
            'monthly_members': 0,
            'annual_members': 0,
            'expiring_soon': 0,
            'total_revenue': 0
        }
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def get_recent_subscriptions(limit=10):
    """获取最近的订阅记录"""
    try:
        # 连接数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # 获取最近的订阅
        cursor.execute("""
            SELECT 
                s.id, s.user_id, u.username, s.plan_type, 
                s.amount, s.start_date, s.end_date, s.is_active,
                s.created_at
            FROM user_subscriptions s
            JOIN users u ON s.user_id = u.id
            ORDER BY s.created_at DESC
            LIMIT %s
        """, (limit,))
        
        subscriptions = cursor.fetchall()
        
        # 格式化日期
        for sub in subscriptions:
            sub['created_at'] = sub['created_at'].strftime('%Y-%m-%d')
            sub['start_date'] = sub['start_date'].strftime('%Y-%m-%d')
            sub['end_date'] = sub['end_date'].strftime('%Y-%m-%d')
            
        return subscriptions
        
    except Exception as e:
        logger.error(f"Error getting recent subscriptions: {str(e)}")
        logger.error(traceback.format_exc())
        return []
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close() 