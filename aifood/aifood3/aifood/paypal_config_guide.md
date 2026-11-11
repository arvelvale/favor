# PayPal 配置

凭据只通过应用目录的本地 `.env` 或部署环境变量提供，不写入源码、模板或文档：

```dotenv
PAYPAL_MODE=sandbox
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
```

沙盒使用 sandbox；上线时在 PayPal 后台创建正式应用，设置 PAYPAL_MODE=live，
并配置相匹配的新 Client ID 和 Client Secret。Client Secret 仅供服务端使用。
未配置完整凭据时，支付接口返回 503；网页只在已配置时加载公开 Client ID。
旧仓库中的沙盒 Secret 已暴露，应在服务后台撤销，不能继续复用。
