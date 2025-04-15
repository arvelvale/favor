from flask import Flask, request, jsonify, render_template, Response, stream_with_context, session, redirect, url_for, g, send_from_directory, make_response
from flask_cors import CORS
import json
import os
import logging
import traceback
from dotenv import load_dotenv
import base64
import requests
from datetime import datetime, timedelta
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from config import db_config, logger
from database import init_database
from db_fix import fix_database
from api_clients import client, generate_recipe_images
from auth import (
    login_user, register_user, send_verification_code,
    verify_code_login, reset_password, require_login, verify_code
)
from werkzeug.utils import secure_filename
import paypalrestsdk
from paypalrestsdk import Payment
import random
from admin_utils import record_user_visit
from admin_routes import admin_bp
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
try:
    from verification_email import sender_email, sender_password, smtp_server, smtp_port, validate_email, logger as email_logger
except ImportError:
    email_logger.error("Could not import email sending configuration from verification_email.py")
    sender_email, sender_password, smtp_server, smtp_port = None, None, None, None
    def validate_email(email): return False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import our recipe generator
from test import generate_recipe, generate_recipe_stream

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)  # Enable CORS for all routes

# Register the admin blueprint
app.register_blueprint(admin_bp)

# Load ingredient database
try:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'ingredients.json'), 'r', encoding='utf-8') as f:
        INGREDIENTS_DATA = json.load(f)
        # Only use English ingredients
        INGREDIENTS = INGREDIENTS_DATA.get("en", [])
        logger.info(f"Successfully loaded ingredient database with {len(INGREDIENTS)} ingredients")
except Exception as e:
    logger.error(f"Error loading ingredient database: {str(e)}")
    # Fallback to empty list if file can't be loaded
    INGREDIENTS = []

# Initialize database on application startup
init_database()

# Set Flask session key
app.secret_key = os.environ.get('SECRET_KEY', '')

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads/avatars')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 配置PayPal SDK
paypalrestsdk.configure({
    "mode": "sandbox",  # 沙盒模式，生产环境改为 "live"
    "client_id": "",
    "client_secret": ""
})

def check_premium_status(user_id):
    """Check if user has an active premium subscription"""
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True, buffered=True)  # 使用buffered=True来避免未读结果错误
    
    try:
        cursor.execute("""
            SELECT * FROM user_subscriptions 
            WHERE user_id = %s AND is_active = TRUE AND end_date > NOW()
        """, (user_id,))
        
        subscription = cursor.fetchone()
        # 不需要额外的fetchall，因为cursor已经是buffered了
        
        return subscription is not None
    except Exception as e:
        logger.error(f"Error checking premium status: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

@app.route('/')
def index():
    # 确保用户的使用状态更新
    if 'user_id' in session:
        # 获取用户当天的使用情况和限制
        _, limit, used = check_usage_limit(session['user_id'])
    else:
        limit = 3  # 默认限制
        used = 0
    
    # 添加is_premium标志
    is_premium = False
    if 'user_id' in session:
        is_premium = check_premium_status(session['user_id'])
    
    return render_template('index.html', 
                         usage_limit=limit, 
                         usage_count=used,
                         is_premium=is_premium,
                         toast_css=url_for('static', filename='css/toast-message.css'),
                         toast_js=url_for('static', filename='js/toast-message.js'))

@app.route('/api/generate-recipe', methods=['POST'])
def api_generate_recipe():
    try:
        # 需要登录才能使用
        if 'user_id' not in session:
            return jsonify({'error': 'Please login to use this feature'}), 401
            
        # 检查使用限制
        allowed, limit, used = check_usage_limit(session['user_id'])
        if not allowed:
            return jsonify({
                'error': f'You have reached your daily limit of {limit} recipe generations. Upgrade to premium for unlimited access!',
                'limit_reached': True
            }), 403
        
        data = request.json
        ingredients = data.get('ingredients', [])
        temperature = data.get('temperature', 0.7)
        max_tokens = data.get('max_tokens', 2000)
        
        if not ingredients:
            return jsonify({'error': 'No ingredients provided'}), 400
        
        logger.info(f"Generating recipe with ingredients: {', '.join(ingredients)}")
        
        # 只有在用户未达到限制时才生成食谱
        recipe = generate_recipe(ingredients, temperature, max_tokens)
        
        # 增加使用次数
        increment_usage_count(session['user_id'])
        
        # 获取更新后的使用情况
        _, _, used_after = check_usage_limit(session['user_id'])
        
        # 返回剩余次数信息
        remaining = limit - used_after if limit != float('inf') else float('inf')
        return jsonify({
            'recipe': recipe,
            'usage': {
                'used': used_after,
                'limit': limit if limit != float('inf') else "unlimited",
                'remaining': remaining if remaining != float('inf') else "unlimited",
                'is_premium': limit == float('inf')
            }
        })
    except Exception as e:
        logger.error(f"Error in generate recipe API: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'An error occurred while generating the recipe. Please try again later.'}), 500

@app.route('/api/generate-recipe-stream', methods=['POST'])
def api_generate_recipe_stream():
    try:
        # 需要登录才能使用
        if 'user_id' not in session:
            return jsonify({'error': 'Please login to use this feature'}), 401
            
        # 检查使用限制
        allowed, limit, used = check_usage_limit(session['user_id'])
        if not allowed:
            return jsonify({
                'error': f'You have reached your daily limit of {limit} recipe generations. Upgrade to premium for unlimited access!',
                'limit_reached': True
            }), 403
        
        data = request.json
        ingredients = data.get('ingredients', [])
        temperature = data.get('temperature', 0.7)
        max_tokens = data.get('max_tokens', 2000)
        mode = data.get('mode', 'partial')
        instructions = data.get('instructions', '')
        
        if not ingredients:
            return jsonify({'error': 'No ingredients provided'}), 400
        
        logger.info(f"Streaming recipe generation with ingredients: {', '.join(ingredients)}")
        
        # 增加使用次数（只有在未达到限制时）
        increment_usage_count(session['user_id'])
        
        # 创建一个流式响应：首先发送开始事件
        def generate_with_header():
            # 发送开始事件
            start_data = {
                "status": "start",
                "message": "Starting recipe generation"
            }
            yield f"data: {json.dumps(start_data)}\n\n".encode('utf-8')
            
            # 创建流式响应，传递生成模式和指令
            stream = generate_recipe_stream(ingredients, temperature, max_tokens, mode, instructions)
            
            # 转发流式响应数据
            yield from stream
            
            # 发送完成事件
            done_data = {
                "status": "done"
            }
            yield f"data: {json.dumps(done_data)}\n\n".encode('utf-8')
            
        return Response(stream_with_context(generate_with_header()), content_type='text/event-stream')
    except Exception as e:
        logger.error(f"Error in stream recipe API: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'An error occurred while generating the recipe. Please try again later.'}), 500

@app.route('/api/generate-images', methods=['POST'])
def api_generate_images():
    try:
        data = request.json
        recipe_text = data.get('recipe', '')
        
        if not recipe_text:
            return jsonify({'error': 'No recipe text provided'}), 400
        
        logger.info(f"Generating images for recipe")
        result = generate_recipe_images(recipe_text)
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in generate images API: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'An error occurred while generating images. Please try again later.'}), 500

@app.route('/api/autocomplete', methods=['GET'])
def api_autocomplete():
    try:
        query = request.args.get('q', '').lower()
        
        if not query:
            return jsonify([])
        
        # Filter ingredients that match the query
        # 优先返回以查询词开头的结果，然后是包含查询词的结果
        starts_with = []
        contains = []
        
        for ing in INGREDIENTS:
            if ing.startswith(query):
                starts_with.append(ing)
            elif query in ing:
                contains.append(ing)
        
        # 组合结果，优先显示以查询词开头的匹配项
        matches = starts_with + contains
        
        # Return top 10 matches
        return jsonify(matches[:10])
    except Exception as e:
        logger.error(f"Error in autocomplete API: {str(e)}")
        return jsonify([]), 500

# Login and registration page routes
@app.route('/login')
def login_page():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register')
def register_page():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/verification-login')
def verification_login_page():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('verification_login.html')

@app.route('/forgot-password')
def forgot_password_page():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return redirect(url_for('verification_login_page'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('login_page'))

# API routes for authentication
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    return login_user(data, app)

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.json
    return register_user(data)

@app.route('/api/check-username', methods=['POST'])
def api_check_username():
    data = request.json
    username = data.get('username')
    
    if not username:
        return jsonify({"available": False, "message": "Username is required"}), 400
    
    try:
        # 连接数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True, buffered=True)  # 使用buffered=True
        
        # 查询用户名是否存在
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        if user:
            return jsonify({"available": False, "message": "This username is already taken"})
        else:
            return jsonify({"available": True})
    except Exception as e:
        logger.error(f"Error checking username: {str(e)}")
        return jsonify({"available": False, "message": "Error checking username availability"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/send-verification-code', methods=['POST'])
def api_send_verification_code():
    data = request.json
    return send_verification_code(data)

@app.route('/api/verify-code', methods=['POST'])
def api_verify_code():
    data = request.json
    return verify_code(data)

@app.route('/api/verify-code-login', methods=['POST'])
def api_verify_code_login():
    data = request.json
    return verify_code_login(data)

@app.route('/api/reset-password', methods=['POST'])
def api_reset_password():
    data = request.json
    return reset_password(data)

# Add authentication middleware
@app.before_request
def check_auth():
    # REMOVED ADMIN CHECK - Handled by admin_bp.before_request
    # if request.endpoint and (request.endpoint.startswith('admin_') or request.endpoint == 'admin'):
    #     if 'admin_id' not in session and request.endpoint != 'admin_login' and request.endpoint != 'admin_login_post':
    #         return redirect(url_for('admin_login'))
    #     return None  # 管理员已登录或正在访问登录页
        
    # List of routes that don't require login
    public_routes = [
        'login_page', 
        'register_page',
        'verification_login_page',
        'forgot_password_page',
        'api_login', 
        'api_register',
        'api_check_username',
        'api_send_verification_code',
        'api_verify_code',
        'api_verify_code_login',
        'api_reset_password',
        'static',
        'index',
        # Admin routes are now handled by the Blueprint, no need to list them here
        # 'admin', 
        # 'admin_login', 
        # 'admin_login_post'
    ]
    
    # Check if the request endpoint is part of the admin blueprint
    if request.endpoint and request.endpoint.startswith('admin.'):
         # Let the admin blueprint's before_request handle it
         return None 
    
    result = require_login(request, public_routes)
    if result is not None:
        return result

# User recipe routes and APIs
@app.route('/my-recipes')
def my_recipes():
    # Ensure user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    
    return render_template('my_recipes.html')

@app.route('/my-recipes/<int:recipe_id>')
def recipe_detail(recipe_id):
    # Ensure user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    
    try:
        # Connect to database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True, buffered=True)  # 使用buffered=True
        
        # Get recipe details
        cursor.execute("""
            SELECT * FROM user_recipes 
            WHERE id = %s AND user_id = %s
        """, (recipe_id, session['user_id']))
        
        recipe = cursor.fetchone()
        
        if not recipe:
            return redirect(url_for('my_recipes'))
        
        # 将Markdown内容转换为HTML (如果需要，可以使用Python的markdown库)
        # 这里我们在前端处理，确保recipe_content字段可用
        
        # 格式化日期
        if recipe['created_at']:
            recipe['created_at'] = recipe['created_at']
        
        # 确保ingredients是字符串，避免被当作字符序列处理
        if recipe['ingredients'] is None:
            recipe['ingredients'] = ''
            
        # 添加配方的文本内容，用于显示
        recipe['recipe_text'] = recipe['recipe_content']
        
        return render_template('recipe_detail.html', recipe=recipe)
    
    except Exception as e:
        logger.error(f"Error getting recipe details: {str(e)}")
        return redirect(url_for('my_recipes'))
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/my-recipes')
def api_my_recipes():
    # Ensure user is logged in
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Please login first"}), 401
    
    try:
        # Connect to database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True, buffered=True)  # 使用buffered=True
        
        # Get user's recipe list
        cursor.execute("""
            SELECT * FROM user_recipes 
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (session['user_id'],))
        
        recipes = cursor.fetchall()
        
        # Convert dates to strings for JSON serialization
        for recipe in recipes:
            if 'created_at' in recipe and recipe['created_at']:
                recipe['created_at'] = recipe['created_at'].isoformat()
        
        return jsonify({"success": True, "recipes": recipes})
    
    except Exception as e:
        logger.error(f"Error getting recipe list: {str(e)}")
        return jsonify({"success": False, "message": f"Error getting recipe list: {str(e)}"}), 500
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/save-recipe', methods=['POST'])
def api_save_recipe():
    # Ensure user is logged in
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Please login first"}), 401
    
    data = request.json
    recipe_name = data.get('recipe_name', 'Unnamed Recipe')
    recipe_content = data.get('recipe_content', '')
    ingredients = data.get('ingredients', '')
    
    if not recipe_content:
        return jsonify({"success": False, "message": "Recipe content cannot be empty"}), 400
    
    try:
        # Connect to database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True, buffered=True)  # 使用buffered=True
        
        # 检查最近5分钟内是否已经保存了相同名称和内容的食谱
        cursor.execute("""
            SELECT id FROM user_recipes 
            WHERE user_id = %s 
            AND recipe_name = %s 
            AND recipe_content = %s
            AND created_at > DATE_SUB(NOW(), INTERVAL 5 MINUTE)
        """, (session['user_id'], recipe_name, recipe_content))
        
        existing_recipe = cursor.fetchone()
        if existing_recipe:
            # 已存在相同的食谱，返回成功但不重复保存
            return jsonify({
                "success": True, 
                "message": "Recipe already saved",
                "recipe_id": existing_recipe['id']
            })
        
        # 保存新的食谱
        cursor.execute("""
            INSERT INTO user_recipes 
            (user_id, recipe_name, recipe_content, ingredients, created_at) 
            VALUES (%s, %s, %s, %s, NOW())
        """, (session['user_id'], recipe_name, recipe_content, ingredients))
        
        recipe_id = cursor.lastrowid
        conn.commit()
        
        return jsonify({
            "success": True, 
            "recipe_id": recipe_id,
            "message": "Recipe saved successfully"
        })
    
    except Exception as e:
        logger.error(f"Error saving recipe: {str(e)}")
        return jsonify({"success": False, "message": f"Failed to save recipe: {str(e)}"}), 500
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/delete-recipe/<int:recipe_id>', methods=['DELETE'])
def api_delete_recipe(recipe_id):
    # Ensure user is logged in
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Please login first"}), 401
    
    try:
        # Connect to database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(buffered=True)  # 使用buffered=True
        
        # Verify recipe ownership
        cursor.execute("""
            SELECT id FROM user_recipes 
            WHERE id = %s AND user_id = %s
        """, (recipe_id, session['user_id']))
        
        if not cursor.fetchone():
            return jsonify({"success": False, "message": "You don't have permission to delete this recipe"}), 403
        
        # Delete recipe
        cursor.execute("DELETE FROM user_recipes WHERE id = %s", (recipe_id,))
        conn.commit()
        
        return jsonify({"success": True, "message": "Recipe deleted"})
    
    except Exception as e:
        logger.error(f"Error deleting recipe: {str(e)}")
        return jsonify({"success": False, "message": f"Failed to delete recipe: {str(e)}"}), 500
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/profile')
def profile_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True, buffered=True)  # 使用buffered=True
        
        cursor.execute("""
            SELECT username, email, bio, profile_image 
            FROM users 
            WHERE id = %s
        """, (session['user_id'],))
        
        user = cursor.fetchone()
        
        if not user:
            return redirect(url_for('login_page'))
        
        timestamp = int(datetime.now().timestamp())
        return render_template('profile.html', 
                             username=user['username'],
                             email=user['email'],
                             bio=user['bio'] or '',
                             user_id=session['user_id'],
                             timestamp=timestamp)
    
    except Exception as e:
        logger.error(f"Error loading profile: {str(e)}")
        return redirect(url_for('index'))
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/update-avatar', methods=['POST'])
def api_update_avatar():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Please login first"}), 401
    
    if 'avatar' not in request.files:
        return jsonify({"success": False, "message": "No file provided"}), 400
    
    file = request.files['avatar']
    if file.filename == '':
        return jsonify({"success": False, "message": "No file selected"}), 400
    
    if file and allowed_file(file.filename):
        try:
            # 读取图片文件数据并转换为Base64
            image_data = file.read()
            encoded_image = base64.b64encode(image_data).decode('utf-8')
            
            # 连接数据库
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor(dictionary=True, buffered=True)  # 使用buffered=True
            
            # 更新数据库中的头像Base64数据
            cursor.execute("""
                UPDATE users 
                SET profile_image = %s 
                WHERE id = %s
            """, (encoded_image, session['user_id']))
            
            conn.commit()
            
            # 生成临时文件名用于URL（不保存实际文件）
            avatar_url = f'/api/avatar/{session["user_id"]}?v={int(datetime.now().timestamp())}'
            
            # 记录成功信息
            logger.info(f"Avatar updated successfully for user {session['user_id']}")
            
            return jsonify({
                "success": True,
                "avatar_url": avatar_url
            })
        except Exception as e:
            logger.error(f"Error updating avatar: {str(e)}")
            logger.error(traceback.format_exc())  # 添加详细错误跟踪
            return jsonify({"success": False, "message": f"Failed to update avatar: {str(e)}"}), 500
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
    
    return jsonify({"success": False, "message": "Unsupported file type"}), 400

@app.route('/api/update-profile', methods=['POST'])
def api_update_profile():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Please login first"}), 401
    
    data = request.json
    email = data.get('email')
    bio = data.get('bio')
    
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users 
            SET email = %s, bio = %s 
            WHERE id = %s
        """, (email, bio, session['user_id']))
        
        conn.commit()
        
        return jsonify({"success": True})
        
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        return jsonify({"success": False, "message": "Failed to update profile"}), 500
        
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/premium')
def premium_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    
    # Check if user already has an active subscription
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True, buffered=True)  # 使用buffered=True避免未读结果错误
    
    try:
        # 修改查询语句，确保获取最新的有效订阅记录
        cursor.execute("""
            SELECT * FROM user_subscriptions 
            WHERE user_id = %s AND is_active = TRUE AND end_date > NOW()
            ORDER BY end_date DESC LIMIT 1
        """, (session['user_id'],))
        
        subscription = cursor.fetchone()
        # 不需要额外的fetchall，因为cursor已经是buffered了
        
        return render_template('premium.html', subscription=subscription)
    except Exception as e:
        logger.error(f"Error checking subscription: {str(e)}")
        return render_template('premium.html', subscription=None)
    finally:
        cursor.close()
        conn.close()

@app.route('/api/create-paypal-order', methods=['POST'])
def create_paypal_order():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Please login first"}), 401
    
    # 获取计划类型
    data = request.json
    plan_type = data.get('plan_type')
    
    if not plan_type or plan_type not in ['monthly', 'annual']:
        return jsonify({"success": False, "message": "Invalid plan type"}), 400
    
    # 设置金额
    amount = '7.90' if plan_type == 'monthly' else '79.90'
    
    # 创建PayPal支付
    payment = Payment({
        "intent": "sale",
        "payer": {
            "payment_method": "paypal"
        },
        "redirect_urls": {
            "return_url": f"{request.host_url}api/capture-paypal-order",
            "cancel_url": f"{request.host_url}premium?cancelled=true"
        },
        "transactions": [{
            "amount": {
                "total": amount,
                "currency": "USD"
            },
            "description": f"Flavor Fusion {plan_type.capitalize()} Premium Plan"
        }]
    })
    
    # 创建支付
    try:
        if payment.create():
            logger.info(f"Payment created: {payment.id} for user {session['user_id']} ({plan_type} plan)")
            
            # 获取批准URL
            approval_url = None
            for link in payment.links:
                if link.rel == "approval_url":
                    approval_url = link.href
                    break
                    
            if not approval_url:
                logger.error(f"No approval URL found in payment {payment.id}")
                return jsonify({"success": False, "message": "Failed to create payment: No approval URL"}), 500
                
            return jsonify({
                "success": True,
                "order_id": payment.id,
                "approval_url": approval_url
            })
        else:
            logger.error(f"Payment creation failed: {payment.error}")
            return jsonify({"success": False, "message": f"Failed to create payment: {payment.error}"}), 500
    except Exception as e:
        logger.error(f"Error creating payment: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "message": f"Failed to create payment: {str(e)}"}), 500

@app.route('/api/capture-paypal-order')
def capture_paypal_order():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    
    payment_id = request.args.get('paymentId')
    payer_id = request.args.get('PayerID')
    
    if not payment_id or not payer_id:
        logger.error(f"Missing paymentId or PayerID: {request.args}")
        return redirect(url_for('premium_page', error='invalid_token'))
    
    try:
        # 执行支付
        payment = Payment.find(payment_id)
        if payment.execute({"payer_id": payer_id}):
            # 从payment对象中提取计划类型
            plan_type = 'monthly'  # 默认值
            for transaction in payment.transactions:
                if 'Annual' in transaction.description:
                    plan_type = 'annual'
            
            transaction_id = payment_id
            
            # 连接数据库
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor(dictionary=True)
            
            try:
                # 检查用户是否有现有有效订阅
                cursor.execute("""
                    SELECT * FROM user_subscriptions 
                    WHERE user_id = %s AND is_active = TRUE AND end_date > NOW()
                    ORDER BY end_date DESC LIMIT 1
                """, (session['user_id'],))
                
                existing_subscription = cursor.fetchone()
                
                # 确保消费所有查询结果
                cursor.fetchall()  # 读取所有剩余结果以防止"Unread result found"错误
                
                # 计算订阅期限
                if existing_subscription:
                    # 如果有现有订阅，从现有订阅结束日期开始累加
                    start_date = existing_subscription['end_date']
                else:
                    # 如果没有现有订阅，从当前时间开始计算
                    start_date = datetime.now()
                
                # 根据订阅类型计算结束日期
                if plan_type == 'monthly':
                    end_date = start_date + timedelta(days=30)
                else:  # annual
                    end_date = start_date + timedelta(days=365)
                
                # 添加新订阅
                cursor.execute("""
                    INSERT INTO user_subscriptions 
                    (user_id, plan_type, start_date, end_date, transaction_id, is_active, created_at) 
                    VALUES (%s, %s, %s, %s, %s, TRUE, NOW())
                """, (
                    session['user_id'], 
                    plan_type, 
                    start_date, 
                    end_date, 
                    transaction_id
                ))
                
                conn.commit()
                logger.info(f"Subscription added for user {session['user_id']}: {plan_type} plan, ending {end_date}")
                
                # 根据是否为扩展订阅设置不同的URL参数
                if existing_subscription:
                    return redirect(url_for('premium_page', status='success', extended='true'))
                else:
                    return redirect(url_for('premium_page', status='success'))
                
            except Exception as e:
                logger.error(f"Error saving subscription: {str(e)}")
                return redirect(url_for('premium_page', error='database'))
            finally:
                cursor.close()
                conn.close()
        else:
            logger.error(f"Payment execution failed: {payment.error}")
            return redirect(url_for('premium_page', error='payment_execution'))
    except Exception as e:
        logger.error(f"Error processing payment: {str(e)}")
        logger.error(traceback.format_exc())
        return redirect(url_for('premium_page', error='payment_processing'))

@app.route('/api/check-subscription-status')
def check_subscription_status():
    if 'user_id' not in session:
        return jsonify({"is_premium": False})
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM user_subscriptions 
            WHERE user_id = %s AND is_active = TRUE AND end_date > NOW()
        """, (session['user_id'],))
        
        subscription = cursor.fetchone()
        
        # 确保消费所有查询结果
        cursor.fetchall()  # 读取所有剩余结果以防止"Unread result found"错误
        
        if subscription:
            return jsonify({
                "is_premium": True,
                "plan_type": subscription['plan_type'],
                "end_date": subscription['end_date'].isoformat() if subscription['end_date'] else None
            })
        else:
            return jsonify({"is_premium": False})
            
    except Exception as e:
        logger.error(f"Error checking subscription status: {str(e)}")
        return jsonify({"is_premium": False, "error": str(e)})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/get-usage-info')
def get_usage_info():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Please login first"}), 401
    
    allowed, limit, used = check_usage_limit(session['user_id'])
    remaining = limit - used if limit != float('inf') else float('inf')
    
    return jsonify({
        "success": True,
        "usage": {
            "used": used,
            "limit": limit if limit != float('inf') else "unlimited",
            "remaining": remaining if remaining != float('inf') else "unlimited",
            "is_premium": limit == float('inf')
        }
    })

@app.context_processor
def inject_user_data():
    """在所有模板中注入用户数据"""
    data = {'user_id': None, 'timestamp': int(datetime.now().timestamp())}
    
    if 'user_id' in session:
        data['user_id'] = session['user_id']
    
    return data

def check_usage_limit(user_id):
    """检查用户是否超过了使用限制"""
    # 检查用户是否是会员
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 先检查是否是会员
        cursor.execute("""
            SELECT * FROM user_subscriptions 
            WHERE user_id = %s AND is_active = TRUE AND end_date > NOW()
        """, (user_id,))
        
        subscription = cursor.fetchone()
        # 确保消费所有结果
        cursor.fetchall()
        
        # 如果是会员，返回无限制
        if subscription:
            logger.info(f"User {user_id} is a premium member with unlimited access")
            return True, float('inf'), 0
            
        # 非会员，检查今日使用次数
        today = datetime.now().date()
        cursor.execute("""
            SELECT * FROM usage_limits
            WHERE user_id = %s AND date = %s
        """, (user_id, today))
        
        usage = cursor.fetchone()
        # 确保消费所有结果
        cursor.fetchall()
        
        # 如果没有记录，创建一条
        if not usage:
            cursor.execute("""
                INSERT INTO usage_limits (user_id, date, usage_count)
                VALUES (%s, %s, 0)
            """, (user_id, today))
            conn.commit()
            logger.info(f"Created new usage record for user {user_id}")
            return True, 3, 0
            
        # 检查是否超过限制
        if usage['usage_count'] >= 3:
            logger.info(f"User {user_id} has reached daily limit: {usage['usage_count']}/3")
            return False, 3, usage['usage_count']
            
        logger.info(f"User {user_id} usage: {usage['usage_count']}/3")
        return True, 3, usage['usage_count']
        
    except Exception as e:
        logger.error(f"Error checking usage limit: {str(e)}")
        logger.error(traceback.format_exc())
        # 出错时默认允许使用
        return True, 3, 0
    finally:
        cursor.close()
        conn.close()

def increment_usage_count(user_id):
    """增加用户的使用次数"""
    # 先检查用户是否是会员或已达到限制
    allowed, limit, used = check_usage_limit(user_id)
    
    # 如果是会员，不需要增加使用次数
    if limit == float('inf'):
        logger.info(f"Premium user {user_id} - not counting usage")
        return
    
    # 如果已达到限制，也不再增加
    if not allowed:
        logger.info(f"User {user_id} already at limit - not incrementing")
        return
        
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    try:
        today = datetime.now().date()
        
        # 检查是否有记录
        cursor.execute("""
            SELECT * FROM usage_limits
            WHERE user_id = %s AND date = %s
        """, (user_id, today))
        
        has_record = cursor.fetchone() is not None
        # 确保消费所有结果
        cursor.fetchall()
        
        if has_record:
            # 更新记录
            cursor.execute("""
                UPDATE usage_limits
                SET usage_count = usage_count + 1
                WHERE user_id = %s AND date = %s
            """, (user_id, today))
            logger.info(f"Incremented usage count for user {user_id}")
        else:
            # 创建记录
            cursor.execute("""
                INSERT INTO usage_limits (user_id, date, usage_count)
                VALUES (%s, %s, 1)
            """, (user_id, today))
            logger.info(f"Created new usage record for user {user_id} with count 1")
            
        conn.commit()
    except Exception as e:
        logger.error(f"Error incrementing usage count: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        cursor.close()
        conn.close()

# 向templates目录中添加一个辅助函数，用于包含toast-message
@app.context_processor
def utility_processor():
    def get_toast_files():
        return {
            'css': url_for('static', filename='css/toast-message.css'),
            'js': url_for('static', filename='js/toast-message.js')
        }
    
    return dict(get_toast_files=get_toast_files)

@app.route('/api/avatar/<int:user_id>')
def get_avatar(user_id):
    try:
        # 连接数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True, buffered=True)  # 使用buffered=True
        
        # 查询用户头像数据
        cursor.execute("SELECT profile_image FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user or not user['profile_image']:
            # 如果用户没有头像，返回默认头像
            return send_from_directory(os.path.join(app.root_path, 'static/images'), 'default-avatar.png', mimetype='image/png')
        
        try:
            # 尝试解码Base64数据
            image_data = base64.b64decode(user['profile_image'])
        except:
            # 如果解码失败，可能是BLOB数据，直接使用
            image_data = user['profile_image']
        
        # 返回二进制图片数据
        response = make_response(image_data)
        response.headers.set('Content-Type', 'image/jpeg')  # 设置为适当的MIME类型
        response.headers.set('Cache-Control', 'no-cache, no-store, must-revalidate')
        response.headers.set('Pragma', 'no-cache')
        response.headers.set('Expires', '0')
        
        return response
    except Exception as e:
        logger.error(f"Error retrieving avatar: {str(e)}")
        return send_from_directory(os.path.join(app.root_path, 'static/images'), 'default-avatar.png', mimetype='image/png')
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.before_request
def track_user_visits():
    """记录用户访问数据 (This needs to stay here for all users)"""
    # Don't track visits within the admin section itself
    if request.endpoint and not request.endpoint.startswith('admin.'):
        if 'user_id' in session:
            record_user_visit(session['user_id'])

@app.route('/feedback')
def feedback_page():
    """Render the feedback page."""
    # Include user info if logged in, otherwise defaults
    user_info = {
        'user_id': session.get('user_id'),
        'username': session.get('username'),
        'timestamp': int(datetime.now().timestamp())
    }
    return render_template('feedback.html', **user_info)

def send_feedback_email(name, user_email, message):
    """Sends the collected feedback to the designated admin email."""
    if not sender_email or not sender_password:
        email_logger.error("Email credentials not configured. Cannot send feedback.")
        return False, "Email service is not configured."

    admin_email = 'djia54995@gmail.com' # Your designated feedback email
    subject = f"Flavor Fusion Feedback from {user_email}"
    
    # Construct email body
    body = f"""New feedback received from Flavor Fusion:

Name: {name if name else 'Not provided'}
Email: {user_email}

Message:
{message}
"""
    
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = f"Flavor Fusion Feedback <{sender_email}>" # Use app name as sender
    msg['To'] = admin_email

    server = None # Initialize server to None
    try:
        email_logger.info(f"Attempting to connect to SMTP server {smtp_server}:{smtp_port}")
        server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=15) # Increased timeout slightly
        email_logger.info(f"Attempting to login with {sender_email}")
        server.login(sender_email, sender_password)
        email_logger.info(f"Attempting to send feedback email to {admin_email}")
        server.sendmail(sender_email, [admin_email], msg.as_string())
        email_logger.info("Feedback email successfully sent (sendmail command completed).")
        # Consider the email sent if sendmail completes without error
        return True, "Success"

    except smtplib.SMTPAuthenticationError:
        email_logger.error("SMTP Authentication Error. Check QQ email/password.")
        return False, "Email server authentication failed."
    except smtplib.SMTPConnectError as e:
        email_logger.error(f"SMTP Connection Error: {e}")
        return False, "Could not connect to email server."
    except smtplib.SMTPSenderRefused as e:
         email_logger.error(f"Sender email {sender_email} refused: {e}")
         return False, "Sender email address refused."
    except smtplib.SMTPRecipientsRefused as e:
         # Note: This usually returns a dictionary of refused recipients
         email_logger.error(f"Recipient email {admin_email} refused: {e}")
         return False, "Recipient email address refused."
    except smtplib.SMTPDataError as e:
         email_logger.error(f"SMTP Data Error: {e}")
         return False, "Invalid email content or format."
    except Exception as e:
        # Catch other potential errors during connection/login/sendmail
        email_logger.error(f"Error during email sending process: {str(e)}")
        import traceback
        email_logger.error(traceback.format_exc())
        return False, f"An unexpected error occurred during sending: {str(e)}"
    finally:
        # Always try to quit the server connection if it was established
        if server:
            try:
                email_logger.info("Attempting to quit SMTP server connection.")
                server.quit()
                email_logger.info("SMTP connection closed successfully.")
            except smtplib.SMTPResponseException as e:
                # Log the QUIT error but don't necessarily fail the operation if sendmail succeeded
                email_logger.warning(f"Error during SMTP QUIT command (Code: {e.smtp_code}): {e.smtp_error}. Email might have already been sent.")
            except Exception as e:
                email_logger.warning(f"Unexpected error during SMTP QUIT: {str(e)}")

@app.route('/api/send-feedback', methods=['POST'])
def handle_feedback():
    """API endpoint to receive and email feedback."""
    data = request.json
    name = data.get('name')
    user_email = data.get('email')
    message = data.get('message')

    if not user_email or not message:
        return jsonify({"success": False, "message": "Email and message are required fields."}), 400
    
    # Validate email format on the server side as well
    if not validate_email(user_email):
         return jsonify({"success": False, "message": "Invalid email format provided."}), 400

    success, status_message = send_feedback_email(name, user_email, message)

    if success:
        return jsonify({"success": True})
    else:
        # Return a generic error message to the user, log the specific error
        logger.error(f"Failed to send feedback email. Reason: {status_message}")
        return jsonify({"success": False, "message": "Failed to send feedback due to a server error. Please try again later."}), 500

if __name__ == "__main__":
    logger.info("Starting Flask application...")
    # 初始化数据库等操作可以保留
    init_database()
    fix_database()
    # 当使用 Gunicorn 时，不需要 Flask 自带的 app.run()
    try:
        # 尝试使用默认端口5000
        app.run(debug=True, host='0.0.0.0', port=5000)
    except Exception as e:
        logger.error(f"Error starting on port 5000: {str(e)}")
        try:
            # 如果5000端口失败，尝试使用5001端口
            logger.info("Trying alternative port 5001...")
            app.run(debug=True, host='0.0.0.0', port=5001)
        except Exception as e:
            logger.error(f"Error starting on port 5001: {str(e)}")
            logger.error("Failed to start the application on both ports.")
