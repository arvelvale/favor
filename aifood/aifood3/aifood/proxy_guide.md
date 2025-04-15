# 代理设置指南

## 问题背景

在使用本应用程序时，您可能会遇到网络连接问题，特别是在以下情况下：

1. 您的服务器需要通过代理才能访问外部API（如DeepSeek API或Gemini API）
2. 您的网络环境有防火墙限制，阻止了对某些API的访问
3. 您所在的地区可能无法直接访问某些API服务

这些问题通常会导致应用程序在生成菜谱或图片时出现"Connection error"错误。

## 解决方案

### 开发环境

在开发环境中，您可以使用以下方法设置代理：

#### 方法一：使用代理设置助手

我们提供了一个简单的代理设置助手，可以帮助您配置代理并启动应用程序：

1. 打开命令行终端
2. 导航到应用程序目录
3. 运行以下命令：

```
python run_with_proxy.py
```

4. 按照提示输入代理信息（如果需要）
5. 应用程序将自动启动并使用您配置的代理设置

#### 方法二：手动设置环境变量

如果您更喜欢手动设置，可以直接设置环境变量：

##### Windows系统：

在命令行中运行：

```
set HTTP_PROXY=http://your-proxy-host:port
set HTTPS_PROXY=http://your-proxy-host:port
python app.py
```

##### Linux/Mac系统：

在终端中运行：

```
export HTTP_PROXY=http://your-proxy-host:port
export HTTPS_PROXY=http://your-proxy-host:port
python app.py
```

### 生产环境

在生产环境中，您应该使用更可靠的方法来设置代理：

#### 方法一：使用配置文件

本应用程序使用`config.py`文件来管理配置，包括代理设置。您可以通过以下方式设置代理：

1. 在服务器上创建或编辑`.env`文件
2. 添加以下内容：

```
HTTP_PROXY=http://your-proxy-host:port
HTTPS_PROXY=http://your-proxy-host:port
```

3. 重启应用程序以应用新的设置

#### 方法二：使用系统环境变量

如果您使用systemd、Docker或其他容器技术部署应用程序，可以在服务配置中设置环境变量：

##### systemd服务示例：

```
[Unit]
Description=AI Food Recipe Generator
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/app
ExecStart=/usr/bin/python3 app.py
Restart=always
Environment=HTTP_PROXY=http://your-proxy-host:port
Environment=HTTPS_PROXY=http://your-proxy-host:port

[Install]
WantedBy=multi-user.target
```

##### Docker示例：

```
docker run -d \
  -e HTTP_PROXY=http://your-proxy-host:port \
  -e HTTPS_PROXY=http://your-proxy-host:port \
  -p 5000:5000 \
  your-docker-image
```

## 常见代理设置

以下是一些常见的代理设置示例：

### 本地代理（如使用Clash、V2Ray等工具）：

```
http://127.0.0.1:7890
```

### 公司代理：

```
http://proxy.company.com:8080
```

### 带认证的代理：

```
http://username:password@proxy.company.com:8080
```

## 重要说明

### 用户访问与服务器代理的区别

需要明确区分两种不同的网络连接：

1. **用户到您的服务器的连接**：
   - 如果用户通过代理访问您的网站，这是在用户端处理的
   - 您的服务器不需要做任何特殊处理
   - 普通用户不需要也不应该设置任何代理配置

2. **您的服务器到外部API的连接**：
   - 如果您的服务器需要通过代理访问DeepSeek或Gemini API
   - 这需要在服务器端配置代理
   - 这就是本指南所涵盖的内容

### 安全注意事项

- 在生产环境中，应避免在代码中硬编码代理信息
- 优先使用环境变量或配置文件来存储敏感信息
- 确保代理服务器是安全的，并且只允许受信任的连接
- 定期更新代理设置和相关密码

## 故障排除

如果您仍然遇到连接问题，请尝试以下步骤：

1. 确认您的代理服务器是否正常工作
2. 尝试在服务器上使用curl或wget测试API连接
3. 检查应用程序日志中的详细错误信息
4. 确保您的代理服务器允许HTTPS连接
5. 如果使用公司代理，请确认是否需要特殊的认证