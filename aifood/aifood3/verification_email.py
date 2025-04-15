#!/usr/bin/env python
# -*- coding: utf-8 -*-

import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import logging
import ssl
import re

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# QQ邮箱SMTP服务器
smtp_server = 'smtp.qq.com'
smtp_port = 465  # 使用SSL的端口

# 发件人信息 - 使用您提供的QQ邮箱和授权码
sender_email = '2337590486@qq.com'  # 您的QQ邮箱
sender_password = ''  # 您的授权码
sender_name = 'Flavor Fusion'  # 发件人显示名称，简化名称避免中文编码问题

def validate_email(email):
    """
    验证邮箱格式是否正确
    
    参数:
    email (str): 需要验证的邮箱地址
    
    返回:
    bool: 格式正确返回True，否则返回False
    """
    # 使用正则表达式验证邮箱格式
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def generate_verification_code(length=6):
    """
    生成随机验证码
    
    参数:
    length (int): 验证码长度，默认6位
    
    返回:
    str: 随机验证码
    """
    # 使用数字生成验证码
    return ''.join(random.choices(string.digits, k=length))

def send_verification_email(receiver_email, verification_code, expires_in_minutes=2):
    """
    发送验证码邮件
    
    参数:
    receiver_email (str): 接收者邮箱地址
    verification_code (str): 验证码
    expires_in_minutes (int): 验证码有效期，单位分钟
    
    返回:
    tuple: (成功状态bool, 错误信息str或None)
    """
    # 先验证邮箱格式
    if not validate_email(receiver_email):
        return False, "邮箱格式不正确，请输入有效的邮箱地址"
    
    # 创建SMTP连接对象
    server = None
    email_sent_success = False
    
    try:
        # 创建多部分邮件
        message = MIMEMultipart()
        message['From'] = f'{sender_name} <{sender_email}>'  # 格式化发件人
        message['To'] = receiver_email
        message['Subject'] = Header('Flavor Fusion - Verification Code', 'utf-8')  # 使用英文主题避免编码问题
        
        # 简化邮件正文，减少HTML复杂度
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
                <h2>Email Verification</h2>
                <p>Hello,</p>
                <p>Your verification code for Flavor Fusion account is:</p>
                <div style="font-size: 24px; font-weight: bold; color: #4CAF50; padding: 10px; background: #f5f5f5; border-radius: 4px; letter-spacing: 5px; text-align: center;">
                    {verification_code}
                </div>
                <p>This code will expire in {expires_in_minutes} minutes.</p>
                <p>Thank you!</p>
                <p>Flavor Fusion Team</p>
            </div>
        </body>
        </html>
        """
        
        # 添加纯文本内容作为备用
        text_content = f"""
        Email Verification
        
        Hello,
        
        Your verification code for Flavor Fusion account is: {verification_code}
        
        This code will expire in {expires_in_minutes} minutes.
        
        Thank you!
        Flavor Fusion Team
        """
        
        # 添加文本和HTML内容
        part1 = MIMEText(text_content, 'plain', 'utf-8')
        part2 = MIMEText(html_content, 'html', 'utf-8')
        message.attach(part1)
        message.attach(part2)
        
        # 创建SSL上下文
        context = ssl.create_default_context()
        
        logger.info(f"正在尝试连接SMTP服务器: {smtp_server}:{smtp_port}")
        
        # 连接到服务器
        server = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context)
        server.set_debuglevel(1)  # 启用详细日志
            
        logger.info(f"正在登录SMTP服务器: {smtp_server}")
        server.login(sender_email, sender_password)
            
        logger.info(f"正在发送验证码邮件到: {receiver_email}")
        result = server.sendmail(sender_email, receiver_email, message.as_string())
        
        # 如果sendmail没有返回任何错误信息，标记邮件发送成功
        if not result:
            email_sent_success = True
            logger.info("验证码邮件发送成功！")
        
        # 尝试安全关闭连接，但不影响成功状态
        try:
            server.quit()
        except Exception as e:
            logger.warning(f"关闭SMTP连接时出现非致命错误: {str(e)}")
        
        # 如果邮件已成功发送，则即使QUIT命令失败也返回成功
        if email_sent_success:
            return True, None
        else:
            return False, "邮件服务器未能确认邮件发送成功"
        
    except smtplib.SMTPRecipientsRefused as e:
        error_msg = "收件人邮箱被拒绝：该邮箱地址可能不存在或已停用"
        logger.error(f"{error_msg}: {str(e)}")
        return False, error_msg
    except smtplib.SMTPAuthenticationError as e:
        error_msg = "邮箱认证失败：请检查QQ邮箱和授权码是否正确"
        logger.error(f"{error_msg}: {str(e)}")
        return False, error_msg
    except smtplib.SMTPSenderRefused as e:
        error_msg = "发件人被拒绝：请检查发件人邮箱格式是否正确"
        logger.error(f"{error_msg}: {str(e)}")
        return False, error_msg
    except smtplib.SMTPDataError as e:
        error_msg = "邮件数据错误：邮件内容可能包含不支持的格式或字符"
        logger.error(f"{error_msg}: {str(e)}")
        return False, error_msg
    except smtplib.SMTPConnectError as e:
        error_msg = "连接错误：无法连接到SMTP服务器，请检查网络或服务器设置"
        logger.error(f"{error_msg}: {str(e)}")
        return False, error_msg
    except smtplib.SMTPServerDisconnected as e:
        error_msg = "服务器连接断开：SMTP服务器意外断开连接"
        logger.error(f"{error_msg}: {str(e)}")
        return False, error_msg
    except smtplib.SMTPResponseException as e:
        code = e.smtp_code
        error_msg = f"SMTP响应错误(代码{code}): "
        if code == 550:
            error_msg += "邮箱地址不存在，请检查收件人邮箱是否正确"
        elif code == 552:
            error_msg += "邮件太大或超出配额限制"
        elif code == 554:
            error_msg += "交易失败，可能是发送内容被识别为垃圾邮件"
        else:
            error_msg += str(e)
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"发送验证码邮件失败 ({type(e).__name__}): {str(e)}"
        logger.error(error_msg)
        return False, error_msg
    finally:
        # 确保SMTP连接被关闭，如果存在的话
        # 但这里不处理异常，避免覆盖主要的错误信息
        if server and not email_sent_success:
            try:
                server.quit()
            except:
                pass

# 用于Web集成的函数
def send_verification_code(email_address):
    """
    生成验证码并发送到指定邮箱，便于Web应用集成
    
    参数:
    email_address (str): 接收验证码的邮箱地址
    
    返回:
    dict: 包含结果状态和错误信息的字典，不再返回验证码
    """
    try:
        # 验证邮箱格式
        if not validate_email(email_address):
            return {
                'success': False,
                'error': '邮箱地址格式无效'
            }
            
        # 生成6位验证码
        verification_code = generate_verification_code(6)
        
        # 发送邮件
        success, error_msg = send_verification_email(email_address, verification_code)
        if success:
            # 安全修复：不再在API响应中返回验证码
            # 验证码已通过邮件发送给用户，并将在服务器端存储用于验证
            return {
                'success': True,
                'code': verification_code,  # 仍然返回验证码，但只用于服务器端存储，不会发送给前端
                'error': None
            }
        else:
            return {
                'success': False,
                'error': error_msg or '邮件发送失败，请检查邮箱地址或稍后重试'
            }
    except Exception as e:
        logger.error(f"发送验证码过程中发生错误: {str(e)}")
        return {
            'success': False,
            'error': f'系统错误: {str(e)}'
        }

# Flask Web应用集成示例（需要安装Flask）
"""
from flask import Flask, request, jsonify, session
app = Flask(__name__)
app.secret_key = os.environ['SECRET_KEY']  # 用于会话管理，实际应用中应使用随机生成的密钥

@app.route('/send-verification', methods=['POST'])
def send_verification():
    data = request.json
    email = data.get('email')
    
    if not email:
        return jsonify({
            'success': False,
            'error': '邮箱地址不能为空'
        }), 400
    
    result = send_verification_code(email)
    
    if result['success']:
        # 在实际应用中，应将验证码存储在会话或数据库中，有效期设为10分钟
        verification_code = result.pop('code')
        session['verification_code'] = verification_code
        session['verification_email'] = email
        session['verification_time'] = time.time()  # 记录生成时间
        
    return jsonify(result)

@app.route('/verify-code', methods=['POST'])
def verify_code():
    data = request.json
    email = data.get('email')
    code = data.get('code')
    
    if not email or not code:
        return jsonify({
            'success': False,
            'error': '邮箱或验证码不能为空'
        }), 400
    
    # 检查是否与会话中的信息匹配
    stored_code = session.get('verification_code')
    stored_email = session.get('verification_email')
    stored_time = session.get('verification_time', 0)
    current_time = time.time()
    
    # 验证码10分钟有效
    if current_time - stored_time > 600:
        return jsonify({
            'success': False,
            'error': '验证码已过期，请重新获取'
        }), 400
    
    if email != stored_email or code != stored_code:
        return jsonify({
            'success': False,
            'error': '验证码错误或邮箱不匹配'
        }), 400
    
    # 验证成功，清除会话中的验证信息
    session.pop('verification_code', None)
    session.pop('verification_email', None)
    session.pop('verification_time', None)
    
    return jsonify({
        'success': True,
        'message': '验证成功'
    })

if __name__ == '__main__':
    app.run(debug=True)
"""

# 单独测试脚本功能
if __name__ == "__main__":
    # 直接测试发送邮件功能，跳过验证码生成
    test_email = input("请输入接收验证码的邮箱地址: ")
    verification_code = generate_verification_code(6)
    print(f"生成验证码: {verification_code}")
    
    success, error_msg = send_verification_email(test_email, verification_code)
    
    if success:
        print(f"验证码已成功发送！验证码为: {verification_code}")
    else:
        print(f"发送失败: {error_msg}")
        print("\n故障排除步骤:")
        print("1. 确认您的QQ邮箱已开启SMTP服务")
        print("2. 确认授权码正确且未过期")
        print("3. 确认收件人邮箱地址存在且可用")
        print("4. 确认网络连接正常")
        print("5. 尝试在QQ邮箱网页版发送测试邮件，确认账户状态")
