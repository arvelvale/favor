#!/usr/bin/env python
# -*- coding: utf-8 -*-

import mysql.connector
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

# Use the same environment-backed database configuration as the application.
import os
import sys
from pathlib import Path
from getpass import getpass
sys.path.insert(0, str(Path(__file__).with_name('aifood')))
from config import db_config

def add_test_user():
    """添加测试会员账号"""
    password = os.getenv('TEST_USER_PASSWORD') or getpass('测试账号密码（至少 12 位）: ')
    if len(password) < 12:
        raise ValueError('测试账号密码至少需要 12 位')
    # 连接数据库
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 用户信息
        username = 'infinity'
        email = 'system@test.com'
        
        # 检查用户是否存在
        cursor.execute('SELECT id FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()
        
        if not user:
            # 创建用户
            cursor.execute(
                'INSERT INTO users (username, email, password_hash, created_at, is_active) VALUES (%s, %s, %s, %s, %s)',
                (username, email, generate_password_hash(password), datetime.now(), True)
            )
            conn.commit()
            
            # 获取新用户ID
            cursor.execute('SELECT id FROM users WHERE username = %s', (username,))
            user = cursor.fetchone()
            print(f'已创建用户 {username}（ID: {user["id"]}）')
        else:
            print(f'用户 {username} 已存在（ID: {user["id"]}）')
        
        # 检查用户是否已有会员订阅
        cursor.execute('SELECT * FROM user_subscriptions WHERE user_id = %s AND is_active = TRUE', (user['id'],))
        subscription = cursor.fetchone()
        
        if not subscription:
            # 添加会员订阅
            start_date = datetime.now()
            end_date = start_date + timedelta(days=365)  # 设置为年度会员
            
            cursor.execute(
                '''INSERT INTO user_subscriptions 
                (user_id, plan_type, start_date, end_date, transaction_id, is_active, created_at) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                (user['id'], 'annual', start_date, end_date, 'TEST-TRANSACTION-123', True, datetime.now())
            )
            conn.commit()
            print(f'用户 {username} 已成功设置为年度会员，到期日期: {end_date.strftime("%Y-%m-%d")}')
        else:
            # 更新现有会员记录
            start_date = datetime.now()
            end_date = start_date + timedelta(days=365)
            
            cursor.execute(
                'UPDATE user_subscriptions SET end_date = %s, plan_type = %s WHERE user_id = %s AND is_active = TRUE',
                (end_date, 'annual', user['id'])
            )
            conn.commit()
            print(f'已更新用户 {username} 的会员状态，延长至一年，新到期日期: {end_date.strftime("%Y-%m-%d")}')
        
    except Exception as e:
        print(f'错误: {str(e)}')
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    add_test_user() 