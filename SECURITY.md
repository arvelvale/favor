# 凭据配置与历史清理

## 已修复

2026-11-11 移除源码和文档中的 API Key、SMTP 授权码、PayPal 沙盒 Secret、
管理员固定密码、Flask 固定会话密钥、测试账号固定密码、服务器登录口令和代理订阅 token。
取消跟踪 `.env`、虚拟环境和编译缓存，并增加 `.gitignore`。

## 当前版本（2026-11-16 起，健康管家重构）

旧版 Flask 模板应用（`aifood/`）已整体移除，管理后台、PayPal、邮箱验证码和 Gemini 图片生成不再存在，
相关凭据在新代码中没有任何读取入口。

配置入口为 `server/.env.example`，复制成同目录 `.env` 后填写：

- `SECRET_KEY` 必填且不少于 32 个字符，缺失或过短时拒绝启动，没有回退值。
- `LLM_API_KEY` 可选；缺失时应用照常运行，对话接口返回 503。模型上游的异常只记录类型名，
  不把异常正文、密钥写入响应或日志（有回归测试）。
- 会话 Cookie 为 HttpOnly + SameSite=Lax，HTTPS 部署时设 `SECURE_COOKIES=true`。
- 所有写接口只接受 `application/json`，不开放 CORS，用以防御跨站表单 CSRF。
- 密码使用 Werkzeug 哈希存储；每条记录、对话、习惯的读写都校验归属用户（有越权回归测试）。

尚未实现、上线前建议补上：登录与对话接口的频率限制、账号注销与数据导出。

## 必须在服务端完成的轮换

移除仓库内容不会撤销已有凭据。仓库维护者还需：

1. 在 DeepSeek、Google、QQ 邮箱和 PayPal 后台撤销旧凭据并创建新凭据。
2. 更换旧服务器登录口令及任何复用口令，并检查 SSH 登录记录；优先使用独立 SSH 密钥。
3. 在代理服务后台重置订阅 token，确认旧订阅链接失效。
4. 更新部署环境中的 SECRET_KEY，使旧会话失效（新版已无管理员账号）。
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
