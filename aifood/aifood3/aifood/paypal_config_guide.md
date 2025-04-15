# PayPal配置指南

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
