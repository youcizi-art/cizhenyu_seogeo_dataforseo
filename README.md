# seogeo-dataforseo（全局工具）

DataForSEO 的 MCP 服务 + CLI，供 agent 调用（关键词量级、难度、意图、SERP、竞品词）。

## 凭据（交付时只换这个文件）

```
C:\scripts\seogeo-auth-config\dataforseo_conf.json
```

| 字段 | 说明 |
|---|---|
| `API_login` / `API_password` | DataForSEO 账号 |
| `Base64_format` | 可选，预生成的 `login:password` Base64（存在则优先用） |

也可用环境变量 `SEOGEO_AUTH_DIR` 指向别的目录（一台机器多套账号时有用）。
**代码里不含任何密钥**，交付客户时替换该 json 即可。

## 自检

```powershell
& 'C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\python.exe' C:\scripts\seogeo-dataforseo\server.py check
```

返回 `balance_usd` 即为可用。

## CLI

```powershell
python server.py list
python server.py dfs_keyword_ideas   --json "{\"keyword\":\"nail lamp\",\"location\":\"United States\"}"
python server.py dfs_keyword_difficulty --json "{\"keywords\":[\"uv nail lamp\",\"gel nail lamp\"]}"
python server.py dfs_search_intent   --json "{\"keywords\":[\"oem nail lamp\",\"nail lamp wholesale\"]}"
python server.py dfs_serp_google     --json "{\"keyword\":\"uv nail lamp\",\"depth\":10}"
python server.py dfs_ranked_keywords --json "{\"domain\":\"sunuv.com\",\"limit\":100}"
python server.py dfs_serp_competitors --json "{\"keywords\":[\"uv nail lamp\",\"gel nail lamp\"]}"
```

## MCP 挂载

```yaml
- id: mcp-seogeo-dataforseo
  name: "@deepseek-ai/dsh-mcp-client"
  config:
    serverName: seogeo_dataforseo
    transport: stdio
    command: "C:/Users/Administrator/AppData/Local/Python/pythoncore-3.14-64/python.exe"
    args: ["C:/scripts/seogeo-dataforseo/server.py"]
    cwd: "C:/scripts/seogeo-dataforseo"
    failOnStartupError: false
    toolCallTimeoutMs: 180000
```

## 计费

每个接口按次扣费（SERP live ~$0.002/次，Labs 接口各自不同）。跑批量前先 `check` 看余额。

## Windows PowerShell 注意

PowerShell 调原生程序会吃掉内层双引号，`--json '{"a":"b"}'` 常失败。三种可靠写法：

```powershell
# 1) 用简单参数（推荐）
python server.py dfs_search_intent --keywords "oem nail lamp,gel nail lamp"

# 2) 用参数文件
python server.py dfs_serp_google --args-file args.json

# 3) 转义内层引号
python server.py dfs_keyword_difficulty --json '{\"keywords\":[\"uv nail lamp\"]}'
```
