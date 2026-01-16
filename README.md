# TK-Ops-Pro（TikTok 蓝海运营助手）

一个面向 TikTok Shop 运营团队的 Windows 桌面工具：选品利润清洗、AI 文案与二创、素材工厂、账号矩阵 CRM、局域网空投。

## 功能概览

- 选品利润清洗池：导入 EchoTik/Kalodata Excel/CSV，按成本/汇率/运费/佣金核算利润，支持参数配置与可视化筛选。
- AI 文案助手：基于 OpenAI 兼容接口（DeepSeek/自建网关等）生成标题/脚本/评论，支持模板化。
- AI 二创工厂：对视频做“脚本 + 配音 + 处理”工作流（耗时任务在 QThread 中执行，避免卡 UI）。
- 智能素材工厂：基于 moviepy/ffmpeg 的批处理去重、混剪、转码等能力。
- 账号矩阵 CRM：账号状态管理（正常/限流/封禁）与基础信息维护。
- 局域网空投：本机启动轻量 HTTP 服务，生成二维码，局域网设备扫码直下素材。

## 快速开始（Windows）

### 方式 A：一键脚本（推荐）

- 双击运行 `start.bat`（自动创建 venv、安装依赖并启动）。

### 方式 B：手动安装

```bash
python -m venv venv
./venv/Scripts/activate
pip install -r requirements.txt
```

启动：

```bash
python -m src.main
```

也支持：

```bash
python src/main.py
```

## 配置（.env）

项目使用项目根目录下的 `.env` 管理配置。首次使用可从 `.env.example` 复制：

```bash
copy .env.example .env
```

说明：

- `DOWNLOAD_DIR` 不配置时，默认使用 `AssetLibrary/Downloads`（更贴合“素材统一归档”）。
- AI 配置在【系统设置】里维护（文案助手与二创工厂共用）：可测试连通性、获取模型列表、选择模型。
- 为避免 `.env.example`/README 与实际 `.env` 漂移，程序启动时会自动“补齐缺失 key”，并把旧的 `DEEPSEEK_API_KEY` 迁移到 `AI_API_KEY`（不清空原值）。

### 常用配置项

| 模块 | 变量名 | 说明 |
| --- | --- | --- |
| 基础 | `THEME_MODE` | `dark` / `light` |
|  | `LOG_LEVEL` | `INFO` / `DEBUG` |
| 目录 | `DOWNLOAD_DIR` | 下载目录（不填则默认 `AssetLibrary/Downloads`） |
| 数据源 | `ECHOTIK_API_KEY` | EchoTik Username（可选） |
|  | `ECHOTIK_API_SECRET` | EchoTik Password（可选） |
| AI（共用） | `AI_PROVIDER` | `openai` / `deepseek` / `compatible` |
|  | `AI_BASE_URL` | OpenAI 兼容 Base URL（以服务文档为准，常见为 `https://xxx/v1`） |
|  | `AI_API_KEY` | API Key |
|  | `AI_MODEL` | 模型名称（可在设置页拉取列表后选择） |
| TTS | `TTS_VOICE` | 如 `en-US-AvaNeural` |
|  | `TTS_SPEED` | 如 `1.1` |
| 局域网空投 | `LAN_PORT` | HTTP 服务端口（默认 8000） |

## 目录结构

```text
tk-ops-assistant/
   src/
      main.py            # 程序入口
      config.py          # 配置读取/写回 .env
      ui/                # 界面层（PyQt5）
      workers/           # 耗时任务（QThread）
      utils/             # 工具与基础设施（日志、样式、局域网服务等）
      video/             # 视频处理能力（moviepy）
   AssetLibrary/        # 素材库（默认下载/归档目录）
   Output/              # 导出目录（报表/处理结果等）
   Logs/                # 日志目录
   start.bat            # 一键启动
   build.bat            # 打包脚本（PyInstaller）
   requirements.txt
```

## 打包（PyInstaller）

- 双击运行 `build.bat`
- 产物输出到 `dist/`（以脚本实际输出为准）

## 常见问题

- 启动报 Qt/sip 相关错误：优先使用 `start.bat` 重新安装依赖；确保同一虚拟环境下运行。
- AI “获取模型列表”失败：检查 `AI_BASE_URL` 是否为 OpenAI 兼容地址，以及服务是否支持 `/v1/models`。

## 免责声明

本工具仅供学习与内部效率提升使用；使用者需自行确保合规（平台规则、法律法规、版权与隐私等）。
