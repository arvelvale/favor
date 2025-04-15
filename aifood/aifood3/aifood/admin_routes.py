from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for
import mysql.connector
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash # Added for admin_user_add

# Import necessary configurations and utilities
from config import db_config, logger
from admin_utils import record_user_visit, get_visit_stats, get_member_stats, get_recent_subscriptions

# Create a Blueprint for admin routes
admin_bp = Blueprint('admin', __name__, url_prefix='/admin', template_folder='../templates') # Adjusted template_folder path

# Middleware to check admin login for all admin routes
@admin_bp.before_request
def require_admin_login():
    # Allow access to login page and login post route without being logged in
    if request.endpoint and request.endpoint not in ['admin.admin_login', 'admin.admin_login_post']:
        if 'admin_id' not in session:
            return redirect(url_for('admin.admin_login'))

# --- Add Admin Routes Below ---

@admin_bp.route('/')
def admin_login():
    if 'admin_id' in session:
        return redirect(url_for('admin.admin_dashboard'))
    return render_template('admin_login.html')

@admin_bp.route('/login', methods=['POST'])
def admin_login_post():
    username = request.form.get('username')
    password = request.form.get('password')
    
    # 验证管理员账户 (Replace with a more secure method in production)
    if username == 'Flavor' and password == '': 
        session['admin_id'] = 1 # Use a non-guessable ID in production
        session['admin_name'] = 'Flavor'
        logger.info(f"Admin user 'Flavor' logged in successfully.")
        return redirect(url_for('admin.admin_dashboard'))
    else:
        logger.warning(f"Admin login failed for username: {username}")
        return render_template('admin_login.html', error='用户名或密码错误')

@admin_bp.route('/dashboard')
def admin_dashboard():
    # The require_admin_login before_request handles the login check
    try:
        # 连接数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True, buffered=True)
        
        # 获取当前日期
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # 1. 用户总数
        cursor.execute("SELECT COUNT(*) as total_users FROM users")
        total_users = cursor.fetchone()['total_users']
        
        # 2. 新增用户数（过去7天）
        cursor.execute("""
            SELECT COUNT(*) as new_users 
            FROM users 
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        """)
        new_users = cursor.fetchone()['new_users']
        
        # 3. 总销售额 (Placeholder - needs subscription amount)
        # Assuming user_subscriptions table has an 'amount' column
        try:
            cursor.execute("""
                SELECT ROUND(SUM(amount), 2) as total_sales 
                FROM user_subscriptions
            """)
            result = cursor.fetchone()
            total_sales = result['total_sales'] if result and result['total_sales'] else 0
        except mysql.connector.Error as err: 
            # If 'amount' column doesn't exist, handle gracefully
            if err.errno == 1054: # Unknown column 'amount'
                logger.warning("Column 'amount' not found in 'user_subscriptions'. Total sales set to 0.")
                total_sales = 0
            else:
                 raise # Re-raise other errors

        # 4. 销售增长率（同比上月）
        current_month = datetime.now().month
        current_year = datetime.now().year
        prev_month = current_month - 1 if current_month > 1 else 12
        prev_year = current_year if current_month > 1 else current_year - 1
        
        # 本月销售额 (Placeholder - needs amount)
        try:
            cursor.execute("""
                SELECT ROUND(SUM(amount), 2) as current_sales 
                FROM user_subscriptions 
                WHERE MONTH(created_at) = %s AND YEAR(created_at) = %s
            """, (current_month, current_year))
            current_sales = cursor.fetchone()['current_sales'] or 0
        except mysql.connector.Error as err:
            if err.errno == 1054:
                 current_sales = 0
            else: raise

        # 上月销售额 (Placeholder - needs amount)
        try:
            cursor.execute("""
                SELECT ROUND(SUM(amount), 2) as prev_sales 
                FROM user_subscriptions 
                WHERE MONTH(created_at) = %s AND YEAR(created_at) = %s
            """, (prev_month, prev_year))
            prev_sales = cursor.fetchone()['prev_sales'] or 0
        except mysql.connector.Error as err:
            if err.errno == 1054:
                 prev_sales = 0
            else: raise

        sales_growth = 0
        if prev_sales > 0:
            sales_growth = round(((current_sales - prev_sales) / prev_sales) * 100, 1)
        
        # 5. 今日销售额 (Placeholder - needs amount)
        try:
            cursor.execute("""
                SELECT ROUND(SUM(amount), 2) as daily_sales 
                FROM user_subscriptions 
                WHERE DATE(created_at) = %s
            """, (today,))
            daily_sales = cursor.fetchone()['daily_sales'] or 0
        except mysql.connector.Error as err:
            if err.errno == 1054:
                 daily_sales = 0
            else: raise

        # 6. 访问量统计（从visit_stats表获取真实数据）
        cursor.execute("""
            SELECT COUNT(*) as count FROM visit_stats WHERE visit_date = %s
        """, (today,))
        # Use fetchone() safely
        today_visit_record = cursor.fetchone()
        if today_visit_record and today_visit_record['count'] == 0:
            # 如果没有今天的记录，插入一条初始记录（访问量为0）
            cursor.execute("""
                INSERT INTO visit_stats (visit_date, page_views, unique_visitors) 
                VALUES (%s, 0, 0)
            """, (today,))
            conn.commit()
            
        # 确保昨天也有数据用于比较
        cursor.execute("SELECT COUNT(*) as count FROM visit_stats WHERE visit_date = %s", (yesterday,))
        yesterday_visit_record = cursor.fetchone()
        if yesterday_visit_record and yesterday_visit_record['count'] == 0:
            cursor.execute("""
                INSERT INTO visit_stats (visit_date, page_views, unique_visitors) 
                VALUES (%s, 0, 0)
            """, (yesterday,))
            conn.commit()
        
        # 获取总访问量
        cursor.execute("SELECT SUM(page_views) as total_visits FROM visit_stats")
        result = cursor.fetchone()
        total_visits = result['total_visits'] if result and result['total_visits'] else 0
        
        # 计算本周访问量环比增长
        # 本周和上周访问量
        this_week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime('%Y-%m-%d')
        last_week_start = (datetime.now() - timedelta(days=datetime.now().weekday()+7)).strftime('%Y-%m-%d')
        
        cursor.execute("""
            SELECT SUM(page_views) as this_week 
            FROM visit_stats 
            WHERE visit_date >= %s
        """, (this_week_start,))
        this_week_visits = cursor.fetchone()['this_week'] or 0
        
        cursor.execute("""
            SELECT SUM(page_views) as last_week 
            FROM visit_stats 
            WHERE visit_date >= %s AND visit_date < %s
        """, (last_week_start, this_week_start))
        last_week_visits = cursor.fetchone()['last_week'] or 0
        
        visits_growth = 0
        if last_week_visits > 0:
            visits_growth = round(((this_week_visits - last_week_visits) / last_week_visits) * 100, 1)
        
        # 7. 日访问量
        cursor.execute("SELECT page_views as daily_visits FROM visit_stats WHERE visit_date = %s", (today,))
        result = cursor.fetchone()
        daily_visits = result['daily_visits'] if result and result['daily_visits'] else 0
        
        # 8. 日访问量变化率
        cursor.execute("SELECT page_views as yesterday_visits FROM visit_stats WHERE visit_date = %s", (yesterday,))
        result = cursor.fetchone()
        yesterday_visits = result['yesterday_visits'] if result and result['yesterday_visits'] else 0
        
        daily_visits_change = 0
        if yesterday_visits > 0:
            daily_visits_change = round(((daily_visits - yesterday_visits) / yesterday_visits) * 100, 1)
        
        # 9. 转化率 - 付费用户 / 注册用户
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) as paid_users 
            FROM user_subscriptions
        """)
        paid_users = cursor.fetchone()['paid_users'] or 0
        
        conversion_rate = 0
        if total_users > 0:
            conversion_rate = round((paid_users / total_users) * 100, 1)
        
        # 10. 新付费用户（过去7天）
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) as new_paid_users 
            FROM user_subscriptions 
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        """)
        new_paid_users = cursor.fetchone()['new_paid_users'] or 0
        
        # 获取一周的真实访问数据
        visit_stats = get_visit_stats(7) # Assumes get_visit_stats is correctly imported
        pv_data = [stat['page_views'] for stat in visit_stats]
        uv_data = [stat['unique_visitors'] for stat in visit_stats]
        
        # 11. 获取门店销售数据 (Placeholder - assumes 'stores' and 'sales_stats' tables exist)
        stores = []
        try:
            cursor.execute("""
                SELECT 
                    s.id, 
                    s.name, 
                    COALESCE(SUM(ss.amount), 0) as sales,
                    0 as `change` # Placeholder for change calculation
                FROM stores s
                LEFT JOIN sales_stats ss ON s.id = ss.store_id 
                    AND ss.sale_date BETWEEN DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY) AND CURRENT_DATE
                GROUP BY s.id, s.name
            """)
            stores_result = cursor.fetchall()
            for store in stores_result:
                 stores.append({
                     'name': store['name'],
                     'sales': round(store['sales'], 2),
                     'change': round(store['change'], 1) if store['change'] else 0
                 })
        except mysql.connector.Error as err:
             if err.errno == 1146: # Table doesn't exist
                 logger.warning("Tables 'stores' or 'sales_stats' not found. Store data skipped.")
                 stores = []
             else:
                 raise

        # 准备数据字典
        data = {
            'total_sales': round(total_sales, 2),
            'sales_growth': sales_growth,
            'total_visits': int(total_visits),
            'visits_growth': visits_growth,
            'total_users': total_users,
            'new_users': new_users,
            'daily_sales': round(daily_sales, 2),
            'today_date': today,
            'daily_visits': daily_visits,
            'daily_visits_change': daily_visits_change,
            'conversion_rate': conversion_rate,
            'new_paid_users': new_paid_users,
            'traffic_data': {
                'pv': pv_data,
                'uv': uv_data
            },
            'stores': stores
        }
        
        return render_template('admin.html', **data)
        
    except Exception as e:
        logger.error(f"Error in admin dashboard: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        # 如果发生错误，使用默认数据
        data = {
            'total_sales': 0,
            'sales_growth': 0,
            'total_visits': 0,
            'visits_growth': 0,
            'total_users': 0,
            'new_users': 0,
            'daily_sales': 0,
            'today_date': datetime.now().strftime('%Y-%m-%d'),
            'daily_visits': 0,
            'daily_visits_change': 0,
            'conversion_rate': 0,
            'new_paid_users': 0,
            'traffic_data': {
                'pv': [0] * 7,
                'uv': [0] * 7
            },
            'stores': []
        }
        return render_template('admin.html', **data, error="获取数据出错，请联系技术支持。")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_bp.route('/logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_name', None)
    logger.info("Admin user logged out.")
    return redirect(url_for('admin.admin_login'))

@admin_bp.route('/users')
def admin_users():
    # The require_admin_login before_request handles the login check
    try:
        # 连接数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True, buffered=True)
        
        # 获取用户列表
        cursor.execute("""
            SELECT 
                u.id, u.username, u.email, u.created_at, u.last_login, 
                (SELECT COUNT(*) FROM user_recipes WHERE user_id = u.id) as recipe_count,
                CASE WHEN EXISTS (
                    SELECT 1 FROM user_subscriptions 
                    WHERE user_id = u.id AND is_active = TRUE AND end_date > NOW()
                ) THEN TRUE ELSE FALSE END as is_premium
            FROM users u
            ORDER BY u.created_at DESC
        """)
        
        users = cursor.fetchall()
        
        # 格式化日期
        for user in users:
            if user['created_at']:
                user['created_at'] = user['created_at'].strftime('%Y-%m-%d %H:%M') # Consistent format
            if user['last_login']:
                user['last_login'] = user['last_login'].strftime('%Y-%m-%d %H:%M')
            else:
                user['last_login'] = 'Never'
        
        return render_template('admin_users.html', users=users, timestamp=int(datetime.now().timestamp()))
        
    except Exception as e:
        logger.error(f"Error loading users for admin: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return render_template('admin_users.html', users=[], error="获取用户数据出错", timestamp=int(datetime.now().timestamp()))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_bp.route('/user/<int:user_id>')
def admin_user_detail(user_id):
    # The require_admin_login before_request handles the login check
    try:
        # 连接数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True, buffered=True)
        
        # 获取用户信息
        cursor.execute("""
            SELECT * FROM users WHERE id = %s
        """, (user_id,))
        
        user = cursor.fetchone()
        if not user:
            logger.warning(f"Admin attempted to view non-existent user ID: {user_id}")
            return redirect(url_for('admin.admin_users'))
        
        # 获取用户的订阅信息
        cursor.execute("""
            SELECT * FROM user_subscriptions 
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))
        subscriptions = cursor.fetchall()
        
        # 获取用户的食谱信息
        cursor.execute("""
            SELECT * FROM user_recipes 
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))
        recipes = cursor.fetchall()
        
        # 格式化日期
        if user['created_at']:
            user['created_at'] = user['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        if user['last_login']:
            user['last_login'] = user['last_login'].strftime('%Y-%m-%d %H:%M:%S')
        else:
             user['last_login'] = 'Never'
            
        for sub in subscriptions:
            if sub['created_at']:
                sub['created_at'] = sub['created_at'].strftime('%Y-%m-%d')
            if sub['start_date']:
                sub['start_date'] = sub['start_date'].strftime('%Y-%m-%d')
            if sub['end_date']:
                sub['end_date'] = sub['end_date'].strftime('%Y-%m-%d')
                
        for recipe in recipes:
            if recipe['created_at']:
                recipe['created_at'] = recipe['created_at'].strftime('%Y-%m-%d %H:%M')
        
        return render_template('admin_user_detail.html', 
                             user=user, 
                             subscriptions=subscriptions, 
                             recipes=recipes,
                             timestamp=int(datetime.now().timestamp()))
        
    except Exception as e:
        logger.error(f"Error loading user details for admin (User ID: {user_id}): {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return redirect(url_for('admin.admin_users'))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_bp.route('/user/edit/<int:user_id>', methods=['GET', 'POST'])
def admin_user_edit(user_id):
    # The require_admin_login before_request handles the login check
    try:
        # 连接数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True, buffered=True)
        
        if request.method == 'POST':
            # 更新用户信息
            username = request.form.get('username')
            email = request.form.get('email')
            bio = request.form.get('bio', '') # Provide default empty string
            is_active_form = request.form.get('is_active')
            is_active = True if is_active_form == 'on' else False # Correct boolean conversion
            
            # Basic validation (add more as needed)
            if not username or not email:
                 # Handle error - maybe flash message and re-render edit page
                 return redirect(url_for('admin.admin_user_edit', user_id=user_id, error='Username and email cannot be empty'))

            cursor.execute("""
                UPDATE users 
                SET username = %s, email = %s, bio = %s, is_active = %s 
                WHERE id = %s
            """, (username, email, bio, is_active, user_id))
            
            conn.commit()
            logger.info(f"Admin updated user profile for User ID: {user_id}")
            return redirect(url_for('admin.admin_user_detail', user_id=user_id))
        
        # GET request: 获取用户信息
        cursor.execute("""
            SELECT * FROM users WHERE id = %s
        """, (user_id,))
        
        user = cursor.fetchone()
        if not user:
            logger.warning(f"Admin attempted to edit non-existent user ID: {user_id}")
            return redirect(url_for('admin.admin_users'))
        
        # Add is_active to user dict if it doesn't exist from DB (older schema?)
        if 'is_active' not in user:
            user['is_active'] = True # Assume active if column missing
            
        return render_template('admin_user_edit.html', user=user, timestamp=int(datetime.now().timestamp()))
        
    except Exception as e:
        logger.error(f"Error editing user for admin (User ID: {user_id}): {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        # Redirect to user list on error, maybe with flash message
        return redirect(url_for('admin.admin_users'))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_bp.route('/user/delete/<int:user_id>', methods=['POST'])
def admin_user_delete(user_id):
    # The require_admin_login before_request handles the login check
    # Consider adding CSRF protection for POST requests like this
    try:
        # 连接数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # You might want to add checks here - e.g., don't delete the admin's own user?
        if 'admin_user_id' in session and user_id == session['admin_user_id']:
             return jsonify({"success": False, "message": "Cannot delete the currently logged-in admin user."}), 403
        
        # Add cascading deletes or handle related data (recipes, subscriptions, etc.)
        # For now, just deleting the user record
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        deleted_count = cursor.rowcount
        conn.commit()
        
        if deleted_count > 0:
            logger.info(f"Admin deleted user ID: {user_id}")
            return jsonify({"success": True, "message": "用户已删除"})
        else:
             logger.warning(f"Admin attempted to delete non-existent user ID: {user_id}")
             return jsonify({"success": False, "message": "用户不存在或已被删除"}), 404
        
    except Exception as e:
        logger.error(f"Error deleting user for admin (User ID: {user_id}): {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "message": f"删除用户失败: {str(e)}"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_bp.route('/user/add', methods=['GET', 'POST'])
def admin_user_add():
    # The require_admin_login before_request handles the login check
    if request.method == 'POST':
        try:
            # 连接数据库
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            
            # 获取表单数据
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            bio = request.form.get('bio', '')
            
            # Basic validation
            if not username or not email or not password:
                return render_template('admin_user_add.html', error='Username, email, and password are required.')
            
            # Check if username or email already exists
            cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
            if cursor.fetchone():
                 conn.close()
                 return render_template('admin_user_add.html', error='Username or email already exists.')

            # 密码加密
            password_hash = generate_password_hash(password)
            
            # 添加用户 (assuming is_active defaults to TRUE or is set in DB)
            cursor.execute("""
                INSERT INTO users 
                (username, email, password_hash, bio, created_at) 
                VALUES (%s, %s, %s, %s, NOW())
            """, (username, email, password_hash, bio))
            
            conn.commit()
            new_user_id = cursor.lastrowid
            logger.info(f"Admin added new user: {username} (ID: {new_user_id})")
            
            return redirect(url_for('admin.admin_users'))
            
        except Exception as e:
            logger.error(f"Error adding user by admin: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return render_template('admin_user_add.html', error=f"Error adding user: {str(e)}")
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals() and conn.is_connected():
                conn.close()
    
    # GET request
    return render_template('admin_user_add.html')

# 会员管理相关路由
@admin_bp.route('/members')
def admin_members():
    # The require_admin_login before_request handles the login check
    try:
        # 获取会员统计数据
        stats = get_member_stats() # Assumes this function is correctly imported and works
        
        # 获取最近的订阅记录
        subscriptions = get_recent_subscriptions(20) # Assumes this function works
        
        # Format subscription dates safely
        for sub in subscriptions:
            for date_key in ['created_at', 'start_date', 'end_date']:
                 if sub.get(date_key):
                     # Check if it's a datetime object before formatting
                     if isinstance(sub[date_key], datetime):
                         sub[date_key] = sub[date_key].strftime('%Y-%m-%d')
                     # If it's already a string, assume it's correctly formatted or leave as is
                     # You might want to add validation here if needed

        return render_template('admin_members.html', 
                              stats=stats, 
                              subscriptions=subscriptions,
                              timestamp=int(datetime.now().timestamp()))
        
    except Exception as e:
        logger.error(f"Error loading member stats for admin: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        # Provide default structure for stats if function fails
        default_stats = {'total_members': 0, 'monthly_members': 0, 'annual_members': 0, 'expiring_soon': 0, 'total_revenue': 0}
        return render_template('admin_members.html', 
                              stats=default_stats, 
                              subscriptions=[], 
                              error="获取会员数据出错",
                              timestamp=int(datetime.now().timestamp()))

# Note: The track_user_visits function using record_user_visit 
# should remain in app.py's before_request, as it applies to all users,
# not just admins navigating the /admin section.

# --- Add Admin Routes Below --- 