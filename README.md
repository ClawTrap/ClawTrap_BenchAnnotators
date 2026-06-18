# ClawTrap Benchmark Creation Page

本项目包含两个部分：

- 审核 Web 页面：登录后审阅本地攻击场景，执行保留、Discard、Mark notes，并查看原始库与最终 Benchmark 集合。
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

审核页、原始库和 Benchmark 页面会显示并筛选数据来源。这里的数据来源指 JSON 文件来源，来源优先级为：

`data_file` -> `data_source` -> `dataset + ".json"` -> `source_file`

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
python -m flask --app clawtrap_benchmark.web run --host 127.0.0.1 --port 5055
```

打开 `http://127.0.0.1:5055`，使用已配置的账号 ID 和密码登录。未配置在账户表中的 ID 不能进入系统。

### 账号与权限

生产部署必须配置账号密码。最简单的方式是在 `.env` 或 Vercel Environment Variables 中配置：

```bash
SECRET_KEY="一串很长的随机字符串"

# 管理员账号 1
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="换成强密码"

# 管理员账号 2
ADMIN_USERNAME_2="admin2"
ADMIN_PASSWORD_2="换成另一个强密码"

# 标注员账号，多个账号用逗号、分号或换行分隔
ANNOTATOR_ACCOUNTS="reviewer01:强密码,reviewer02:强密码"
```

所有已配置账号都可以进入当前工作台。工作台入口包括审核、原始库检查和 ClawTrap Bench 检查。

也可以使用一个 JSON 账户表集中管理：

```bash
CLAWTRAP_ACCOUNTS_JSON='{
  "admin": {"password": "换成强密码", "role": "admin"},
  "admin2": {"password": "换成另一个强密码", "role": "admin"},
  "reviewer01": {"password": "强密码", "role": "annotator"}
}'
```

`CLAWTRAP_ACCOUNTS_JSON` 也支持 `password_hash` 字段；如果提供 hash，会优先按 hash 校验。未配置任何账户时，仅本地非 Vercel 开发环境会临时开放 `admin/admin` 和 `admin2/admin2` 两个开发管理员账号。

生成密码 hash 的方式：

```bash
python -c "from werkzeug.security import generate_password_hash; import getpass; print(generate_password_hash(getpass.getpass('Password: ')))"
```

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
SECRET_KEY="一串很长的随机字符串"
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="换成强密码"
ADMIN_USERNAME_2="admin2"
ADMIN_PASSWORD_2="换成另一个强密码"
ANNOTATOR_ACCOUNTS="reviewer01:强密码,reviewer02:强密码"
OPENAI_API_KEY="..."
OPENAI_BASE_URL="..."
OPENAI_MODEL="gpt-4.1"
```

如果要在线保存审核裁决、字段修改和 Benchmark 入选标记，必须添加 PostgreSQL 连接串。Raw case 池仍然从 repo 内的 `data/*.json` 读取，不需要把原始数据 seed 到数据库：

```bash
DATABASE_URL="postgresql://..."
```

也可以使用 Vercel Marketplace 里的 Neon/Vercel Postgres。没有 `DATABASE_URL` 时，Vercel 上仍可读取 repo 内的 `data/*.json`，但保存接口会返回明确错误，避免误以为数据已持久保存。

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
