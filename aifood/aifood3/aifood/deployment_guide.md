# AI食谱应用 - 服务器部署指南

## 服务器信息
- **服务器地址**：SERVER_HOST
- **用户名**：root
- **认证**：使用运维单独提供的 SSH 密钥，本文不保存登录口令。
- **系统版本**：Ubuntu 22.04

## 一、准备工作

### 1. 连接到服务器
```bash
ssh root@SERVER_HOST
# 使用独立保存的 SSH 密钥连接；不要将口令写入文档。
```

### 2. 更新系统
```bash
sudo apt update
sudo apt upgrade -y
```

### 3. 安装必要工具
```bash
sudo apt install -y software-properties-common build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev curl git zip unzip nginx wget gzip
```

### 4. 安装Python 3.9.6（与本地环境保持一致）
```bash
# 添加deadsnakes PPA仓库
sudo add-apt-repository ppa:deadsnakes/ppa -y # 添加 -y 避免交互提示
sudo apt update

# 安装Python 3.9及相关工具
sudo apt install -y python3.9 python3.9-venv python3.9-dev

# 设置Python 3.9为默认Python版本 (可选，但建议保持系统默认以避免潜在问题)
# 如果需要明确指定python3.9，请在后续命令中使用 python3.9 而不是 python 或 python3
# sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 1
# sudo update-alternatives --install /usr/bin/python python /usr/bin/python3.9 1

# 验证Python 3.9安装
python3.9 --version

# 安装pip for Python 3.9
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
sudo python3.9 get-pip.py
rm get-pip.py # 清理下载的文件
```

## 二、部署项目

### 1. 创建项目目录
```bash
sudo mkdir -p /var/www/aifood3
cd /var/www
```

### 2. 上传项目文件
将本地项目打包上传到服务器：

**本地操作**:
```bash
# 在本地计算机上，确保在 aifood (2) 目录下执行
cd "D:\pythonproject\aifood (2)\aifood0.7"
# 使用系统自带压缩或第三方工具 (如 7-Zip) 创建 aifood.zip，包含 aifood3 文件夹

# 使用 scp 或 FileZilla 上传 aifood.zip
# 例如使用 scp (确保路径正确，可能需要引号):
scp "D:\pythonproject\aifood (2)\aifood0.7\aifood.zip" root@SERVER_HOST:/var/www/
```

**服务器操作**:
```bash
# 在服务器上执行
cd /var/www
sudo unzip aifood.zip # 解压
# 现在你应该有 /var/www/aifood3 目录了
# 可选：删除压缩包 sudo rm aifood.zip
```

### 3. 创建虚拟环境
```bash
cd /var/www/aifood3
sudo python3.9 -m venv venv # 使用 python3.9 创建
```

### 4. 安装依赖
```bash
# 激活虚拟环境
source /var/www/aifood3/venv/bin/activate

# 升级 pip
pip install --upgrade pip

# 安装应用依赖 (确保在 /var/www/aifood3/aifood 目录下有 requirements.txt 或手动安装)
cd /var/www/aifood3/aifood # 进入包含 app.py 的目录
pip install flask mysql-connector-python gunicorn
pip install werkzeug==2.0.3 # 指定版本
pip install protobuf==3.20.0 google-api-python-client google-auth-httplib2 google-auth-oauthlib
pip install google-generativeai Pillow

# 安装完成后可以退出虚拟环境 (可选)
# deactivate
```

## 三、配置MySQL

### 1. 安装MySQL 5.7
```bash
sudo apt update
# 下载 MySQL APT 配置仓库
wget https://dev.mysql.com/get/mysql-apt-config_0.8.29-1_all.deb
# 安装配置包，过程中会提示选择版本，请选择 MySQL 5.7
sudo dpkg -i mysql-apt-config_0.8.29-1_all.deb
# 更新包列表
sudo apt update
# 安装 MySQL Server 5.7
sudo apt install -y mysql-server=5.7* mysql-client=5.7* mysql-common=5.7*
# 清理下载的配置包
rm mysql-apt-config_0.8.29-1_all.deb
```

### 2. 配置MySQL 安全性
```bash
sudo mysql_secure_installation
# 根据提示设置root密码并回答安全问题 (建议都选 Y)
```

### 3. 创建数据库和用户
```bash
sudo mysql -u root -p
```

在MySQL提示符下执行 (将 `your_secure_password` 替换为您想设置的强密码):
```sql
CREATE DATABASE recipe_app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'aifood_user'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON recipe_app.* TO 'aifood_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 4. 导入数据库（如有本地备份）
```bash
# 如果您有本地数据库备份文件 backup.sql，先上传到服务器
# scp /path/to/local/backup.sql root@SERVER_HOST:/tmp/

# 在服务器上导入
sudo mysql -u aifood_user -p recipe_app < /tmp/backup.sql
```

## 四、修改项目配置

### 1. 配置环境变量

```bash
cd /var/www/aifood3/aifood
cp .env.example .env
chmod 600 .env
nano .env
```

填写新的 DEEPSEEK_API_KEY、SECRET_KEY、DB_USER、DB_PASSWORD；不要在 auth.py 或
config.py 中写密码。数据库账号使用前面创建的专用账号。SECRET_KEY 至少 32 位，
可用 `python -c 'import secrets; print(secrets.token_urlsafe(48))'` 本地生成。
管理员密码用 `python scripts/configure_admin.py` 生成哈希并保存到 .env。
各服务的其他环境变量见 `.env.example`；不要复用旧仓库中的凭据。

### 2. 代理设置

需要代理时在 .env 中设置 HTTP_PROXY、HTTPS_PROXY；不需要时保持为空。
不要把带口令的代理地址或订阅链接写入代码和文档。

## 五、配置Clash Meta代理

### 1. 下载Clash Meta核心和GeoIP库
```bash
sudo mkdir -p /opt/clash-meta
cd /opt/clash-meta

# 下载 Clash Meta 核心 (访问 https://github.com/MetaCubeX/Clash.Meta/releases 确认最新版本)
# 假设最新版本是 v1.15.1
sudo wget https://github.com/MetaCubeX/Clash.Meta/releases/download/v1.15.1/clash.meta-linux-amd64-v1.15.1.gz
sudo gzip -d clash.meta-linux-amd64-v1.15.1.gz
sudo mv clash.meta-linux-amd64-v1.15.1 clash-meta
sudo chmod +x clash-meta

# 下载 GeoIP 数据库
sudo wget -O Country.mmdb https://github.com/Dreamacro/maxmind-geoip/releases/latest/download/Country.mmdb
```

### 2. 下载Clash配置文件
```bash
# 使用您的订阅链接
YOUR_SUB_LINK="${CLASH_SUBSCRIPTION_URL:?请在部署环境中设置订阅链接}"
sudo wget -O config.yaml "$YOUR_SUB_LINK"

# 检查文件
ls -l /opt/clash-meta
```

### 3. 创建Clash Meta的Systemd服务
```bash
sudo nano /etc/systemd/system/clash-meta.service
```

粘贴以下内容：
```ini
[Unit]
Description=Clash Meta Daemon Service
After=network.target

[Service]
Type=simple
User=root # 考虑使用非root用户运行以提高安全性
WorkingDirectory=/opt/clash-meta
ExecStart=/opt/clash-meta/clash-meta -d /opt/clash-meta
Restart=on-failure

[Install]
WantedBy=multi-user.target
```
保存并关闭。

### 4. 启动并启用Clash Meta服务
```bash
sudo systemctl daemon-reload
sudo systemctl start clash-meta.service
sudo systemctl enable clash-meta.service
root@10-7-88-154:/opt/clash-meta# sudo journalctl -u clash-meta.service --no-pager -n 50
Apr 11 17:07:23 10-7-88-154 systemd[1]: Started Clash Meta Daemon Service.
Apr 11 17:07:23 10-7-88-154 systemd[18293]: clash-meta.service: Failed to determine user credentials: No such process
Apr 11 17:07:23 10-7-88-154 systemd[18293]: clash-meta.service: Failed at step USER spawning /opt/clash-meta/clash-meta: No such process
Apr 11 17:07:23 10-7-88-154 systemd[1]: clash-meta.service: Main process exited, code=exited, status=217/USER
Apr 11 17:07:23 10-7-88-154 systemd[1]: clash-meta.service: Failed with result 'exit-code'.
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Scheduled restart job, restart counter is at 1.
Apr 11 17:07:24 10-7-88-154 systemd[1]: Stopped Clash Meta Daemon Service.
Apr 11 17:07:24 10-7-88-154 systemd[1]: Started Clash Meta Daemon Service.
Apr 11 17:07:24 10-7-88-154 systemd[18294]: clash-meta.service: Failed to determine user credentials: No such process
Apr 11 17:07:24 10-7-88-154 systemd[18294]: clash-meta.service: Failed at step USER spawning /opt/clash-meta/clash-meta: No such process
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Main process exited, code=exited, status=217/USER
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Failed with result 'exit-code'.
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Scheduled restart job, restart counter is at 2.
Apr 11 17:07:24 10-7-88-154 systemd[1]: Stopped Clash Meta Daemon Service.
Apr 11 17:07:24 10-7-88-154 systemd[1]: Started Clash Meta Daemon Service.
Apr 11 17:07:24 10-7-88-154 systemd[18295]: clash-meta.service: Failed to determine user credentials: No such process
Apr 11 17:07:24 10-7-88-154 systemd[18295]: clash-meta.service: Failed at step USER spawning /opt/clash-meta/clash-meta: No such process
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Main process exited, code=exited, status=217/USER
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Failed with result 'exit-code'.
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Scheduled restart job, restart counter is at 3.
Apr 11 17:07:24 10-7-88-154 systemd[1]: Stopped Clash Meta Daemon Service.
Apr 11 17:07:24 10-7-88-154 systemd[1]: Started Clash Meta Daemon Service.
Apr 11 17:07:24 10-7-88-154 systemd[18296]: clash-meta.service: Failed to determine user credentials: No such process
Apr 11 17:07:24 10-7-88-154 systemd[18296]: clash-meta.service: Failed at step USER spawning /opt/clash-meta/clash-meta: No such process
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Main process exited, code=exited, status=217/USER
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Failed with result 'exit-code'.
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Scheduled restart job, restart counter is at 4.
Apr 11 17:07:24 10-7-88-154 systemd[1]: Stopped Clash Meta Daemon Service.
Apr 11 17:07:24 10-7-88-154 systemd[1]: Started Clash Meta Daemon Service.
Apr 11 17:07:24 10-7-88-154 systemd[18297]: clash-meta.service: Failed to determine user credentials: No such process
Apr 11 17:07:24 10-7-88-154 systemd[18297]: clash-meta.service: Failed at step USER spawning /opt/clash-meta/clash-meta: No such process
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Main process exited, code=exited, status=217/USER
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Failed with result 'exit-code'.
Apr 11 17:07:25 10-7-88-154 systemd[1]: clash-meta.service: Scheduled restart job, restart counter is at 5.
Apr 11 17:07:25 10-7-88-154 systemd[1]: Stopped Clash Meta Daemon Service.
Apr 11 17:07:25 10-7-88-154 systemd[1]: clash-meta.service: Start request repeated too quickly.
Apr 11 17:07:25 10-7-88-154 systemd[1]: clash-meta.service: Failed with result 'exit-code'.
Apr 11 17:07:25 10-7-88-154 systemd[1]: Failed to start Clash Meta Daemon Service.
root@10-7-88-154:/opt/clash-meta#     sudo /opt/clash-meta/clash-meta -d /opt/clash-meta
FATA[2025-04-11T17:15:08.809330299+08:00] Parse config error: yaml: unmarshal errors:
  line 1: cannot unmarshal !!str `dHJvamF...` into config.RawConfig 
root@10-7-88-154:/opt/clash-meta#     ls -l /opt/clash-meta/clash-meta
    ls -l /opt/clash-meta/config.yaml
    ls -l /opt/clash-meta/Country.mmdb
-rwxr-xr-x 1 root root 28987392 Aug 13  2023 /opt/clash-meta/clash-meta
-rw-r--r-- 1 root root 21116 Apr 11 17:00 /opt/clash-meta/config.yaml
-rw-r--r-- 1 root root 8828854 Mar 12 08:14 /opt/clash-meta/Country.mmdb
root@10-7-88-154:/opt/clash-meta# 
root@10-7-88-154:/opt/clash-meta# sudo journalctl -u clash-meta.service --no-pager -n 50
Apr 11 17:07:23 10-7-88-154 systemd[1]: Started Clash Meta Daemon Service.
Apr 11 17:07:23 10-7-88-154 systemd[18293]: clash-meta.service: Failed to determine user credentials: No such process
Apr 11 17:07:23 10-7-88-154 systemd[18293]: clash-meta.service: Failed at step USER spawning /opt/clash-meta/clash-meta: No such process
Apr 11 17:07:23 10-7-88-154 systemd[1]: clash-meta.service: Main process exited, code=exited, status=217/USER
Apr 11 17:07:23 10-7-88-154 systemd[1]: clash-meta.service: Failed with result 'exit-code'.
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Scheduled restart job, restart counter is at 1.
Apr 11 17:07:24 10-7-88-154 systemd[1]: Stopped Clash Meta Daemon Service.
Apr 11 17:07:24 10-7-88-154 systemd[1]: Started Clash Meta Daemon Service.
Apr 11 17:07:24 10-7-88-154 systemd[18294]: clash-meta.service: Failed to determine user credentials: No such process
Apr 11 17:07:24 10-7-88-154 systemd[18294]: clash-meta.service: Failed at step USER spawning /opt/clash-meta/clash-meta: No such process
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Main process exited, code=exited, status=217/USER
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Failed with result 'exit-code'.
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Scheduled restart job, restart counter is at 2.
Apr 11 17:07:24 10-7-88-154 systemd[1]: Stopped Clash Meta Daemon Service.
Apr 11 17:07:24 10-7-88-154 systemd[1]: Started Clash Meta Daemon Service.
Apr 11 17:07:24 10-7-88-154 systemd[18295]: clash-meta.service: Failed to determine user credentials: No such process
Apr 11 17:07:24 10-7-88-154 systemd[18295]: clash-meta.service: Failed at step USER spawning /opt/clash-meta/clash-meta: No such process
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Main process exited, code=exited, status=217/USER
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Failed with result 'exit-code'.
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Scheduled restart job, restart counter is at 3.
Apr 11 17:07:24 10-7-88-154 systemd[1]: Stopped Clash Meta Daemon Service.
Apr 11 17:07:24 10-7-88-154 systemd[1]: Started Clash Meta Daemon Service.
Apr 11 17:07:24 10-7-88-154 systemd[18296]: clash-meta.service: Failed to determine user credentials: No such process
Apr 11 17:07:24 10-7-88-154 systemd[18296]: clash-meta.service: Failed at step USER spawning /opt/clash-meta/clash-meta: No such process
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Main process exited, code=exited, status=217/USER
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Failed with result 'exit-code'.
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Scheduled restart job, restart counter is at 4.
Apr 11 17:07:24 10-7-88-154 systemd[1]: Stopped Clash Meta Daemon Service.
Apr 11 17:07:24 10-7-88-154 systemd[1]: Started Clash Meta Daemon Service.
Apr 11 17:07:24 10-7-88-154 systemd[18297]: clash-meta.service: Failed to determine user credentials: No such process
Apr 11 17:07:24 10-7-88-154 systemd[18297]: clash-meta.service: Failed at step USER spawning /opt/clash-meta/clash-meta: No such process
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Main process exited, code=exited, status=217/USER
Apr 11 17:07:24 10-7-88-154 systemd[1]: clash-meta.service: Failed with result 'exit-code'.
Apr 11 17:07:25 10-7-88-154 systemd[1]: clash-meta.service: Scheduled restart job, restart counter is at 5.
Apr 11 17:07:25 10-7-88-154 systemd[1]: Stopped Clash Meta Daemon Service.
Apr 11 17:07:25 10-7-88-154 systemd[1]: clash-meta.service: Start request repeated too quickly.
Apr 11 17:07:25 10-7-88-154 systemd[1]: clash-meta.service: Failed with result 'exit-code'.
Apr 11 17:07:25 10-7-88-154 systemd[1]: Failed to start Clash Meta Daemon Service.
root@10-7-88-154:/opt/clash-meta#     sudo /opt/clash-meta/clash-meta -d /opt/clash-meta
FATA[2025-04-11T17:15:08.809330299+08:00] Parse config error: yaml: unmarshal errors:
  line 1: cannot unmarshal !!str `dHJvamF...` into config.RawConfig 
root@10-7-88-154:/opt/clash-meta#     ls -l /opt/clash-meta/clash-meta
    ls -l /opt/clash-meta/config.yaml
    ls -l /opt/clash-meta/Country.mmdb
-rwxr-xr-x 1 root root 28987392 Aug 13  2023 /opt/clash-meta/clash-meta
-rw-r--r-- 1 root root 21116 Apr 11 17:00 /opt/clash-meta/config.yaml
-rw-r--r-- 1 root root 8828854 Mar 12 08:14 /opt/clash-meta/Country.mmdb
root@10-7-88-154:/opt/clash-meta# 
 # 确认状态为 active (running)
```

### 5. 验证代理出口IP
```bash
curl --proxy http://127.0.0.1:7890 ifconfig.me
# 预期输出一个非香港的IP地址 (取决于您的代理默认节点)
```

## 六、配置Gunicorn服务 (使用Clash Meta代理)

### 1. 创建/修改Gunicorn服务文件
```bash
sudo nano /etc/systemd/system/aifood.service
```

确保内容如下 (请仔细核对所有路径是否为 `/var/www/aifood3/...`):
```ini
[Unit]
Description=Gunicorn instance to serve aifood
After=network.target clash-meta.service # 依赖Clash Meta服务

[Service]
User=root # 考虑使用非root用户运行
Group=www-data
WorkingDirectory=/var/www/aifood3/aifood # <--- 确认路径
# 设置代理环境变量
Environment="HTTP_PROXY=http://127.0.0.1:7890"
Environment="HTTPS_PROXY=http://127.0.0.1:7890"
# 设置Python虚拟环境路径
Environment="PATH=/var/www/aifood3/venv/bin" # <--- 确认路径
# 启动Gunicorn，绑定到socket文件
ExecStart=/var/www/aifood3/venv/bin/gunicorn --workers 3 --bind unix:/var/www/aifood3/aifood.sock -m 007 app:app # <--- 确认路径和socket文件名
Restart=on-failure

[Install]
WantedBy=multi-user.target
```
保存并关闭。

### 2. 启动并启用Gunicorn服务
```bash
sudo systemctl daemon-reload
sudo systemctl start aifood.service
sudo systemctl enable aifood.service
sudo systemctl status aifood.service # 确认状态为 active (running)
```
*如果启动失败，请使用 `sudo journalctl -u aifood.service -n 50 --no-pager` 查看详细错误日志。*

## 七、配置Nginx反向代理

### 1. 创建Nginx配置文件
```bash
sudo nano /etc/nginx/sites-available/aifood
```

添加以下内容 (请仔细核对所有路径是否为 `/var/www/aifood3/...`):
```nginx
server {
    listen 80;
    server_name SERVER_HOST your_domain.com www.your_domain.com; # 替换为您的服务器IP或域名

    # 增加client_max_body_size以允许更大的上传（如果需要）
    client_max_body_size 20M;

    location /static {
        alias /var/www/aifood3/aifood/static; # <--- 确认静态文件路径
        expires 7d; # 可选：设置静态文件缓存时间
    }

    location / {
        # 将请求转发给Gunicorn的socket
        proxy_pass http://unix:/var/www/aifood3/aifood.sock; # <--- 确认socket文件路径
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # 增加超时时间（如果应用响应较慢）
        proxy_connect_timeout 60s;
        proxy_read_timeout 300s;
    }

    # 可选：优化gzip压缩
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css application/json application/javascript application/x-javascript text/xml application/xml application/xml+rss text/javascript;

    # 可选：错误页面
    error_page 500 502 503 504 /50x.html;
    location = /50x.html {
        root /usr/share/nginx/html; # 或您的自定义错误页面路径
    }
}
```
保存并关闭。

### 2. 启用配置并测试
```bash
# 创建符号链接以启用站点
sudo ln -s /etc/nginx/sites-available/aifood /etc/nginx/sites-enabled/

# 测试Nginx配置语法
sudo nginx -t
# 如果显示 "syntax is ok" 和 "test is successful"，则继续

# 重启Nginx以应用更改
sudo systemctl restart nginx
```
*如果 `nginx -t` 报错，请根据错误提示检查配置文件 `/etc/nginx/sites-available/aifood`。如果链接已存在，删除旧的再创建: `sudo rm /etc/nginx/sites-enabled/aifood`*

### 3. 配置防火墙
```bash
# 允许Nginx通过防火墙 (HTTP和HTTPS)
sudo ufw allow 'Nginx Full'

# 如果您之前为测试打开了5000端口，现在可以关闭它 (因为Nginx在80端口处理请求)
# sudo ufw delete allow 5000/tcp

# 确保防火墙已启用
sudo ufw enable
sudo ufw status # 确认 Nginx Full (或 80, 443) 是 allow
```

## 八、解决哈希算法兼容性问题 (如果遇到)

如果登录时遇到与 `scrypt` 相关的 "unsupported hash type" 错误，编辑 `auth.py`：

```bash
sudo nano /var/www/aifood3/aifood/auth.py
```

找到验证密码的函数 (通常是 `check_password` 或类似名称，或者在 `login` 函数内部)，修改逻辑以兼容旧哈希或强制更新哈希：

```python
from werkzeug.security import check_password_hash, generate_password_hash

def verify_user_password(stored_hash, provided_password):
    try:
        return check_password_hash(stored_hash, provided_password)
    except ValueError as e:
        if "unsupported hash type" in str(e) and stored_hash.startswith('scrypt:'):
            # 这里可以添加逻辑：
            # 1. 尝试用旧方法验证 (如果知道旧方法)
            # 2. 或者，更推荐的做法是：在用户成功登录后（例如通过邮箱验证码重置密码）
            #    强制用户更新密码，生成新格式的哈希并存入数据库。
            # 暂时返回 False，提示用户密码错误或需要重置
            print(f"Unsupported hash type detected for user. Hash needs update: {stored_hash[:20]}...")
            return False
        else:
            # 其他类型的 ValueError，重新抛出
            raise
```
*注意：简单地返回 True 是不安全的。最佳实践是在用户下次成功验证身份后更新哈希。*

修改后需要重启 Gunicorn 服务：`sudo systemctl restart aifood.service`

## 九、测试和维护

### 1. 测试应用
在浏览器中访问 `http://SERVER_HOST` (或您的域名)。尝试注册、登录、调用Gemini API等功能。

### 2. 查看日志
```bash
# Gunicorn 应用日志
sudo journalctl -u aifood.service -f --no-pager

# Clash Meta 日志
sudo journalctl -u clash-meta.service -f --no-pager

# Nginx 访问日志
sudo tail -f /var/log/nginx/access.log

# Nginx 错误日志
sudo tail -f /var/log/nginx/error.log

# MySQL 日志 (如果需要)
# sudo tail -f /var/log/mysql/error.log
```

### 3. 重启服务
```bash
sudo systemctl restart aifood.service
sudo systemctl restart clash-meta.service
sudo systemctl restart nginx
```

### 4. 更新应用
```bash
cd /var/www/aifood3
# git pull # 如果使用git

# 或者重新上传文件并解压覆盖

# 确保激活虚拟环境更新依赖 (如果 requirements.txt 变化)
# source venv/bin/activate
# pip install -r aifood/requirements.txt

# 重启应用服务
sudo systemctl restart aifood.service
```

### 5. 更新Clash订阅
```bash
cd /opt/clash-meta
YOUR_SUB_LINK="${CLASH_SUBSCRIPTION_URL:?请在部署环境中设置订阅链接}"
sudo wget -O config.yaml "$YOUR_SUB_LINK"
sudo systemctl restart clash-meta.service
```
*可以将其设置为定时任务 (cron job) 自动更新。*

## 十、备份策略 (路径已更新)

### 1. 数据库备份
```bash
sudo nano /usr/local/bin/backup_db.sh # 脚本放在 /usr/local/bin 更好
```
先在服务器单独创建权限为 600 的 `/etc/aifood-mysql.cnf` 保存数据库连接信息；该文件不纳入 Git。脚本中不写密码：
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/mysql"
sudo mkdir -p $BACKUP_DIR
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
sudo mysqldump --defaults-extra-file=/etc/aifood-mysql.cnf recipe_app > $BACKUP_DIR/recipe_app_$TIMESTAMP.sql
# 设置权限
sudo chown root:root $BACKUP_DIR/recipe_app_$TIMESTAMP.sql
sudo chmod 600 $BACKUP_DIR/recipe_app_$TIMESTAMP.sql
# 保留最近30天的备份
find $BACKUP_DIR -name "recipe_app_*.sql" -type f -mtime +30 -delete
```
设置执行权限并添加定时任务:
```bash
sudo chmod +x /usr/local/bin/backup_db.sh
sudo crontab -e
# 添加行: 0 2 * * * /usr/local/bin/backup_db.sh
```

### 2. 文件备份
```bash
sudo nano /usr/local/bin/backup_files.sh
```
添加内容:
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/aifood"
sudo mkdir -p $BACKUP_DIR
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
sudo tar -czf $BACKUP_DIR/aifood_$TIMESTAMP.tar.gz /var/www/aifood3
# 保留最近7天的备份
find $BACKUP_DIR -name "aifood_*.tar.gz" -type f -mtime +7 -delete
```
设置执行权限并添加定时任务:
```bash
sudo chmod +x /usr/local/bin/backup_files.sh
sudo crontab -e
# 添加行: 0 3 * * 0 /usr/local/bin/backup_files.sh
```

## 十一、故障排除

### 1. 应用无法启动 (aifood.service)
- 检查日志：`sudo journalctl -u aifood.service -n 50 --no-pager`
- 确认虚拟环境路径 (`/var/www/aifood3/venv`) 和 Gunicorn 路径正确。
- 确认工作目录 (`/var/www/aifood3/aifood`) 正确。
- 确认 `app:app` 对于 Gunicorn 是可导入的 (目录下有 `app.py` 且包含 `app = Flask(__name__)`)。
- 手动激活虚拟环境 (`source /var/www/aifood3/venv/bin/activate`)，进入工作目录 (`cd /var/www/aifood3/aifood`)，尝试手动运行 Gunicorn 看是否报错：`gunicorn --workers 1 --bind 0.0.0.0:8001 app:app`

### 2. Clash Meta 无法启动 (clash-meta.service)
- 检查日志：`sudo journalctl -u clash-meta.service -n 50 --no-pager`
- 确认 `config.yaml` 和 `Country.mmdb` 文件存在于 `/opt/clash-meta`。
- 确认 `clash-meta` 程序有执行权限 (`ls -l /opt/clash-meta/clash-meta`)。
- 尝试手动运行：`cd /opt/clash-meta && sudo ./clash-meta -d .` 看是否有报错。

### 3. 数据库连接问题
- 确认MySQL服务运行：`sudo systemctl status mysql`
- 检查 `auth.py` 中的密码是否与创建用户时设置的一致。
- 尝试从服务器命令行连接：`mysql -u aifood_user -p recipe_app`

### 4. Gemini API 问题 (区域限制已解决后)
- 确认 `aifood.service` 中已正确设置 `HTTP_PROXY` 和 `HTTPS_PROXY` 环境变量。
- 确认 `clash-meta.service` 正在运行。
- 检查 `clash-meta` 日志看是否有关于 API 请求被阻止或失败的信息。
- 验证 API 密钥本身是否有效，以及在 Google Cloud Console 中是否启用了正确的 API。

### 5. Nginx 配置问题 (502 Bad Gateway 等)
- 检查 Nginx 错误日志：`sudo tail -f /var/log/nginx/error.log`
- 确认 Gunicorn 服务 (`aifood.service`) 正在运行。
- 确认 Nginx 配置中的 `proxy_pass http://unix:/var/www/aifood3/aifood.sock;` 路径与 `aifood.service` 中 `ExecStart` 的 `--bind unix:/var/www/aifood3/aifood.sock` 路径完全一致。
- 检查 socket 文件是否存在且 Nginx 进程(通常用户是 www-data)有权限访问：`ls -la /var/www/aifood3/aifood.sock`。权限可能需要调整，例如 `sudo chown root:www-data /var/www/aifood3/aifood.sock` 和 `sudo chmod 660 /var/www/aifood3/aifood.sock`。

### 6. Python版本问题
- 如果遇到依赖包错误，确认是在 Python 3.9 的虚拟环境中安装的。
- 检查 Gunicorn 服务文件中的 `Environment="PATH=..."` 是否指向正确的 Python 3.9 虚拟环境。

## 附录：重要文件路径 (已更新)

- 应用目录：`/var/www/aifood3/aifood`
- 虚拟环境：`/var/www/aifood3/venv`
- Clash Meta 目录：`/opt/clash-meta`
- 配置文件：
  - 数据库配置：`/var/www/aifood3/aifood/auth.py` (或相关文件)
  - Clash 配置：`/opt/clash-meta/config.yaml`
- 日志文件：
  - Gunicorn 应用日志：`sudo journalctl -u aifood.service`
  - Clash Meta 日志：`sudo journalctl -u clash-meta.service`
  - Nginx 访问日志：`/var/log/nginx/access.log`
  - Nginx 错误日志：`/var/log/nginx/error.log`
- 服务配置：
  - Gunicorn 服务：`/etc/systemd/system/aifood.service`
  - Clash Meta 服务：`/etc/systemd/system/clash-meta.service`
  - Nginx 配置：`/etc/nginx/sites-available/aifood` (启用链接在 `/etc/nginx/sites-enabled/aifood`)
- Gunicorn Socket 文件：`/var/www/aifood3/aifood.sock`
