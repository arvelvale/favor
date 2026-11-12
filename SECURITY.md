# 凭据配置与历史清理

## 已修复

2026-11-11 移除源码和文档中的 API Key、SMTP 授权码、PayPal 沙盒 Secret、
管理员固定密码、Flask 固定会话密钥、测试账号固定密码、服务器登录口令和代理订阅 token。
取消跟踪 `.env`、虚拟环境和编译缓存，并增加 `.gitignore`。

配置入口为 `aifood/aifood3/aifood/.env.example`。将它复制成同目录 `.env` 后，
填写新凭据。核心配置缺失会阻止启动；管理员、图片、邮件、支付配置缺失时拒绝对应请求。
管理员密码通过 `python scripts/configure_admin.py` 交互生成哈希，不接受明文回退密码。

Gemini 密钥通过请求头传递，依据 [Google 官方接口文档](https://ai.google.dev/api)。
关闭 SMTP 协议日志，并避免将上游异常正文、密钥和代理凭据写入响应或 API 日志。

## 必须在服务端完成的轮换

移除仓库内容不会撤销已有凭据。仓库维护者还需：

1. 在 DeepSeek、Google、QQ 邮箱和 PayPal 后台撤销旧凭据并创建新凭据。
2. 更换旧服务器登录口令及任何复用口令，并检查 SSH 登录记录；优先使用独立 SSH 密钥。
3. 在代理服务后台重置订阅 token，确认旧订阅链接失效。
4. 更新部署环境中的 SECRET_KEY，使旧会话失效；配置新的管理员密码哈希。
5. 更改实际使用过的数据库弱密码，处理旧测试账号，并检查服务用量和访问日志。

不要将新凭据写进 Git、Issue、PR、聊天或截图。`.env` 文件权限应限制为服务账号可读。

## 历史范围

2026-11-12 已完成远端 master 历史重写，并从远端重新克隆复核全部 10 个提交：
已知旧凭据匹配为 0，历史中不再跟踪 .env、虚拟环境和编译缓存。执行时只有 master 分支，没有标签或 PR。
此次重写改变了提交 SHA；旧克隆应重新克隆，不能合并或推送旧历史，以免重新引入敏感内容。
维护与同步记录作为后续普通提交保留。

**公开后的剩余安全事项：**仓库于 2026-11-12 经维护者授权改为公开；公开操作不表示旧凭据已经撤销。
重写后实测 GitHub 仍能按旧 SHA 返回旧 .env 的元数据，
因此分支历史清理不等于 GitHub 已清除所有旧对象或缓存。维护者仍需完成上述凭据轮换，
并核实平台缓存、fork、旧克隆和备份。若风险不能通过轮换解决，可按
[GitHub 官方流程](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
向 GitHub Support 申请评估旧对象与缓存清理；是否受理由 GitHub 判断。
无法从本次静态审计确认旧凭据是否仍有效或是否被外部获取。
旧版部署文档中的 YOUR_SUB_LINK 变量实际包含订阅凭据，不能因变量名像示例而忽略。

## 防止再次提交

CI 拉取完整历史，同时扫描当前版本与所有可达提交，并执行安全回归测试。
Gitleaks 固定为 8.30.1，CI 下载时校验 SHA-256。

开发机安装 Gitleaks 8.30.1 和 pre-commit 后，在仓库根目录运行：

```text
pre-commit install
gitleaks dir . --redact
python -m unittest discover -s tests -v
```

pre-commit 使用本机 gitleaks-system hook，只检查暂存内容；缺少 Gitleaks 时检查失败，不能跳过。
测试使用临时凭据并隔离外部 API、SMTP 和数据库调用，不能代替真实部署联调。
