# Flavor Fusion - AI美食助手与食谱管理系统

Flavor Fusion是一个基于AI技术的美食助手与食谱管理系统，为用户提供个性化的食谱推荐、创建和管理，以及会员订阅服务等功能。

## 功能概述

### 用户功能
- 用户注册与登录（支持邮箱验证码登录）
- 个人食谱创建与管理
- AI食谱生成与推荐
- 会员订阅（月度/年度计划）

### 管理功能
- 管理员控制面板
- 用户管理
- 会员管理
- 访问量与销售数据统计

## 技术架构

- 前端：HTML, CSS, JavaScript, Bootstrap 5
- 后端：Python Flask
- 数据库：MySQL
- AI组件：Claude API

## 项目结构

```
aifood/
├── app.py            # 主应用入口
├── auth.py           # 用户认证相关功能
├── admin_utils.py    # 管理员工具函数（访问统计、会员管理等）
├── database.py       # 数据库配置与初始化
├── static/           # 静态资源文件
│   ├── css/          # 样式表
│   ├── js/           # JavaScript文件
│   └── images/       # 图片资源
├── templates/        # HTML模板
│   ├── index.html    # 首页
│   ├── login.html    # 登录页
│   ├── register.html # 注册页
│   ├── admin.html    # 管理控制面板
│   ├── admin_users.html  # 用户管理页面
│   ├── admin_members.html # 会员管理页面
│   └── ...           # 其他模板文件
└── schema/           # 数据库架构定义
    └── users.sql     # 用户相关表结构
```

## 数据库结构

系统使用以下主要数据表：

- `users` - 用户基本信息
- `user_recipes` - 用户创建的食谱
- `user_subscriptions` - 用户订阅记录
- `visit_stats` - 网站访问量统计
- `user_visits` - 用户访问记录

## 新增功能说明

### 1. 用户访问量统计

系统实现了真实用户访问量的统计功能，而非使用随机数据：

- 每次用户登录或访问都会记录在`user_visits`表中
- 系统会自动更新用户的最后登录时间
- 访问量统计会计算页面浏览量(PV)和唯一访客数(UV)
- 控制面板显示实时的访问量数据和环比变化

实现方式：
- 使用`@app.before_request`装饰器自动跟踪用户访问
- 存储访问记录到数据库
- 通过`admin_utils.py`中的功能获取统计数据

### 2. 会员管理功能

新增了完整的会员管理系统：

- 管理员可以查看所有会员用户
- 显示会员统计数据（总会员数、月度会员、年度会员）
- 会员收入统计（精确到小数点后两位）
- 会员趋势图表
- 即将到期会员提醒

## 安装与运行

### 环境要求
- Python 3.8+
- MySQL 8.0+
- pip

### 安装步骤

1. 克隆代码库
```bash
git clone <repository-url>
cd aifood
```

2. 创建并激活虚拟环境
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

4. 配置数据库
- 创建MySQL数据库
- 导入`schema/users.sql`初始化数据库结构

5. 创建配置文件
- 复制`config.example.py`为`config.py`
- 填入数据库连接信息和其他配置参数

6. 运行应用
```bash
python app.py
```

## 使用说明

### 管理员登录
- 访问`/admin/login`进入管理员登录页面
- 默认管理员账号：Flavor
- 默认管理员密码：

### 控制面板
- 查看网站核心数据（访问量、销售额、用户数等）
- 监控实时趋势和环比变化

### 用户管理
- 查看和管理所有用户
- 编辑用户信息
- 查看用户详情（订阅记录、食谱等）

### 会员管理
- 查看所有会员及其订阅状态
- 监控会员订阅趋势
- 查看会员收入统计
- 查看即将到期的会员

## 数据统计说明

### 访问量统计
本系统采用真实用户访问数据统计，不使用随机数据或固定数据。访问统计实现方式：

1. 系统使用两个表来记录访问数据：
   - `visit_stats`: 记录每日的总页面浏览量(PV)和独立访客数(UV)
   - `user_visits`: 记录每个用户的访问历史

2. 在每次HTTP请求前，通过Flask的`@app.before_request`装饰器自动调用`track_user_visits`函数
   ```python
   @app.before_request
   def track_user_visits():
       if 'user_id' in session:
           record_user_visit(session['user_id'])
   ```

3. `record_user_visit`函数记录用户访问数据并更新总体统计
   - 更新用户的最后登录时间
   - 记录或更新用户当天的访问次数
   - 更新全站的总访问量和独立访客数

4. 显示原则：
   - 当没有访问记录时，显示为0，不使用随机数或默认值填充
   - 所有统计数据来源于数据库中的实际记录
   - 管理界面明确标注数据来源为"真实数据"

### PayPal支付系统
当前系统使用PayPal沙盒环境进行测试，这不是真实的支付环境。如需部署到生产环境并接收真实支付：

1. 需要创建PayPal商业账户
2. 在PayPal开发者平台创建生产环境应用并获取API凭证
3. 修改系统配置从沙盒模式切换到生产模式
4. 详细配置步骤参见项目根目录下的`paypal_config_guide.md`文件

## 系统维护

### 数据库备份
建议定期备份数据库，特别是在用户量增长时：
```
mysqldump -u [用户名] -p [数据库名] > backup.sql
```

### 访问统计数据
管理员后台可以查看真实的访问统计数据，包括：
- 每日页面浏览量(PV)和独立访客数(UV)
- 总访问量及增长率
- 用户访问记录

### 订阅数据
管理员后台可以查看订阅统计和历史记录：
- 活跃会员数量（总体/月度/年度）
- 即将到期的会员数
- 总收入和近期交易