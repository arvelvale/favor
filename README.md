# Favor · AI 健康管家

像和朋友聊天一样告诉 Favor 你吃了什么、睡得怎么样、运动了多久，它会自动记录、估算营养、对照你的目标给出建议，并帮你养成小习惯。

> 本项目由早期的 Flavor Fusion（AI 食谱生成器，Flask 模板 + jQuery）重构而来。旧版代码保留在 Git 历史中（提交 `734fb0c` 及之前）。

## 页面结构

| 路径 | 内容 |
|---|---|
| `/` | 落地页：自动播放的产品演示、功能介绍、使用步骤 |
| `/login` `/register` | 登录 / 注册 |
| `/app` | 工作台总览：热量环、今日建议、四项指标（带 7 天迷你趋势）、周图表、习惯、时间线、体重目标 |
| `/app/chat` | 完整对话页（含历史对话列表） |
| `/app/trends` `/app/records` `/app/profile` | 趋势、记录、健康档案 |

工作台右侧常驻 Favor 面板：在任意页面说一句话即可记录，记录完成后左侧面板实时刷新；“今日建议”里的条目可一键交给 Favor 展开。
视觉沿用旧版的暖橙 `#FF6B35` + 深海军蓝 `#2E4057` 色系；动效均为手写 CSS/JS，系统开启“减少动态效果”时自动关闭。

## 功能

- **对话式记录（Agent）**：一句“午饭吃了牛肉面加卤蛋，下午跑了 25 分钟”，Favor 会调用工具分别记录饮食和运动，营养按常见份量估算，并给出今日剩余热量与建议。
- **14 个工具**：记录饮食/饮水/运动/睡眠/体重/心情、删除记错的记录、查看当日汇总、分析 N 天趋势、读写健康档案、创建习惯与打卡。
- **今日面板**：热量环、三大营养素、饮水/运动/睡眠/体重卡片，一键快捷记录，每日习惯打卡。
- **趋势**：7 / 30 / 90 天的体重、热量、睡眠、饮水、运动、心情图表。
- **健康档案**：按 Mifflin-St Jeor 公式计算每日目标（见下方说明），记录体重时自动同步。
- **安全边界**：不做诊断与用药建议；危险信号提示就医；热量目标有下限，不鼓励极端节食。

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | React 18 + TypeScript + Vite，React Router，lucide 图标，手写 SVG 图表，容器查询布局，Poppins（自托管拉丁子集） |
| 后端 | Flask 3，SQLite（零配置），会话 Cookie 鉴权 |
| Agent | OpenAI 兼容接口的 function calling（默认 DeepSeek V4.1 Flash `deepseek-flash`），SSE 流式输出 |
| 菜品配图 | 阿里云百炼 `multimodal-generation`（默认 `z-image-turbo`，可换 `qwen-image-3.0`），后台生成、下载到本地、仅本人可见 |

```
server/            Flask API
  app.py           路由、鉴权、SSE 对话接口；生产环境同时托管 web/dist
  health.py        领域逻辑：目标计算、记录校验、汇总、趋势、习惯
  agent/tools.py   Agent 工具定义与执行器
  agent/runner.py  Agent 主循环（流式 → 工具 → 回填 → 最终回复）
  agent/prompts.py 系统提示词（动态注入时间、档案、今日概况）
web/               React 前端
tests/             后端回归测试（假模型客户端，不访问网络）
```

## 本地运行

需要 Python 3.11+ 与 Node.js 18+。

```bash
cd server
pip install -r requirements.txt
cp .env.example .env    # 填写 SECRET_KEY 和 LLM_API_KEY
python app.py           # http://127.0.0.1:5000
```

开发前端（热更新，/api 代理到 5000 端口）：

```bash
cd web
npm install
npm run dev             # http://localhost:5173
```

生产部署：`cd web && npm run build` 后只需启动 `server/app.py`（建议用 gunicorn/waitress 等 WSGI 服务器并置于 HTTPS 反向代理后，同时设置 `SECURE_COOKIES=true`）。

不配置 `LLM_API_KEY` 时应用照常运行，只有对话功能不可用；手动记录、趋势、档案均可使用。

配置 `DASHSCOPE_API_KEY` 后，Favor 给出菜谱或搭配建议时会为主菜生成一张成品示意图：每轮最多 1 张、每人每天默认 10 张（`IMAGE_DAILY_LIMIT`），
失败（欠费、审核未通过等）会在卡片里给出原因且不计入额度。百炼返回的图片链接 24 小时失效，所以服务端会立即下载保存到 `server/data/images/`。

## 目标计算

- 基础代谢 BMR（Mifflin-St Jeor）：男 `10×体重 + 6.25×身高 − 5×年龄 + 5`，女 `… − 161`
- 日常消耗 TDEE = BMR × 活动系数（1.2 / 1.375 / 1.55 / 1.725 / 1.9）
- 热量目标：减脂 15% 缺口 → `TDEE × 0.85`；增肌 10% 盈余 → `TDEE × 1.10`；其余 `× 1.0`
- 安全下限：不低于 BMR，且女性 ≥ 1200 kcal、男性 ≥ 1500 kcal
- 蛋白质：减脂 1.6 g/kg，增肌 1.8 g/kg，其余 1.2 g/kg；饮水 33 ml/kg（1500–3500 ml）

这些都是通用估算，不构成医疗建议。

## 测试

```bash
python -m unittest discover -s tests -v
```

覆盖配置安全、账号与数据隔离、记录校验、目标计算方向与下限、Agent 工具循环（并行工具调用、参数分片、历史配对、工具报错回传、模型异常不泄露细节）。

## 安全

见 [SECURITY.md](SECURITY.md)。
