# Favor · AI 厨房搭子

**冰箱里有什么，今晚就做什么。** 拍一张冰箱、勾几样或随口说一句，Favor 记住你有什么、哪些快过期了，
推荐现在就能做的菜；做完点「做好了」，用掉的食材自动从冰箱扣掉，这一餐也顺手记下。健康记录保留为次要入口。

> 本项目由早期的 Flavor Fusion（AI 食谱生成器，Flask 模板 + jQuery）重构而来，中间做过一版「AI 健康管家」；
> 2026-11 起按 `docs/冰箱优先重构方案.md` 改回「冰箱优先」。旧版代码保留在 Git 历史中。

## 页面结构

| 路径 | 内容 |
|---|---|
| `/` | 落地页：自动播放的「拍冰箱 → 认出食材 → 3 道推荐 → 做好了 → 记一餐」演示、功能介绍、使用步骤 |
| `/login` `/register` | 登录 / 注册 |
| `/welcome` | 首次使用的问卷（7–8 题，可整体或逐题跳过）；`?q=题目` 单独修改一题 |
| `/app` | 今天吃什么：快过期提醒、3 道推荐、库存摘要、上手进度清单 |
| `/app/fridge` | 冰箱：按冷藏 / 冷冻 / 常温分组，按到期排序；勾选、说一句话、拍一张三种录入 |
| `/app/recipe/:id` | 菜谱详情、全屏做菜模式（步骤计时器）、「做好了」扣库存并记一餐 |
| `/app/recipes` | 收藏和做过的菜 |
| `/app/chat` | 对话（agent 能管冰箱、推荐、记录） |
| `/app/me` | 我的：问卷带来的每一条调整，可单独修改 |
| `/app/health` `/app/trends` `/app/records` `/app/profile` | 健康：总览、趋势、记录、档案 |

新用户做完问卷后，由聚焦式引导带着走完一次「放食材 → 帮我想想 → 做好了」。
视觉沿用暖橙 `#FF6B35` + 深海军蓝 `#2E4057` 色系；动效均为手写 CSS/JS，系统开启「减少动态效果」时自动关闭。

## 功能

- **三种录入**：勾选常见食材、说一句话（「有 6 个鸡蛋、半颗洋葱」）、拍冰箱照片（DeepSeek 视觉模型）。识别结果都先给用户确认再入库；照片只用来识别，不保存。数量选填，保质期按食材和存放位置估算。
- **推荐**：菜谱由 AI 生成，但缺料、用到的临期食材、过敏原、厨具、饮食方式都由服务端对照库存和问卷重新校验；排序规则写死在 `kitchen.rank_key` 并有测试。
- **问卷**：每一题都改变一个看得见的行为（份量、难度、时间、厨具硬过滤、常备调料、忌口、排序、健康入口位置）。
- **做好了**：按数量或分类建议扣减，确认后扣库存并按吃了几份记一餐。
- **越用越准**：从做过、收藏、换一批时跳过、「不想吃」里学口味（规则见 `server/taste.py`），「我的」里能看到学到了什么并撤销；按估算过期的食材不进推荐，首页清点「还在吗」。
- **对话 Agent**：管冰箱、推荐菜、记录饮食和健康数据，营养问题查本地知识库（BM25）并标注出处。
- **安全边界**：不做诊断与用药建议；危险信号提示就医；热量目标有下限，不鼓励极端节食。

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | React 18 + TypeScript + Vite，React Router，lucide 图标，手写 SVG 图表，容器查询布局，Poppins（自托管拉丁子集） |
| 后端 | Flask 3，SQLite（零配置），会话 Cookie 鉴权 |
| Agent | OpenAI 兼容接口的 function calling（默认 DeepSeek V4.1 Flash `deepseek-flash`），SSE 流式输出 |
| 菜品配图 | 默认 MiniMax `image-01`（配了 `MINIMAX_API_KEY` 时），否则阿里云百炼 `multimodal-generation`（`z-image-turbo`）；后台生成、存到本地、仅本人可见 |
| 拍照识别 | DeepSeek 视觉模型（OpenAI 兼容接口，默认 `deepseek-flash`），默认复用 `LLM_API_KEY` |

```
server/            Flask API
  app.py           路由、鉴权、SSE 对话接口；生产环境同时托管 web/dist
  kitchen.py       冰箱库存、保质期估算、AI 菜谱校验与排序、做好了（扣库存 + 记一餐）
  prefs.py         问卷偏好、推荐提示词、过敏/饮食方式/忌口/厨具硬约束
  onboarding.py    新手引导进度（从真实数据推导）与情境提示
  photo.py         拍冰箱照片识别食材（只预览不入库，照片不落盘）
  taste.py         口味学习：做过/收藏/跳过/不想吃 → 下一次推荐的剔除、排序与提示词
  health.py        健康记录：目标计算、记录校验、汇总、趋势、习惯
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

不配置 `LLM_API_KEY` 时应用照常运行，只是对话和菜谱推荐不可用；冰箱管理、手动记录、趋势、档案均可使用。

配置 `MINIMAX_API_KEY`（优先）或 `DASHSCOPE_API_KEY` 后，Favor 给出菜谱或搭配建议时会为主菜生成一张成品示意图：每轮最多 1 张、每人每天默认 10 张（`IMAGE_DAILY_LIMIT`），
失败（欠费、审核未通过等）会在卡片里给出原因且不计入额度。百炼返回的图片链接 24 小时失效，所以服务端会立即下载保存到 `server/data/images/`。

拍照识别食材复用 DeepSeek 密钥 `LLM_API_KEY`（也可用 `VISION_API_KEY` / `VISION_BASE_URL` / `VISION_MODEL` 单独指定，默认 `deepseek-flash`）：每人每天默认 20 次（`VISION_DAILY_LIMIT`，失败也计入，防止反复重试刷费用）。
浏览器先把照片压到长边 1280px 再上传；这个接口单独放宽请求体上限，其他接口仍是 256KB。

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

覆盖配置安全、账号与数据隔离、记录校验、目标计算方向与下限、Agent 工具循环（并行工具调用、参数分片、历史配对、工具报错回传、模型异常不泄露细节）；以及冰箱闭环、问卷偏好（同一份模型输出、不同答案得到不同推荐）、新手引导进度、拍照识别（图片校验、只预览不入库、限额）。

## 安全

见 [SECURITY.md](SECURITY.md)。
