from flask import jsonify, session, redirect, url_for, request
from database import db_config
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import logging
import traceback
from datetime import timedelta, datetime
import os
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Gmail API 权限范围
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def login_user(data, app):
    """Handle user login"""
    username = data.get('username')
    password = data.get('password')
    remember = data.get('remember', False)
    
    try:
        # Connect to database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # Query user
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        # Verify password
        if user and check_password_hash(user['password_hash'], password):
            # Login successful
            session['user_id'] = user['id']
            session['username'] = user['username']
            
            # If "remember me" is selected, set session persistence to 30 days
            if remember:
                session.permanent = True
                app.permanent_session_lifetime = timedelta(days=30)
            
            return jsonify({"success": True})
        else:
            # Login failed
            return jsonify({"success": False, "message": "Incorrect username or password"})
    
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        return jsonify({"success": False, "message": "Server error, please try again later"})
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def register_user(data):
    """Handle user registration"""
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    # 服务端密码强度验证
    if not re.match(r'^(?=.*[0-9])(?=.*[a-zA-Z])(?=.*[@#!%^&*;\'":,.?/])[a-zA-Z0-9@#!%^&*;\'":,.?/]{8,}$', password):
        return jsonify({
            "success": False, 
            "message": "Password must be at least 8 characters and include numbers, letters, and special characters"
        })
    
    try:
        # Connect to database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # Check if username already exists
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Username is already taken"})
        
        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Email is already registered"})
        
        # Create new user
        password_hash = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, created_at) VALUES (%s, %s, %s, NOW())",
            (username, email, password_hash)
        )
        conn.commit()
        
        return jsonify({"success": True})
    
    except Exception as e:
        logger.error(f"Error during registration: {str(e)}")
        return jsonify({"success": False, "message": "Server error, please try again later"})
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def get_gmail_service():
    """获取Gmail API服务实例"""
    creds = None
    
    # 尝试从token.pickle加载凭据
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    # 如果没有有效凭据，进行登录流程
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            # 使用端口5000，与应用实际端口匹配
            creds = flow.run_local_server(port=5000)
            
        # 保存凭据供下次使用
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

def send_verification_code(data):
    """Send verification code to email or phone"""
    email = data.get('email')
    phone = data.get('phone')
    action = data.get('action', 'login')  # 默认为登录场景，可选值: login, register, reset_password
    
    # 优先使用邮箱发送验证码
    if email:
        try:
            # 连接数据库检查邮箱是否已注册
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor(dictionary=True)
            
            # 检查邮箱是否已注册
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            
            # 根据不同场景进行验证
            if action in ['login', 'reset_password'] and not user:
                # 登录和密码重置场景：邮箱必须已注册
                return jsonify({
                    "success": False,
                    "message": "This email is not registered. Please sign up first."
                }), 400
            elif action == 'register' and user:
                # 注册场景：邮箱不能已注册
                return jsonify({
                    "success": False,
                    "message": "This email is already registered. Please log in or use a different email."
                }), 400
            
            # 检查该邮箱的验证码发送频率
            cursor.execute("""
                SELECT created_at FROM email_verification_codes
                WHERE email = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (email,))
            
            last_code = cursor.fetchone()
            
            # 如果存在最近发送的验证码，检查时间间隔
            if last_code:
                last_sent_time = last_code['created_at']
                current_time = datetime.now()
                time_diff = (current_time - last_sent_time).total_seconds()
                
                # 限制60秒内只能发送一次验证码
                if time_diff < 60:
                    return jsonify({
                        "success": False,
                        "message": f"请求过于频繁，请在{60 - int(time_diff)}秒后再试"
                    }), 429
            
            # 导入验证码发送功能
            import sys
            import os
            
            # 获取项目根目录路径
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sys.path.append(root_dir)
            
            # 导入验证码发送模块
            from verification_email import send_verification_code as send_email_code
            
            # 生成验证码并发送
            result = send_email_code(email)
            
            if result['success']:
                # 将验证码保存到数据库
                verification_code = result['code']
                
                try:
                    # 检查验证码表是否已存在
                    cursor.execute("""
                        SELECT COUNT(*) as count 
                        FROM information_schema.tables 
                        WHERE table_schema = DATABASE() AND table_name = 'email_verification_codes'
                    """)
                    table_exists = cursor.fetchone()['count'] > 0
                    
                    # 如果表不存在，创建表
                    if not table_exists:
                        cursor.execute("""
                        CREATE TABLE IF NOT EXISTS email_verification_codes (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            email VARCHAR(255) NOT NULL,
                            code VARCHAR(10) NOT NULL,
                            created_at DATETIME NOT NULL,
                            expires_at DATETIME NOT NULL,
                            is_used BOOLEAN DEFAULT FALSE,
                            INDEX (email, code)
                        );
                        """)
                    
                    # 清除该邮箱之前的验证码
                    cursor.execute(
                        "DELETE FROM email_verification_codes WHERE email = %s",
                        (email,)
                    )
                    
                    # 插入新验证码，设置3分钟过期时间（原为2分钟），但用户提示不变
                    created_at = datetime.now()
                    expires_at = created_at + timedelta(minutes=3)
                    
                    cursor.execute(
                        """INSERT INTO email_verification_codes 
                        (email, code, created_at, expires_at) 
                        VALUES (%s, %s, %s, %s)""",
                        (email, verification_code, created_at, expires_at)
                    )
                    conn.commit()
                    
                    logger.info(f"Verification code sent to email: {email}")
                    return jsonify({
                        "success": True,
                        "message": "验证码已发送到您的邮箱，请查收"
                    })
                finally:
                    cursor.close()
                    conn.close()
            else:
                logger.error(f"Failed to send verification code to email {email}: {result['error']}")
                return jsonify({
                    "success": False, 
                    "message": f"发送验证码失败: {result['error']}"
                }), 500
                
        except Exception as e:
            logger.error(f"Error sending verification code to email: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                "success": False, 
                "message": "发送验证码失败，请稍后重试"
            }), 500
    # 如果没有提供邮箱，尝试使用手机发送验证码（已实现的模拟功能）
    elif phone:
        try:
            # 为了向后兼容，保留原有的手机验证码逻辑
            logger.info(f"Sending verification code to phone: {phone}")
            
            return jsonify({
                "success": True,
                "message": "验证码已发送到您的手机，请查收"
            })
        except Exception as e:
            logger.error(f"Error sending verification code to phone: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                "success": False, 
                "message": "发送验证码失败，请稍后重试"
            }), 500
    else:
        return jsonify({"success": False, "message": "请提供邮箱地址或手机号码"}), 400

def verify_code(data):
    """Verify code without logging in (used for registration)"""
    email = data.get('email')
    code = data.get('code')
    
    if not email or not code:
        return jsonify({
            "success": False, 
            "message": "请提供邮箱及验证码"
        }), 400
    
    try:
        # 连接数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        try:
            # 查询验证码记录
            cursor.execute("""
                SELECT * FROM email_verification_codes
                WHERE email = %s AND code = %s AND is_used = FALSE AND expires_at > NOW()
                ORDER BY created_at DESC LIMIT 1
            """, (email, code))
            
            verification = cursor.fetchone()
            
            if not verification:
                return jsonify({
                    "success": False,
                    "message": "验证码无效或已过期，请重新获取"
                }), 400
            
            # 标记验证码为已使用
            cursor.execute("UPDATE email_verification_codes SET is_used = TRUE WHERE id = %s", 
                          (verification['id'],))
            conn.commit()
            
            return jsonify({
                "success": True,
                "message": "验证码验证成功"
            })
        finally:
            cursor.close()
            conn.close()
        
    except Exception as e:
        logger.error(f"Error verifying code: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False, 
            "message": "验证失败，请稍后重试"
        }), 500

def verify_code_login(data):
    """Verify code and log user in"""
    email = data.get('email')
    phone = data.get('phone')
    code = data.get('code')
    
    # 优先使用邮箱验证
    if email and code:
        try:
            # 连接数据库
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor(dictionary=True)
            
            try:
                # 查询验证码记录
                cursor.execute("""
                    SELECT * FROM email_verification_codes
                    WHERE email = %s AND code = %s AND is_used = FALSE AND expires_at > NOW()
                    ORDER BY created_at DESC LIMIT 1
                """, (email, code))
                
                verification = cursor.fetchone()
                
                if not verification:
                    return jsonify({
                        "success": False,
                        "message": "验证码无效或已过期，请重新获取"
                    }), 400
                
                # 查询用户信息
                cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
                user = cursor.fetchone()
                
                if not user:
                    return jsonify({
                        "success": False,
                        "message": "This email is not registered. Please sign up first."
                    }), 400
                
                # 标记验证码为已使用
                cursor.execute("UPDATE email_verification_codes SET is_used = TRUE WHERE id = %s", 
                              (verification['id'],))
                conn.commit()
                
                # 创建用户会话
                session['user_id'] = user['id']
                session['username'] = user['username']
                
                return jsonify({
                    "success": True,
                    "message": "登录成功",
                    "redirect": "/"
                })
            finally:
                cursor.close()
                conn.close()
            
        except Exception as e:
            logger.error(f"Error verifying code for email: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                "success": False, 
                "message": "验证失败，请稍后重试"
            }), 500
    # 如果是通过手机验证（保留原有的模拟功能）
    elif phone and code:
        try:
            # 保留原有的模拟登录功能
            session['user_id'] = 999  # Demo user ID
            session['username'] = "Demo User"
            
            return jsonify({
                "success": True,
                "message": "登录成功",
                "redirect": "/"
            })
        except Exception as e:
            logger.error(f"Error verifying code for phone: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                "success": False, 
                "message": "验证失败，请稍后重试"
            }), 500
    else:
        return jsonify({
            "success": False, 
            "message": "请提供邮箱或手机号码以及验证码"
        }), 400

def reset_password(data):
    """Send password reset link"""
    email = data.get('email')
    
    if not email:
        return jsonify({"success": False, "message": "Email address is required"}), 400
    
    try:
        # 连接数据库验证邮箱是否存在
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # 检查邮箱是否存在于系统中
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if not user:
            # 邮箱不存在，但为了安全考虑，不向前端透露此信息
            logger.info(f"Reset password attempt for non-existent email: {email}")
            return jsonify({
                "success": True,
                "message": "如果此邮箱地址存在于我们的系统中，重置链接将发送到该邮箱"
            })
        
        # 导入验证码发送功能
        import sys
        import os
        
        # 获取项目根目录路径
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.append(root_dir)
        
        # 导入验证码发送模块
        from verification_email import send_verification_code
        
        # 生成验证码并发送
        result = send_verification_code(email)
        
        if result['success']:
            # 将验证码保存到数据库
            verification_code = result['code']
            
            # 检查验证码表是否已存在
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE() AND table_name = 'email_verification_codes'
            """)
            table_exists = cursor.fetchone()['count'] > 0
            
            # 如果表不存在，创建表
            if not table_exists:
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS email_verification_codes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    code VARCHAR(10) NOT NULL,
                    created_at DATETIME NOT NULL,
                    expires_at DATETIME NOT NULL,
                    is_used BOOLEAN DEFAULT FALSE,
                    INDEX (email, code)
                );
                """)
            
            # 清除该邮箱之前的验证码
            cursor.execute(
                "DELETE FROM email_verification_codes WHERE email = %s",
                (email,)
            )
            
            # 插入新验证码，设置3分钟过期时间
            created_at = datetime.now()
            expires_at = created_at + timedelta(minutes=3)
            
            cursor.execute(
                """INSERT INTO email_verification_codes 
                (email, code, created_at, expires_at) 
                VALUES (%s, %s, %s, %s)""",
                (email, verification_code, created_at, expires_at)
            )
            conn.commit()
            
            return jsonify({
                "success": True,
                "message": "如果此邮箱地址存在于我们的系统中，重置链接将发送到该邮箱"
            })
        else:
            # 发送失败，但为了安全考虑，不向前端透露具体错误
            logger.error(f"Failed to send verification code to email {email}: {result['error']}")
            return jsonify({
                "success": True,
                "message": "如果此邮箱地址存在于我们的系统中，重置链接将发送到该邮箱"
            })
    except Exception as e:
        logger.error(f"Error in reset password: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False, 
            "message": "系统错误，请稍后重试"
        }), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def require_login(request, public_routes):
    """Middleware to require login for protected routes"""
    if 'user_id' not in session and request.endpoint not in public_routes:
        if request.content_type == 'application/json':
            return jsonify({
                'success': False,
                'message': 'Please login to access this feature',
                'redirect': '/login'
            }), 401
        else:
            return redirect(url_for('login_page'))
    return None
