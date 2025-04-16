# Flavor Fusion - AI美食助手与食谱管理系统

Flavor Fusion是一个基于AI技术的美食助手与食谱管理系统，为用户提供个性化的食谱生成、管理、分享，以及会员订阅服务等功能。

## 功能概述

### 用户功能
- **用户认证**：支持用户名密码注册/登录，以及邮箱验证码注册/登录/重置密码。
- **AI 食谱生成**：
    - 输入食材，利用AI（DeepSeek API）生成食谱。
    - 支持流式输出，逐步展示食谱内容。
    - 提供参数调整（如创意程度 temperature）。
    - AI 生成食谱图片（通过 `api_clients.py`）。
- **食谱管理**：
    - 保存生成的食谱到个人账户。
    - 查看、编辑、删除个人食谱。
    - 食材自动补全提示。
- **个人中心**：
    - 查看和编辑个人资料（邮箱、简介）。
    - 上传和更换头像。
- **会员系统**：
    - 提供免费额度和付费会员（月度/年度）。
    - 非会员每日有生成次数限制，会员无限制。
    - 通过 PayPal (沙盒环境) 进行支付。
- **反馈系统**：用户可以提交使用反馈。

### 管理功能 (通过 `/admin` 路径访问)
- **管理员登录**
- **数据看板**：
    - 实时访问量统计 (PV/UV) 及环比变化。
    - 销售额统计及环比变化。
    - 用户增长统计及环比变化。
    - 各项数据的历史图表。
- **用户管理**：
    - 查看、搜索、编辑、删除用户。
    - 查看用户详细信息（订阅、食谱等）。
- **会员管理**：
    - 查看、搜索会员。
    - 查看会员统计（总数、类型分布）。
    - 收入统计和趋势。
    - 查看即将到期的会员。
- **访问统计**：查看详细的每日 PV/UV 数据。
- **销售统计**：查看详细的每日销售额和交易数据。
- **系统配置**：(待实现)

## 技术架构

- **前端**：HTML, CSS, JavaScript, Bootstrap 5, jQuery, Chart.js (用于图表)
- **后端**：Python (Flask 框架)
- **数据库**：MySQL
- **AI模型接口**：DeepSeek API (通过 `api_clients.py` 调用)
- **支付接口**：PayPal REST SDK (沙盒环境)
- **邮件服务**：SMTP (用于发送验证码和反馈邮件，需配置 `verification_email.py`)
- **依赖管理**：pip

## 项目结构

```
aifood/aifood3/aifood/
├── app.py                 # Flask 主应用文件，包含核心路由和逻辑
├── admin_routes.py        # 管理后台相关的路由和逻辑
├── admin_utils.py         # 管理后台使用的工具函数（统计计算等）
├── auth.py                # 用户认证（注册、登录、验证码、密码重置）相关逻辑
├── api_clients.py         # 调用外部 API（如 DeepSeek）的客户端
├── database.py            # 数据库初始化、表结构创建
├── db_fix.py              # 数据库结构修复脚本（可选）
├── config.py              # 应用配置（数据库、API代理、调试模式等）
├── test.py                # AI 食谱生成的核心逻辑 (被 app.py 调用)
├── verification_email.py  # 邮件发送配置和逻辑
├── requirements.txt       # 项目所需的 Python 依赖库
├── .env                   # 环境变量配置文件（存储敏感信息如 API Key）
├── README.md              # 项目说明文件 (就是你正在看的这个)
├── deployment_guide.md    # 部署指南
├── paypal_config_guide.md # PayPal 配置指南
├── proxy_guide.md         # 代理配置指南
├── schema/                # 包含数据库结构的 SQL 文件 (仅作参考，实际由 database.py 创建)
│   └── users.sql
├── static/                # 存放 CSS, JavaScript, Images 等静态文件
│   ├── css/
│   ├── js/
│   ├── images/
│   └── uploads/           # 用户上传文件（如头像）的目录
│       └── avatars/
├── templates/             # 存放 Flask 使用的 HTML 模板文件
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── admin/             # 管理后台相关模板
│   │   ├── admin_base.html
│   │   ├── admin_dashboard.html
│   │   └── ...
│   └── ...                # 其他用户界面模板
├── data/                  # 存放数据文件
│   └── ingredients.json   # 食材数据库 (用于自动补全)
├── __pycache__/           # Python 缓存目录 (可忽略)
└── (其他辅助脚本和文件)
    ├── add_test_user.py
    ├── create_verification_table.sql
    ├── init_db.py
    ├── test_import.py
    └── verify_fix.py
```
*注意：项目外层还有 `aifood/aifood3/venv/` 或 `.venv/` 等虚拟环境目录，这里未列出。*

## 数据库结构

系统使用 MySQL 数据库，包含以下主要数据表（具体字段和约束由 `database.py` 定义和创建）：

- `users`: 存储用户基本信息（用户名、邮箱、密码哈希、头像、简介等）。
- `user_recipes`: 存储用户保存的食谱（名称、内容、食材、创建时间等）。
- `user_subscriptions`: 存储用户的会员订阅记录（用户ID、计划类型、起止日期、交易ID、状态等）。
- `usage_limits`: 存储非会员用户的每日 AI 功能使用次数。
- `email_verification_codes`: 存储邮箱验证码及其状态。
- `visit_stats`: 按日存储网站的页面浏览量 (PV) 和独立访客数 (UV)。
- `user_visits`: 记录每个用户的访问日期和次数。
- `sales_stats`: 按日存储销售额和交易数量。

## 安装与运行

### 环境要求
- Python 3.8+
- MySQL 8.0+
- pip (Python 包管理器)

### 安装步骤

1.  **克隆代码库**
    ```bash
    # 替换 <repository-url> 为你的仓库地址
    git clone <repository-url>
    cd aifood/aifood3/aifood # 进入项目核心目录
    ```

2.  **创建并激活虚拟环境** (推荐)
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```
    *如果你使用的是其他虚拟环境工具（如 conda），请相应调整命令。*

3.  **安装依赖**
    ```bash
    pip install -r requirements.txt
    ```

4.  **配置环境变量**
    - 复制 `.env.example` 文件 (如果存在) 或手动创建 `.env` 文件。
    - 在 `.env` 文件中填入必要的环境变量，至少需要 DeepSeek API 密钥：
      ```env
      DEEPSEEK_API_KEY=你的DeepSeek_API密钥
      SECRET_KEY=设置一个复杂且随机的字符串用于Flask Session加密
      # 其他可选环境变量，如数据库密码等，虽然可以在 config.py 硬编码，但推荐放入 .env
      # DB_PASSWORD=你的数据库密码
      ```

5.  **配置应用设置 (`config.py`)**
    - 打开 `config.py` 文件。
    - **数据库连接**：检查 `db_config` 字典中的数据库连接信息 (`host`, `user`, `password`, `database`, `port`) 是否正确。如果数据库密码放在了 `.env` 文件，需要修改 `config.py` 来读取它 (例如: `password=os.getenv('DB_PASSWORD', '默认密码')`)。
    - **API 代理**：如果需要通过代理访问 DeepSeek API，请设置 `HTTP_PROXY` 和 `HTTPS_PROXY`。
    - **邮箱服务**：打开 `verification_email.py` 文件，配置你的 SMTP 服务器信息、发件人邮箱和密码。**注意：直接在代码中存储密码存在安全风险，建议使用环境变量或其他更安全的方式管理。**

6.  **创建数据库**
    - 手动连接到你的 MySQL 服务器。
    - 创建项目所需的数据库（数据库名称在 `config.py` 的 `db_config` 中定义，默认为 `recipe_app`）：
      ```sql
      CREATE DATABASE IF NOT EXISTS recipe_app DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
      ```
    *注意：数据表结构将在首次运行应用时由 `database.py` 中的 `init_database()` 函数自动创建。*

7.  **运行应用**
    ```bash
    python app.py
    ```
    应用启动后，会监听 `0.0.0.0` 地址的指定端口（默认为 5000 或 5001）。你可以在浏览器中访问 `http://localhost:5000` (或相应端口) 来查看应用。

## 使用说明

### 管理员登录
- 访问 `/admin/login` 进入管理员登录页面。
- **默认管理员账号**：`Flavor`
- **默认管理员密码**：`` (首次登录后强烈建议修改密码)

### 控制面板
- 访问 `/admin` (登录后)。

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
建议定期备份数据库，特别是在用户量增长或进行重要更新前：
```bash
# 将 [用户名], [密码], [数据库名], backup.sql 替换为实际值
# 如果密码包含特殊字符，可能需要特殊处理或在提示时输入
mysqldump -u [用户名] -p[密码] [数据库名] > backup.sql
# 或者省略 -p[密码]，命令执行后会提示输入密码
mysqldump -u [用户名] -p [数据库名] > backup.sql
```

### 日志文件
应用运行日志会输出到控制台。对于生产环境部署，建议配置日志记录到文件，并定期轮转和归档日志文件。可以修改 `config.py` 或 `app.py` 中的日志配置来实现。

### 依赖更新
定期检查并更新项目依赖库，以获取安全补丁和新功能：
```bash
pip list --outdated
pip install --upgrade <package_name>
# 更新后记得重新生成 requirements.txt
pip freeze > requirements.txt
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

### 清理旧数据 (可选)
根据需要，可以考虑定期清理或归档旧的访问记录 (`user_visits`) 或验证码记录 (`email_verification_codes`)，以控制数据库大小。

### 2025年4月16日更新
1.增加了用户反馈界面
2.未登录用户在使用create recipe功能时会跳转至登录页面
3.解决了password输入处警告重复的问题
4.在验证密码是否相同时，把passwords match格式修改为和valid username一样的样式
5.修改了不正确的年份2023

## 注意事项
- **安全**：
    - **切勿**将敏感信息（如 API 密钥、数据库密码、邮箱密码、Secret Key）直接硬编码在代码中或提交到 Git 仓库。强烈推荐使用环境变量 (`.env`) 或专门的配置管理工具。
    - 默认管理员密码非常不安全，首次登录后务必修改。
    - 对用户输入进行严格的验证和清理，防止 SQL 注入、XSS 等攻击 (项目中使用了 Bleach 等库，但仍需注意)。
    - 生产环境部署时，确保使用 HTTPS。
- **错误处理**：应用中有基本的错误处理，但可以进一步完善，提供更友好的用户错误提示，并记录详细的错误日志供排查。
- **性能**：随着用户量和数据量的增长，可能需要对数据库查询、API 调用等进行性能优化，例如添加数据库索引、使用缓存等。
- **测试**：项目中缺少自动化测试（单元测试、集成测试）。添加测试可以显著提高代码质量和系统稳定性。
- **部署**：`deployment_guide.md` 提供了部署建议，生产环境通常使用 Gunicorn/uWSGI + Nginx/Apache 等组合进行部署。

## 贡献指南 (可选)
如果你希望其他人参与贡献，可以在这里添加贡献指南，例如代码风格、提交流程等。

## License (可选)
说明项目的许可证信息。
