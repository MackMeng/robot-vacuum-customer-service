# 架构设计文档

本文档描述扫地机器人智能客服系统的内部设计，配合根目录 `README.md` 阅读。

## 1. 分层总览

系统自上而下分为四层：

| 层 | 模块 | 职责 |
|---|---|---|
| 交互层 | `app.py`、`api.py` | Streamlit 聊天界面（流式渲染、会话侧边栏）；FastAPI HTTP 接口（SSE 流式、会话 CRUD） |
| 智能体层 | `agent/react_agent.py`、`agent/tools/`、`agent/report_graph.py` | ReAct 决策、工具调用、中间件增强、报告子图编排 |
| 能力层 | `rag/`、`model/`、`mcp_server/` | 检索总结、向量存储、模型实例、MCP 天气服务 |
| 基础设施层 | `utils/`、`config/`、`prompts/`、`Dockerfile` | 配置、提示词、日志、文件/路径/MCP 客户端工具、容器化 |

## 2. 智能体层

### 2.1 ReactAgent

`agent/react_agent.py` 中的 `ReactAgent` 对 LangChain `create_agent` 做了一层封装：

- 装配 `model`（模型工厂产物）、`system_prompt`（主提示词）、4 个对外 `tools`、2 个 `middleware`；
- `execute_stream(query, history)` 以 `stream_mode="values"` 流式执行，仅 yield 模型的最终文本回答（跳过工具结果与带工具调用的中间消息）；`history` 为既往对话，按滑动窗口仅保留最近 8 条，避免上下文无限增长；
- 报告生成不在主循环内自由编排，而是交由 `generate_usage_report` 工具内部的报告子图（见 2.4）完成。

### 2.2 工具（agent/tools/agent_tools.py）

| 工具 | 入参 | 作用 |
|---|---|---|
| `rag_summarize` | `query` | 调用 RAG 服务检索并总结知识库 |
| `get_city_name` | 无 | 获取用户城市（演示：随机） |
| `get_weather` | `city` | 经 MCP 天气服务（Open-Meteo）获取真实天气；服务不可用时降级为提示字符串，不中断对话 |
| `generate_usage_report` | 无 | 运行报告子图，返回个性化使用报告 |

报告子图内部复用、但不直接暴露给模型的数据工具：`get_user_id`（随机）、`get_current_month`（随机）、`fetch_external_data`（读取使用记录 CSV）。`fetch_external_data` 首次调用时惰性加载 `records.csv` 到内存字典 `external_data[user_id][month]`，缺失记录返回空字典并记录告警。

### 2.3 中间件（agent/tools/middleware.py）

- `monitor_tool`（`@wrap_tool_call`）：记录工具名与参数、成功/失败日志。
- `log_before_model`（`@before_model`）：模型调用前记录消息数量与最新消息。

### 2.4 报告子图（agent/report_graph.py）

报告生成用显式 LangGraph `StateGraph` 编排，状态 `ReportState`（`user_id` / `month` / `records` / `report`）在节点间流转：

```
START → resolve_user → resolve_month → fetch_records
      → 条件边 has_records
          ├─ 有记录 → generate_report（模型依据记录撰写）→ END
          └─ 无记录 → no_record（返回提示）        → END
```

节点复用数据工具与 `chat_model`、`report_prompt.txt`；对外仅暴露 `run_report()`，由 `generate_usage_report` 工具调用。相比原先「中间件切提示词 + 模型自主决定调用顺序」，这里把流程固化为图，状态流转清晰、可扩展（后续可加人工介入/断点）。

### 2.5 MCP 天气服务与客户端

天气查询通过 MCP（Model Context Protocol）拆成独立进程，而非在 Agent 进程内直连 HTTP：

- **服务端** `mcp_server/weather_server.py`：`FastMCP` 以 stdio 传输暴露 `get_weather(city)`，内部调 Open-Meteo 地理编码 + 预报接口（免 Key），WMO 天气码转中文，返回带数据来源的字符串；
- **客户端** `utils/mcp_client.py`：`run_mcp_tool(server_script, tool_name, args)` 用 `StdioServerParameters` 拉起服务子进程、`initialize` 后 `call_tool`，汇总文本内容返回；
- **同步/异步桥接**：MCP SDK 全异步，而 LangGraph / Streamlit 的调用链是同步的。客户端把 `asyncio.run` 放进一个新线程执行并 `join(timeout)`，避免「event loop already running」，也便于统一超时（默认 30s）。

`get_weather` 仅负责取路径与异常降级：MCP 不可用（无外网、子进程失败、超时）时记录错误并返回提示文本，保证 ReAct 链路不因外部依赖中断。

## 3. 能力层

### 3.1 模型工厂（model/factory.py）

采用抽象工厂模式：`BaseModelFactory` 定义 `generator()` 抽象方法，`ChatModelFactory` 与 `EmbeddingModelFactory` 分别产出 `ChatOpenAI`（新一代千问模型仅支持 OpenAI 兼容端点，`base_url` 配置化）与 `DashScopeEmbeddings`（需向封装层 `BATCH_SIZE` 表注册新模型批次上限）。模块级单例 `chat_model` / `embedding_model` 在导入时创建，供全局复用。

### 3.2 RAG 流水线

**离线（`rag/vector_store.py` 的 `load_documents`）：**

```
遍历 data/ 允许类型文件 → 计算 MD5 → 已处理则跳过
  → PDF/TXT 加载为 Document → RecursiveCharacterTextSplitter 分块
  → 嵌入并写入 Chroma → 记录 MD5
```

MD5 去重保证增量加载：仅新增或内容变更的文档才会重新嵌入。注意 MD5 记录与集合配套：更换嵌入模型时向量空间不兼容，需同时换新集合名与 MD5 记录文件重建。

**在线（`rag/rag_service.py` 的 `rag_summarize`）：**

```
query → retriever 粗召回 top-k 文档 → DashScopeRerank 精排留 top-n
  → 拼接为带元数据的参考资料 → 填充 RAG 提示词模板 → 模型 → StrOutputParser → 总结字符串
```

两段式检索：粗召回保覆盖率，精排保相关性；精排模型名构造后显式覆盖（封装层默认模型已下线），精排后文档 metadata 附带 `relevance_score`。

### 3.3 离线测评（evals/）

轻量测评模块，不引入额外评估框架，直接复用生产链路的 `RagSummarizeService`：

- **标注集**：`evals/dataset.jsonl`，每行一个用例（`query` / `keywords` / `source`），随代码进版本库；
- **指标**：检索关键词召回率、期望来源命中率；`--with-answer` 时额外算答案关键词覆盖率（忠实度代理指标）；
- **消融对照**：`--no-rerank` 基线用粗召回截断到相同 top_n，与默认 rerank 组对照量化精排贡献；基线答案用已检索片段直接走总结链，保证上下文拼接一致；
- **报告**：带时间戳存入 `evals/results/`（gitignore），支持历次纵向对比；改动检索相关配置后重跑对照，指标不回退再上线。

实测基线 vs rerank（12 用例）：关键词召回 79.2% → 91.7%，来源命中 83.3% → 91.7%。注意关键词覆盖是代理指标：否定表述（如"不可直接冲洗"）与跨分片关键词会造成假阴性，低分用例需人工复核而非直接归咎检索。

## 4. 基础设施层

- `utils/cofig_handler.py`：加载四个 YAML 配置为模块级字典。
- `utils/prompt_loader.py`：按配置路径加载三套提示词，缺失配置项/文件时记录并抛出异常。
- `utils/path_tool.py`：以本文件位置推导项目根目录，提供 `get_abspath`，使运行不依赖当前工作目录。
- `utils/file_handler.py`：MD5 计算、按类型遍历目录、PDF/TXT 加载。
- `utils/logger_handler.py`：统一日志器，控制台 + 按天文件输出。
- `utils/mcp_client.py`：MCP 客户端，在独立线程中跑异步 SDK 调用 stdio 服务（见 2.5）。
- `utils/session_store.py`：SQLite 会话持久化，提供建表与新建/列表/加载/保存/删除。

### 4.1 会话存储（utils/session_store.py）

为 Web 端提供多轮对话的持久化，单表 `sessions` 存储：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | 会话唯一 ID |
| `title` | TEXT | 侧边栏标题，取首条用户消息前 20 字 |
| `messages` | TEXT | 整段对话的 JSON（role/content 列表） |
| `created_at` / `updated_at` | DATETIME | 创建 / 最近活跃时间 |

CRUD：`create_session` / `list_sessions`（按 `updated_at` 倒序）/ `load_messages` / `save_messages` / `delete_session`。

设计要点：

- **整段 JSON 存储**：demo 规模下整读整写最简单，无需按消息拆表；
- **随用随开连接**：每次操作独立 `connect`/`commit`/`close`，规避 Streamlit 多线程下的 `check_same_thread` 限制；
- **中文不转义**：`json.dumps(..., ensure_ascii=False)`；
- **懒创建会话**：点击「新建」仅清空状态，首条消息落库时才真正 `INSERT`，避免空会话；
- **只存最终对话**：持久化干净的 user/assistant 文本，不含 ReAct 中间工具轨迹。

## 5. 接口与部署

### 5.1 FastAPI（api.py）

同一套 `ReactAgent` 与会话存储对外暴露 HTTP 接口：

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/health` | 健康检查（Docker healthcheck 使用） |
| `GET` | `/sessions` | 会话列表 |
| `DELETE` | `/sessions/{id}` | 删除会话 |
| `POST` | `/chat` | 对话，`StreamingResponse` + `text/event-stream` |

`POST /chat` 的 SSE 事件序列：

```
event: session  data: {"session_id": 10, "created": true}
data: <文本分片>        （可多次）
event: done     data: [DONE]
event: error    data: <错误信息>（异常时替代 done）
```

要点：

- **懒加载智能体**：`get_agent()` 在首次请求时导入并构造 `ReactAgent`，避免模块导入即要求 `DASHSCOPE_API_KEY`，让健康检查与路由探测在无 Key 环境也能工作；
- **会话复用**：请求未带 `session_id` 时新建会话并通过 `event: session` 回传；已有则加载历史作为上下文；
- **流结束再落库**：把历史、用户输入、模型输出拼成完整对话后一次性 `save_messages`，与 UI 端「只存最终对话」的约定一致；
- **错误隔离**：流中异常转为 `event: error`，不让连接悬挂。

### 5.2 容器化（Dockerfile / docker-compose.yml）

- `Dockerfile`：`python:3.13-slim`，装依赖后 `COPY` 全项目；入口 `docker-entrypoint.sh` 在 `chroma_db/chroma.sqlite3` 缺失时先执行 `python -m rag.vector_store`，再 `exec` 传入命令；默认 `CMD` 为 `uvicorn api:app --host 0.0.0.0 --port 8000`；
- `docker-compose.yml`：`api`（8000）与 `ui`（8501，`streamlit run app.py`）两服务；`ui` 通过 `depends_on: service_healthy` 等 API 健康；两者共享 `chroma_db` 命名卷，`DASHSCOPE_API_KEY` 由宿主环境透传；
- **已知约束**：仅向量库跨容器共享，`data/sessions.db` 仍各自独立——API 建的会话不会出现在 UI 侧边栏。demo 可接受；若需统一，应把会话库挂为共享卷或迁到外部数据库。

## 6. 关键设计取舍

- **配置与提示词外置**：模型 ID、分块参数、提示词内容均与代码分离，便于调整而无需改代码。
- **报告流程显式图编排**：报告生成用 `StateGraph` 固定节点与条件边，流程确定、状态可追踪；扩展新分支（如按面积分档给建议）只需加节点/边。
- **增量知识库**：MD5 去重降低重复嵌入成本。
- **演示用模拟工具**：城市/用户/月份与外部使用记录为模拟实现，便于在无外部依赖时跑通完整 ReAct 链路；天气已通过 MCP 接真实数据，并保留不可用时的降级提示。
- **MCP 独立进程**：天气能力与主进程解耦、可单独替换/复用；代价是多一层进程与序列化开销，故客户端加了超时与降级。
- **SSE 而非 WebSocket**：对话是单向服务端推流，SSE 基于普通 HTTP、实现与调试成本更低；若后续需要双向中断/语音等再考虑 WebSocket。
- **会话存储选 SQLite**：单机单用户、低并发场景下零依赖、免起服务，克隆即可跑，降低复现门槛；多用户线上部署再迁移 MySQL（SQL 与表设计通用）。
- **滑动窗口上下文**：仅向模型传入最近若干轮历史，控制 token 成本与上下文长度，避免长会话超窗口。