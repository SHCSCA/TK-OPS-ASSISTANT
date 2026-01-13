# TK-Ops-Pro | TikTok 蓝海运营助手

<div align="center">

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![PyQt5](https://img.shields.io/badge/GUI-PyQt5-green)
![License](https://img.shields.io/badge/License-MIT-orange)
![Status](https://img.shields.io/badge/Status-Beta-yellow)

**一个专为 TikTok 卖家打造的现代化桌面运营工具。集成选品分析、智能素材混剪、本地资产管理与 AI 文案生成。**

[功能特性](#-功能特性) • [安装指南](#-安装指南) • [配置说明](#-配置说明) • [项目架构](#-项目架构) • [免责声明](#-免责声明)

</div>

---

## 📖 简介

**TK-Ops-Pro** 是一款基于 `PyQt5` 开发的高性能桌面应用程序，旨在解决 TikTok 跨境电商运营中的痛点。它不仅仅是一个脚本集合，而是一个拥有现代化 Flat UI 界面、健壮的后台任务队列和本地数据管理能力的完整解决方案。

从**蓝海选品数据挖掘**到**短视频批量去重混剪**，再到**AI 文案生成**，TK-Ops-Pro 提供了全流程的自动化支持。

![Screenshot Placeholder](https://via.placeholder.com/800x450?text=App+Dashboard+Preview)

## ✨ 功能特性

### 🔍 1. 蓝海选品监测 (Blue Ocean Monitor)
对接 **EchoTik** 等三方数据平台，实时挖掘潜力爆品。
- **智能筛选**：支持按增长率、销量、价格区间等多维过滤。
- **一键导出**：自动生成带图 Excel 报表，内置 1688 搜图链接。
- **IP 隔离检测**：内置 IP 纯净度检测工具，保障账号安全。

### 🎬 2. 智能素材工厂 (Video Factory)
基于 `moviepy` 和 `ffmpeg` 的高性能视频处理引擎。
- **批量去重**：微调帧率、比特率、画面裁剪、镜像翻转等深度去重算法。
- **智能混剪**：自动拼接多个视频片段，随机转场特效。
- **非阻塞处理**：采用多线程任务队列（Task Queue），处理视频时 UI 绝不卡顿。
- **懒加载技术**：优化启动速度，视频引擎仅在需要时加载，保证低配机器秒开。

### 📦 3. 本地素材库 (Asset Library)
内置 SQLite 数据库，告别混乱的文件夹管理。
- **元数据管理**：自动记录视频来源、处理时间、关联标签。
- **智能检索**：支持按标签、类型（原始/已处理）快速筛选素材。
- **剪贴板监听**：后台监听 TikTok 链接，自动下载并导入素材库。

### 🤖 4. AI 文案助手 (AI Copilot)
基于 OpenAI 标准接口（支持 DeepSeek/ChatGPT）。
- **模板化生成**：内置多种爆款文案模板（标题/脚本/评论）。
- **多语言支持**：一键生成英语、印尼语、泰语等本地化文案。

### 🛠 5. 诊断与运维 (Diagnostics)
企业级应用的健壮性设计。
- **环境自检**：一键检测 FFmpeg、Python 依赖、API 连通性。
- **自动修复**：提供常见问题的自动化修复方案。
- **一键构建**：提供 `build.bat` 脚本，基于 PyInstaller 生成独立 EXE 文件。

---

## 🚀 安装指南

### 前置要求
- Windows 10/11
- Python 3.9+ 
- FFmpeg (需添加到系统 PATH 环境变量)

### 开发环境搭建

1. **克隆项目**
   ```bash
   git clone https://github.com/yourusername/tk-ops-assistant.git
   cd tk-ops-assistant
   ```

2. **创建虚拟环境**
   ```bash
   # Windows
   start.bat
   # 该脚本会自动创建 venv 并安装依赖，然后启动应用
   ```

   或者手动：
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **运行程序**
   ```bash
   python src/main.py
   ```

---

## ⚙️ 配置说明

项目使用 `.env` 文件进行配置管理。首次运行请复制 `.env.example` 为 `.env`。

| 模块 | 变量名 | 说明 | 必填 |
| :--- | :--- | :--- | :---: |
| **基础** | `THEME_MODE` | 界面主题 (`dark`/`light`) | 否 |
| | `DOWNLOAD_DIR` | 默认下载/输出目录 | 否 |
| **数据源** | `ECHOTIK_API_KEY` | EchoTik 平台 API Key | **是** |
| | `ECHOTIK_API_SECRET`| EchoTik 平台 Secret | **是** |
| **AI** | `AI_PROVIDER` | AI 服务商 (`openai`/`deepseek`) | 否 |
| | `AI_API_KEY` | 模型 API Key | 否 |
| | `AI_MODEL` | 模型名称 (如 `gpt-3.5-turbo`) | 否 |

> 💡 **提示**: 你也可以在软件界面的「设置」面板中直接修改这些配置，保存后立即生效。

---

## 🏗 项目架构

采用模块化分层架构，确保代码的可维护性与扩展性。

```plaintext
tk-ops-assistant/
├── src/
│   ├── main.py              # 程序入口
│   ├── config.py            # 全局配置管理
│   ├── ui/                  # 界面层 (PyQt5)
│   │   ├── main_window.py   # 主窗口框架
│   │   ├── material_factory.py # 素材工厂 UI
│   │   └── ...
│   ├── workers/             # 业务逻辑层 (QThread)
│   │   ├── task_queue.py    # 通用任务队列
│   │   ├── video_worker.py  # 视频处理线程
│   │   └── ...
│   ├── video/               # 视频处理核心算法
│   ├── db/                  # 数据库层 (SQLite)
│   ├── ai/                  # AI 接口层
│   └── utils/               # 工具类
├── pyinstaller_hooks/       # 打包 Hook 配置
├── requirements.txt         # 依赖列表
├── start.bat                # 快速启动脚本
└── build.bat                # EXE 构建脚本
```

---

## 🛠 构建发布

本项目包含完整的 PyInstaller 构建配置，支持一键生成单文件 EXE。

1. 双击运行 `build.bat`
2. 构建产物将输出至 `dist/tk-ops-assistant.exe`

**构建特性：**
- 自动处理 `numpy` 版本兼容性
- 自动挂载 `pyinstaller_hooks` 解决 SIP 模块冲突
- 自动包含必要的资源文件

---

## 🤝 贡献指南

欢迎提交 Issue 或 Pull Request！我们欢迎所有形式的贡献，包括新功能、Bug 修复、文档改进等。

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

---

## ⚠️ 免责声明

本工具仅供技术研究与学习使用。

- **合规性**：使用者须严格遵守 TikTok 平台规则及相关法律法规。
- **数据使用**：严禁用于非法抓取个人隐私数据或侵犯版权的行为。
- **责任限定**：作者不对因使用本工具导致的账号封禁、法律诉讼或其他损失承担任何责任。

---

<div align="center">
    Made with ❤️ by TK-Ops Team
</div>
