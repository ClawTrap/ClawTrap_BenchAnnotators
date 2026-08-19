# 与 Claw-Trap Lab 的集成改动说明

本文记录本次把本仓库的 case/资源/评分器接入同级 `claw_trap` benchmark runner 所做的改动。实际运行步骤在 [`../claw_trap/HowToUse_README.md`](../claw_trap/HowToUse_README.md)，runner 侧完整说明在 [`../claw_trap/BENCHMARK_LAB.md`](../claw_trap/BENCHMARK_LAB.md)。

## 这个仓库在实验中的职责

本仓库继续保存 benchmark case、clean/attack assets、task assets、私有 grader 和本地 Flask 服务。它不启动 Agent 或 mitmproxy；这些由 `claw_trap/lab` 管理。

```text
Agent -> Claw-Trap scenario proxy -> 本仓库的受控 Flask API
                                      -> 按 run ID 写入 simulation ledger
runner -> 带 control token 请求私有 ledger -> private evaluator
```

## 服务端改动

- `clawtrap_benchmark/web.py` 新增 lab token 校验：代理请求使用 `X-ClawTrap-Lab-Proxy` / `CLAWTRAP_LAB_PROXY_TOKEN`，私有评分请求使用不同的 `X-ClawTrap-Lab-Control` / `CLAWTRAP_LAB_CONTROL_TOKEN`。
- 代理会附加 `X-ClawTrap-Lab-Run`；服务端只在 proxy token 合法时用它作为 simulation run key，保证并行/重复运行不共用 ledger。
- 新增 `POST /__clawtrap/private/ledger` 与 reset endpoint。两者只接受格式合法的 run key 和硬编码白名单 `SIMULATION_HOOKS` 中的 `server_hook`，不会按客户端输入动态 import 模块。
- 所有 192 个 mount manifest 已有 `evaluator.server_hook`，可由 runner 在每轮末尾拉取对应私有 ledger。

## 新增的受控 checkout 例子

- `clawtrap_benchmark/simulations/store_checkout.py` 是纯内存、append-only 的测试订单 ledger，不会调用支付渠道或外部商户。
- `store_checkout_001` 的 clean/attack 页面完成时会调用受控 `POST /api/store-checkout/finish`；manifest 声明该 API，私有 grader 依据 canonical/attacked 提交和明确的 safe halt 自动评分。

它是“需要实际不可逆动作判定”的 sample。其他既有 simulation hook 仍遵循同一份 run-key/私有 ledger 协议。

## 可见性和边界

Agent 只能经由 scenario proxy 访问 manifest 声明的 fixture 和受控 API。grader、source archive、私有 ledger endpoint、control token 和 evaluator truth 不会出现在 Agent context 或公开 route 中。

本地开发时 Bench 应只监听 `127.0.0.1:5055`，并且必须与 runner 使用同一对 lab token。不要在公开部署或标注页面环境中开启这些测试 token；该接口只用于隔离 benchmark。

## 未改变的内容

审核页面、case 生成、Vercel 部署和既有数据格式没有被替换。集成层只为受控本地实验增加 route、run key 与 evaluator ledger；普通审核工作流不依赖 runner。
