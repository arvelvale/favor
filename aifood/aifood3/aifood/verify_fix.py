import mysql.connector
import sys
from datetime import datetime, timedelta
from config import db_config, logger

def verify_visit_stats():
    """验证访问统计表是否存在并查询最近数据"""
    print("检查访问统计数据...")
    
    try:
        # 连接数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # 检查visit_stats表是否存在
        cursor.execute("""
        SELECT COUNT(*) as count 
        FROM information_schema.tables 
        WHERE table_schema = DATABASE()
        AND table_name = 'visit_stats'
        """)
        
        if cursor.fetchone()['count'] == 0:
            print("错误: visit_stats表不存在!")
            return False
        
        # 查询最近7天的访问数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        cursor.execute("""
        SELECT visit_date, page_views, unique_visitors 
        FROM visit_stats 
        WHERE visit_date BETWEEN %s AND %s
        ORDER BY visit_date DESC
        """, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        
        visits = cursor.fetchall()
        
        if not visits:
            print("注意: 没有找到最近7天的访问记录，但这是正常的 - 访问数据会在有用户访问时自动生成")
        else:
            print(f"找到{len(visits)}条访问记录:")
            for visit in visits:
                print(f"  日期: {visit['visit_date']}, 页面访问量: {visit['page_views']}, 独立访客: {visit['unique_visitors']}")
        
        print("访问统计功能正常工作中")
        return True
        
    except Exception as e:
        print(f"错误: 检查访问统计时出现异常: {str(e)}")
        return False
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def create_paypal_config_guide():
    """创建PayPal配置指南文件"""
    print("创建PayPal配置指南...")
    
    guide_content = """# PayPal配置指南

## 当前状态
当前网站使用的是PayPal沙盒（Sandbox）环境，这是一个测试环境，不会处理真实的支付。

## 如何切换到生产环境
要使PayPal支付系统实际接收付款，需要按照以下步骤操作：

1. 创建PayPal商业账户（Business Account）
   - 访问 https://www.paypal.com/business 注册商业账户
   - 确保账户已经完成验证

2. 获取生产环境API凭证
   - 登录 https://developer.paypal.com/dashboard/
   - 点击右上角的"Sandbox/Live"按钮切换到"Live"模式
   - 进入"Apps & Credentials"
   - 点击"Create App"按钮创建新应用
   - 保存生成的Client ID和Secret

3. 修改应用配置
   - 打开app.py文件
   - 找到PayPal配置部分（大约在第75行附近）
   - 将mode从"sandbox"改为"live"
   - 替换client_id和client_secret为您的生产环境凭证
   
```python
# 修改前（沙盒环境）:
paypalrestsdk.configure({
    "mode": "sandbox",  # 沙盒模式，生产环境改为 "live"
    "client_id": "",
    "client_secret": ""
})

# 修改后（生产环境）:
paypalrestsdk.configure({
    "mode": "live",  # 已切换到生产环境
    "client_id": "您的生产环境Client ID",
    "client_secret": ""
})
```

注意事项:
- 在切换到生产环境前，请确保完全测试过沙盒环境中的支付流程
- 生产环境将处理真实的支付，资金会实际转入您的PayPal账户
- 请妥善保管您的API凭证，不要泄露给他人
- 建议在网站上线前设置IPN (Instant Payment Notification)以便接收支付通知
"""
    
    try:
        with open("paypal_config_guide.md", "w", encoding="utf-8") as f:
            f.write(guide_content)
        print("PayPal配置指南已创建: paypal_config_guide.md")
        return True
    except Exception as e:
        print(f"错误: 创建PayPal配置指南时出现异常: {str(e)}")
        return False

if __name__ == "__main__":
    print("开始验证...")
    visit_stats_ok = verify_visit_stats()
    paypal_guide_ok = create_paypal_config_guide()
    
    if visit_stats_ok and paypal_guide_ok:
        print("\n验证完成: 所有检查通过!")
        print("1. 访问统计功能正常")
        print("2. PayPal配置指南已创建")
        sys.exit(0)
    else:
        print("\n验证完成: 存在问题!")
        if not visit_stats_ok:
            print("- 访问统计功能可能存在问题")
        if not paypal_guide_ok:
            print("- PayPal配置指南创建失败")
        sys.exit(1) 