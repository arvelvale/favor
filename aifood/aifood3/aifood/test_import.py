"""
测试脚本，用于验证模块导入是否正常工作
"""
print("开始测试导入...")

try:
    print("导入config模块...")
    from config import db_config, logger
    print("config模块导入成功!")
    
    print("导入database模块...")
    from database import init_database
    print("database模块导入成功!")
    
    print("导入admin_utils模块...")
    from admin_utils import record_user_visit, get_visit_stats, get_member_stats, get_recent_subscriptions
    print("admin_utils模块导入成功!")
    
    print("调用数据库初始化函数...")
    init_database()
    print("数据库初始化完成!")
    
    print("所有测试通过!")
except ImportError as e:
    print(f"导入错误: {str(e)}")
except Exception as e:
    print(f"测试失败: {str(e)}")
    import traceback
    traceback.print_exc() 