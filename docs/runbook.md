# 全栈启动手册（CRM + AI 能力层）

覆盖三个进程组：本机向量模型（Ollama）、AI 能力层（`D:\codex`）、
自研 CRM（`D:\crm`）。两个仓库各自独立启动，互不内嵌：
CRM 只管业务数据，AI 层只通过 REST 契约读写 CRM。

## 1. 服务与端口总览

| 服务 | 端口 | 仓库 | 本机状态 |
| --- | --- | --- | --- |
| Ollama 向量服务 | 11434 | 本机安装 | 未验证（需自行安装） |
| AI 层 Postgres（pgvector） | 5432 | `D:\codex` | 未验证（本机无 docker） |
| AI 层 Redis | 6379 | `D:\codex` | 未验证（本机无 docker） |
| AI 层 API | 8000 | `D:\codex` | 未验证（live 依赖外部 key） |
| AI 层前端 dev | 5173 | `D:\codex` | 未验证 |
| **CRM API** | **9100** | `D:\crm` | **已验证（sqlite）** |
| CRM 前端 dev | 5174 | `D:\crm` | 已验证（tsc + vite build） |
| CRM Postgres | 5433 | `D:\crm` | 未验证（本机无 docker） |

端口刻意错开：AI 层占 5432 / 8000 / 5173，CRM 占 5433 / 9100 / 5174。

## 2. 一次性准备

```powershell
python -V          # 需要 3.11+
node -v            # 需要 18+
ollama --version   # 用本机向量模型时需要
docker -v          # 用容器形态时需要
```

依赖安装（两个仓库分别装）：

```powershell
cd D:\crm
pip install -r requirements.txt
cd D:\crm\web
npm install

cd D:\codex
pip install -r requirements.txt
cd D:\codex\web
npm install
```

配置文件（各自目录下的 `.env`，缺省值可直接开发用）：

```powershell
cd D:\crm
copy .env.example .env
cd D:\codex
copy .env.example .env
```

## 3. 启动顺序

依赖顺序：Ollama → AI 层基础设施 → CRM → AI 层 API → 两个前端。

### 3.1 Ollama（本机向量模型）

```powershell
ollama serve
ollama pull mxbai-embed-large
curl http://127.0.0.1:11434/api/tags
```

`mxbai-embed-large` 是 1024 维。换模型必须三处同时改，否则向量无法入库：
`AICRM_EMBEDDING_MODEL`、`AICRM_EMBEDDING_DIM`、`D:\codex\sql\001_init.sql` 里的 `vector(N)`，
改完重建索引。

### 3.2 AI 层基础设施（Postgres + Redis）

```powershell
cd D:\codex
docker compose up -d
docker compose ps
```

只有在用 postgres 存储或需要向量检索持久化时才必须启动；
`AICRM_STORAGE=memory` 时 AI 层可以不依赖这两个服务。

### 3.3 CRM 后端（默认 sqlite，零外部依赖）

```powershell
cd D:\crm
python -m uvicorn app.main:app --host 127.0.0.1 --port 9100
```

首次启动会自动建表、写入演示数据、创建管理员账号。自检：

```powershell
curl http://127.0.0.1:9100/health
```

接口文档在 `http://127.0.0.1:9100/docs`。
若 `D:\crm\web\dist` 存在，9100 还会直接把 CRM 界面托管出来；
没有构建产物时自动退化成纯 API（AI 层对接不受影响）。

### 3.4 CRM 前端（开发形态）

```powershell
cd D:\crm\web
npm run dev
```

访问 `http://127.0.0.1:5174`，开发服务器把 `/api` 代理到 9100。

### 3.5 CRM 生产形态（Postgres + 容器）

```powershell
cd D:\crm\web
npm run build            # 必须先构建，容器只负责托管 web/dist

cd D:\crm
docker compose up -d --build
docker compose ps
```

CRM Postgres 暴露在 5433，API 在 9100。
容器通过 `./web/dist` 挂载读取前端产物，所以构建要在宿主机做。

不用容器、只想把 CRM 切到本机 Postgres：

```powershell
pip install psycopg[binary]
$env:CRM_STORAGE = 'postgres'
$env:CRM_DATABASE_URL = 'postgresql+psycopg://crm:crm@localhost:5433/crm'
python -m uvicorn app.main:app --host 127.0.0.1 --port 9100
```

### 3.6 AI 能力层

先确认要连真实 CRM（`rest`），否则默认是内存假数据（`fake`）：

```powershell
cd D:\codex
$env:AICRM_CRM_MODE = 'rest'
$env:AICRM_CRM_BASE_URL = 'http://127.0.0.1:9100/api/v1'
$env:AICRM_CRM_API_TOKEN = 'dev-service-token'
$env:AICRM_CRM_AUTH_MODE = 'bearer'
```

`AICRM_CRM_API_TOKEN` 必须等于 CRM 的 `CRM_SERVICE_TOKEN`，两边同时改。

本机向量 + DeepSeek：

```powershell
$env:AICRM_EMBEDDING_PROVIDER = 'http'
$env:AICRM_EMBEDDING_BASE_URL = 'http://127.0.0.1:11434/v1'
$env:AICRM_EMBEDDING_MODEL = 'mxbai-embed-large'
$env:AICRM_EMBEDDING_DIM = '1024'

$env:AICRM_LLM_MODE = 'live'
$env:AICRM_LLM_BASE_URL = 'https://api.deepseek.com/v1'
$env:AICRM_LLM_API_KEY = 'sk-...'
$env:AICRM_LLM_MODEL_FAST = 'deepseek-chat'
$env:AICRM_LLM_MODEL_DEEP = 'deepseek-chat'
```

本机实测：`deepseek-chat` 会被映射成 `deepseek-flash`；可用模型是 `deepseek-flash` 与 `deepseek-v4-pro`，
两者都支持 function calling，所以快档慢档都留 `deepseek-chat` 即可。
真实 key 只写进 `D:\codex\.env` 的 `AICRM_LLM_API_KEY`（`.env` 已被 .gitignore 忽略）；
写进 `.env.example` 不会生效，那是模板文件。改完 `.env` 必须重启后端才生效。

启动 API 与前端：

```powershell
cd D:\codex
python -m uvicorn app.main:app --port 8000

cd D:\codex\web
npm run dev              # 5173
```

### 3.7 MCP 工具（可选，AI 层侧）

MCP 默认关闭，跟 CRM 没有耦合：AI 层只是多接几个外部工具。

```powershell
cd D:\codex
pip install -r requirements.txt          # mcp>=1.9 才需要；不启用可以不装

$env:AICRM_MCP_ENABLED = 'true'
$env:AICRM_MCP_SERVERS = '[{"name":"fs","transport":"stdio","command":"npx","args":["-y","@modelcontextprotocol/server-filesystem","D:/data"],"read_only_tools":["read_text_file","list_directory"]}]'

python -m uvicorn app.main:app --port 8000
curl http://127.0.0.1:8000/health        # 看 mcp 字段：connected / exposed / blocked / error
```

- 只想验证链路、不想装外部服务：`tests/mcp_server_fixture.py` 就是本地样例服务端，把
  `command` 填成 `python`、`args` 填成 `["D:\\codex\\tests\\mcp_server_fixture.py"]` 即可。
- 读工具直接用；写工具默认不暴露，必须在 `allow_write_tools` 里点名才会注册给模型。
- 单个服务端连不上不影响启动，状态只在 `/health` 的 `mcp.servers[].error` 里体现。

## 4. 账号与令牌

| 用途 | 值 |
| --- | --- |
| CRM 管理员 | `admin@example.com` / `admin12345` |
| CRM 主管（t-sales） | `chenxiao@example.com` / `sales12345` |
| CRM 销售（t-finance） | `zhoumin@example.com` / `sales12345` |
| AI 层服务令牌 | `dev-service-token` |

以上都由 CRM 的 `CRM_*` 环境变量决定，生产环境必须全部替换。

调 AI 层时的身份请求头是 `X-User-Id` / `X-Team-Ids`（逗号分隔）/ `X-User-Admin`。
注意 `AICRM_DEFAULT_USER_ADMIN=true`（本机默认）只对「一个身份头都不带」的请求生效：
只要带了 `X-User-Id` 或 `X-Team-Ids`，该请求就按普通用户处理，只读得到本人或本团队的数据，
要管理员视角必须显式带 `X-User-Admin: true`。所以转发身份头时不会因为漏配 admin 而越权。

## 5. 联调验证顺序

按这个顺序排查，每一步都能独立定位问题：

1. CRM 自测：`cd D:\crm; python -X utf8 -m unittest discover -s tests -t .`
2. 契约探测（只读，不写数据）：

   ```powershell
   cd D:\codex
   python -X utf8 scripts\crm_probe.py --base-url http://127.0.0.1:9100/api/v1 --token dev-service-token --auth-mode bearer --all --show-raw
   ```

   期望：8 个对象都有返回，响应键里能看到 `next_cursor` 与 `total`。
3. 全量同步：`POST http://127.0.0.1:8000/api/v1/sync/all`
4. 控制台问答：带 `X-User-Id` / `X-Team-Ids` / `X-User-Admin` 调 `/api/v1/chat`
5. 业务技能：摘要、线索评分、跟进草稿、客户 360
6. 写回与审批：低风险动作自动执行，高风险（推阶段、赢单、转派、删除）要人工审批
7. 回到 CRM 界面确认字段变化，并在「审计」页看到 AI 写回记录（来源标记为 `ai`）
8. MCP（可选）：`curl http://127.0.0.1:8000/health`，`mcp.connected` 大于 0 即接入成功；
   提问时模型引用 `[mcp:服务端/工具]`，结果同样过引用白名单

## 6. 故障定位

- CRM 起不来：端口 9100 被占、`CRM_STORAGE` 拼错、`.env` 编码不是 UTF-8。
- AI 层 401：`AICRM_CRM_API_TOKEN` 与 CRM 的 `CRM_SERVICE_TOKEN` 不一致。
- 列表返回 200 但 `data` 为空：行级权限（该账号看不到这些记录），不是接口坏了。
- AI 侧字段对不上：看探测脚本打印的「未映射字段」，那部分会进 `_extra`。
- 写回 409：版本冲突（别人先改了）或幂等键被不同请求体复用。
- 写回 404：记录不存在，或当前身份看不到（越权和不存在统一返回 404）。
- 写回 403：记录看得见但没有写权限（例如销售改同队他人的记录）。
- 向量相关报错：Ollama 没起、`AICRM_EMBEDDING_DIM` 与 `vector(N)` 不一致。
- 改了 `.env` 不生效：配置只在进程启动时读一次，必须重启后端；写进 `.env.example` 同样不生效。
- 助手回答风格没变：`AICRM_SYSTEM_PROMPT*` 没配，或被 `AICRM_SYSTEM_PROMPT_FILE` 覆盖；
  文件路径写错会直接启动失败（`PromptConfigError`）。
- 前端页面 404：`web/dist` 没构建；`/api`、`/health`、`/docs` 是保留前缀，不会被前端接管。
- MCP 不生效：`AICRM_MCP_ENABLED` 没开、`AICRM_MCP_SERVERS` 的 JSON 非法（启动即抛错）、
  `.env` 里没给整段 JSON 加单引号、Windows 路径没写正斜杠（`D:/data`）、或 `command` 不在 PATH 里（看 `mcp.servers[].error`）。
- MCP 工具不见了：写工具默认不暴露；只读工具要么服务端给了 `readOnlyHint`，要么在
  `read_only_tools` 里显式声明，否则按写处理。

## 7. 已修复的对接问题

### 7.1 团队归属读不到（2026-09-22 修复）

AI 层 `app/integrations/crm/field_map.py` 的 `normalize_record` 以前按原始字段名
`owner_team_ids` 去取值，而映射表声明的是 `team_ids -> owner_team_ids`，于是 REST 模式下
`owner_team_ids` 恒为空，团队维度 ACL 退化成只看 `owner_id`。

现在统一用 `raw_key_for(mapping, ...)` 按归一化名反查原始字段名。实测（9100 CRM）：

- 记录上 `owner_team_ids` 正常落成 `['t-sales']` / `['t-finance']`。
- 身份 `X-User-Id: u-300` + `X-Team-Ids: t-finance` 只看到 `lead-0002`；
  同队其它记录与非本队记录都不可见。

### 7.2 负责人不进检索文本（2026-09-22 修复）

记录切块只写了字段值，`owner_id` / `owner_team_ids` 只挂在 chunk 元数据上，模型看不到，
所以「这条线索归谁」只能答「资料缺口」。现在 `app/rag/chunker.py` 的 `_owner_lines`
会把两个字段写进正文，答案能给出负责人（如 `u-100` → `陈晓`）与归属团队。

### 7.3 流式问答必然降级（2026-09-22 修复）

`app/integrations/llm/gateway.py` 的 `HttpLlmClient.stream` 在收到上游 usage 结算时，直接给
`event.usage.model / .tier / .latency_ms` 赋值。`LlmUsage` 是 `@dataclass(frozen=True)`，于是每轮
带 usage 的流式请求都抛 `FrozenInstanceError`，被上层当成模型故障，整段回答降级成
「模型暂时不可用，以下是本次检索到的原文片段」，`degrade_reason = 模型调用失败：FrozenInstanceError`。

因为 `stream` 里带了 `stream_options.include_usage=true`，DeepSeek 一定会回 usage 分片，所以
**前端流式问答 100% 复现，非流式 `/api/v1/chat` 反而正常**。现在用 `dataclasses.replace` 造新对象
补齐档位与耗时，不再改冻结实例；`tests/test_stream.py::HttpLlmStreamTest` 用 `httpx.MockTransport`
跑完整 SSE 通路守住这个回归（改回直接赋值即失败）。

## 8. 本机验证状态

仍未验证（只交付代码与命令，不要当成跑过）：

- Postgres 形态的 CRM 与 AI 层（本机无 docker、无 Postgres 实例、无 `psycopg`）。
- `docker compose` 相关的镜像构建与容器编排。

已经在 2026-09-22 实测过：

- CRM：sqlite 形态、108 条 unittest、前端 `tsc --noEmit` 与 `vite build`、`crm_probe.py` 的 8 对象契约探测。
- AI 层：199 条 unittest（含真实 stdio 子进程的 MCP 链路、真 SSE 通路回归）、前端 `tsc --noEmit` 与 `vite build`、Ollama `http` 向量（`mxbai-embed-large`，1024 维，`embedding_ok=true`）。
- AI 层接 CRM 9100 的 `POST /api/v1/sync/all`：8 个对象、0 失败、10 条记录、10 个块。
- 团队维度 ACL：`t-finance` 身份只看到本队记录，越权记录不出现。
- `AICRM_ORCHESTRATOR=langgraph` 编排：与 native 行为一致（对照测试 + 真实问答）。
- DeepSeek `live` 问答（真实 key）：`grounded=true`、`degraded=false`、引用全部来自白名单；自定义系统提示词生效。
- DeepSeek 流式问答 `/api/v1/chat/stream`（真实 key）：`degraded=false`、`degrade_reason` 为空、4 条引用；done 事件里的 usage 结算正常（`tier=deep`、`latency_ms` 有值）。
