# ClawTrap Benchmark Creation Page

本项目包含两个部分：

- 标注 Web 页面：登录后查看自己设计过的攻击场景，新增、保存草稿、提交场景。
- LLM 批量生成脚本：根据固定 prompt 批量生成 MITM benchmark seed cases，并以 JSON 落盘。

## 数据格式

所有 case 存储在 `data/cases.json`，每条 case 使用以下核心字段：

- `task`
- `target`
- `task_type`
- `attack_method`
- `success_states`
- `failure_states`
- `logic`
- `attack_type`
- `interactive_form`
- `metadata`

提交时会校验核心字段非空、枚举值合法、成功/失败状态至少各 2 条。

## 安装

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

`.env` 需要包含：

```bash
OPENAI_API_KEY="..."
OPENAI_BASE_URL="..."
```

可选：

```bash
OPENAI_MODEL="gpt-4.1"
```

## 批量生成

第一批 300 条，按 5 类攻击类型、10 类任务类型、每组合 6 条生成，并要求每条 case 的 `interactive_form` 只包含 1 个选项：

```bash
python scripts/generate_cases.py --limit 300 --per-combo 6 --batch-size 3
```

生成 30 条 demo 到单独文件，不追加到主数据：

```bash
python scripts/generate_cases.py --model gpt-4.1 --limit 30 --per-combo 1 --batch-size 1 --combo-order task-first --output data/demo_cases_gpt41.json
```

只验证调用和 parse，不落盘：

```bash
python scripts/generate_cases.py --limit 3 --per-combo 3 --batch-size 3 --no-write
```

## 启动标注页面

```bash
python app.py
```

打开 `http://127.0.0.1:8000`，输入任意标注员用户名即可登录。页面会展示该用户自己的 case 和 LLM seed case。

## 管理员审阅页面

管理员页面用于查看和筛选 `data/` 目录下的 JSON 数据集：

```text
http://127.0.0.1:8000/admin
```

生产部署前在 `.env` 中设置管理员账号和密码：

```bash
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="换成强密码"
```

未设置 `ADMIN_PASSWORD` 时，本地开发默认账号密码为 `admin/admin`。管理员页面支持选择数据集、按状态/攻击类型/任务类型/植入形式筛选、全文搜索、查看详情和导出当前筛选结果。

部署到域名时可通过环境变量调整监听地址：

```bash
APP_HOST="0.0.0.0"
APP_PORT="8000"
```

## Vercel 部署

这个项目现在包含两套入口：

- `app.py`：本地标准库开发入口。
- `api/index.py`：Vercel 使用的 Flask Serverless 入口。

Vercel 部署会通过 `vercel.json` 把所有请求转发到 `api/index.py`。

### 1. 推到 GitHub

```bash
git init
git add .
git commit -m "Initial ClawTrap benchmark app"
git branch -M main
git remote add origin <你的 GitHub repo URL>
git push -u origin main
```

### 2. 在 Vercel 导入 Repo

在 Vercel 新建 Project，选择刚才的 GitHub repo。默认构建设置即可，Vercel 会读取：

- `requirements.txt`
- `vercel.json`
- `api/index.py`

### 3. 配置环境变量

在 Vercel Project Settings -> Environment Variables 添加：

```bash
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="换成强密码"
SECRET_KEY="一串很长的随机字符串"
OPENAI_API_KEY="..."
OPENAI_BASE_URL="..."
OPENAI_MODEL="gpt-4.1"
```

如果要在线保存标注员提交，必须添加 PostgreSQL 连接串：

```bash
DATABASE_URL="postgresql://..."
```

也可以使用 Vercel Marketplace 里的 Neon/Vercel Postgres。没有 `DATABASE_URL` 时，Vercel 上仍可读取 repo 内的 `data/*.json`，但保存接口会返回明确错误，避免误以为数据已持久保存。

### 4. 初始化数据库数据

本地 `.env` 中临时放入线上数据库的 `DATABASE_URL` 后执行：

```bash
. .venv/bin/activate
python scripts/seed_database.py data/cases.json --dataset cases
python scripts/seed_database.py data/demo_cases_gpt41.json --dataset demo_cases_gpt41
```

之后 Vercel 管理员页面会从数据库读取这些数据集。

### 5. 绑定 clawtrap.cn

在 Vercel Project Settings -> Domains 添加：

```text
clawtrap.cn
www.clawtrap.cn
```

然后去域名注册商处按 Vercel 给出的提示配置 DNS。通常是：

- `clawtrap.cn` 配 `A` 记录到 Vercel 指定 IP。
- `www.clawtrap.cn` 配 `CNAME` 到 Vercel 指定域名。

DNS 生效后，Vercel 会自动签发 HTTPS 证书。
# ClawTrap_BenchAnnotators
