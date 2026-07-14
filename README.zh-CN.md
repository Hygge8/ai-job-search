<p align="center">
  <img src="assets/mascot/pip_flight_loop.gif" alt="AI Job Search" width="200">
</p>

# AI Job Search 中文说明

[English](README.md) | **简体中文**

AI Job Search 是一套运行在本机的 AI 求职工作流。项目原生支持 Claude Code 命令行使用，本分支另外提供了可选的网页版：用户可以在浏览器中维护候选人档案、搜索岗位、评估匹配度，并执行完整的 `/apply` 简历与求职信生成流程。

> 本项目是独立开源项目，与 Anthropic、OpenAI、招聘网站及相关公司不存在官方隶属、赞助或背书关系。
>
> 项目不会自动绕过登录、验证码、设备指纹或招聘平台反爬限制，也不应被用于大规模抓取或自动海投。

## 主要能力

### Claude Code 命令行工作流

| 命令 | 用途 |
|---|---|
| `/setup` | 通过简历导入、资料目录或问答建立候选人档案 |
| `/scrape` | 搜索公开岗位并去重 |
| `/rank` | 批量评估岗位匹配度并生成排序 |
| `/apply` | 评估岗位、生成简历与求职信、复审、编译和核验 |
| `/interview` | 根据岗位和已投材料生成面试准备包 |
| `/outcome` | 记录投递、面试、Offer 或拒绝结果 |
| `/expand` | 从已提供的公开资料中补充技能证据 |
| `/upskill` | 分析技能差距并生成学习计划 |
| `/add-template` | 注册自定义 LaTeX 简历或求职信模板 |
| `/add-portal` | 为新的公开招聘网站生成搜索适配器 |
| `/reset` | 重置个人资料或项目状态 |

### 网页版能力

网页版采用 FastAPI、SQLite、OpenAI 兼容接口和 Docker Compose，实现：

- 浏览器登录；
- 候选人档案导入、编辑和保存；
- LinkedIn、FreeHire 等公开岗位源搜索；
- 完整岗位描述粘贴与匹配度评估；
- 完整 `/apply` 后台任务；
- 独立 Reviewer 模型复审；
- LaTeX 简历和求职信生成；
- PDF 编译、页数校验和视觉模型检查；
- ATS 文本层与关键词覆盖检查；
- 申请材料、报告和 ZIP 下载；
- 浏览器系统设置和模型连通性测试。

网页版详细说明请阅读：[WEB_APP.zh-CN.md](WEB_APP.zh-CN.md)。

## `/apply` 完整流程

无论通过 Claude Code 还是网页版，核心流程都是：

```text
岗位链接或完整 JD
        ↓
解析公司、岗位、地点、语言和关键词
        ↓
候选人匹配度评估
        ↓
用户确认是否继续
        ↓
生成定制 CV 和求职信初稿
        ↓
独立 Reviewer 复审
        ↓
根据复审意见修订，拒绝虚构内容
        ↓
编译 CV 与求职信 PDF
        ↓
检查 CV 2 页、求职信 1 页
        ↓
PDF 页面视觉检查与自动修复
        ↓
ATS 文本提取、联系方式和关键词检查
        ↓
最终事实、一致性、针对性和质量核验
        ↓
下载 PDF、TeX、JSON、Markdown 和 ZIP
```

项目始终遵循真实性原则：

- 不虚构技能、工作经历、数据成果或公司信息；
- 候选人确实掌握但材料中漏写的关键词可以补充；
- 真正缺失的岗位要求必须保留为差距；
- 公司研究结果必须有可验证来源；
- 无法访问招聘页面时应手动粘贴完整 JD。

## 环境要求

### Claude Code 版本

- Claude Code CLI；
- Python 3.10 或更高版本；
- Bun；
- TeX Live、MiKTeX、MacTeX 或 TinyTeX；
- `lualatex` 和 `xelatex`；
- 可选：Poppler 的 `pdftotext`，用于 ATS 文本层检查。

### 网页版

推荐使用 Docker Desktop。镜像会安装：

- Python 3.11；
- Bun；
- FastAPI 与 Uvicorn；
- TeX Live；
- `lualatex`、`xelatex`；
- moderncv、CJK 和字体相关包；
- Poppler：`pdfinfo`、`pdftoppm`、`pdftotext`；
- Ghostscript。

由于包含完整 TeX 环境，第一次构建镜像会较慢，镜像体积也会较大。

## Windows 快速开始

### 1. 下载代码

```cmd
cd /d "D:\项目\docker"
git clone https://github.com/Hygge8/ai-job-search.git
cd /d "D:\项目\docker\ai-job-search"
```

当前网页版开发位于：

```text
agent/web-ai-mvp
```

切换分支：

```cmd
git fetch origin
git switch agent/web-ai-mvp
git pull origin agent/web-ai-mvp
```

### 2. Claude Code 使用方式

```cmd
claude
```

进入 Claude Code 后执行：

```text
/setup
```

初始化完成后常用命令：

```text
/scrape
/rank
/apply <岗位链接或完整 JD>
/interview
```

### 3. 网页版启动

复制启动配置：

```cmd
copy .env.web.example .env.web
notepad .env.web
```

首次启动只需要先设置网页登录信息：

```env
SERVER_PORT=8000
WEB_USERNAME=admin
WEB_PASSWORD=请修改成至少8位密码
```

模型和 Tavily 配置可以在网页的“系统设置”中填写。

启动：

```cmd
docker compose --env-file .env.web -f docker-compose.web.yml up -d --build
```

查看日志：

```cmd
docker compose --env-file .env.web -f docker-compose.web.yml logs -f app
```

浏览器打开：

```text
http://127.0.0.1:8000
```

停止服务：

```cmd
docker compose --env-file .env.web -f docker-compose.web.yml down
```

## 网页系统设置

登录后打开左侧的 **系统设置**，可以配置：

- OpenAI 兼容接口地址；
- 文本模型名称；
- 视觉模型名称；
- OpenAI API Key；
- 模型请求超时；
- 严格 `/apply` 模式；
- PDF 最大自动修复次数；
- Tavily API Key；
- 是否强制公司研究；
- 管理员用户名和密码。

页面提供：

- 测试文本模型；
- 测试视觉模型；
- 测试 Tavily。

安全规则：

- API Key 和密码只保存在服务端；
- 页面不会回显密钥明文；
- 空白密钥输入表示保留原值；
- 删除密钥需要显式勾选“清除”；
- 设置保存在 `web-data/app.sqlite3`；
- 容器重启后配置仍然存在；
- 修改登录账号或密码后，当前浏览器会切换到新凭据。

## 岗位搜索范围

项目内置或复用的岗位源主要包括：

- LinkedIn 公开岗位；
- FreeHire 技术岗位聚合；
- Jobindex；
- Jobnet；
- Jobdanmark；
- Akademikernes Jobbank。

其中部分平台面向丹麦市场，LinkedIn 和 FreeHire 更适合国际化搜索。

国内平台注意事项：

- BOSS直聘、猎聘、智联招聘、前程无忧等通常需要登录并存在反爬限制；
- 项目不会绕过验证码、登录验证和设备指纹；
- 推荐在浏览器中打开岗位，复制完整 JD，再交给 `/apply` 或网页版分析；
- 只有明确公开且允许访问的网页才适合自动抓取。

## 网页版生成文件

每个任务独立保存在：

```text
web-data/applications/<任务编号>_<公司>_<岗位>/
```

典型输出包括：

```text
job.json
evaluation.json
company_research.json
review.json
revision_notes.json
compile_report.json
visual_report.json
ats_report.json
final_report.json
final_report.md
application_bundle.zip
cv/main_<company>.tex
cv/main_<company>.pdf
cover_letters/cover_<company>_<role>.tex
cover_letters/cover_<company>_<role>.pdf
```

## 严格模式

```env
STRICT_APPLY_MODE=true
```

严格模式最接近 Claude Code `/apply` 的完整要求：

- 缺少 TeX 或 Poppler 命令时停止；
- 视觉模型检查失败时停止；
- CV 不是 2 页时停止；
- 求职信不是 1 页时停止；
- ATS 文本层出现严重问题时停止；
- 最终核验不通过时任务标记为失败，但保留诊断报告和已生成文件。

自动修复次数：

```env
APPLY_MAX_REPAIR_ATTEMPTS=3
```

也可以在网页系统设置中修改。

## 公司研究

项目可以使用岗位页面本身作为研究资料。需要额外搜索公司官网、近期动态、战略项目和团队信息时，可配置 Tavily。

网页中填写 Tavily API Key 后，可以选择：

```text
公司研究可降级
```

或：

```text
公司研究必须成功
```

当强制公司研究开启但 Tavily 未配置或调用失败时，完整 `/apply` 会在前置检查阶段停止，避免虚构公司信息。

## 数据与隐私

项目默认忽略以下敏感内容：

- `.env.web`；
- `web-data/`；
- 本地简历和证书；
- 求职记录；
- 生成的 CV 和求职信；
- SQLite 数据库；
- API Key；
- 个性化候选人档案。

Docker 构建上下文也会排除这些文件，防止把个人数据打进镜像。

网页版使用 HTTP Basic 登录，更适合本机或可信内网。不要直接暴露到公网；需要远程访问时，应增加 HTTPS、反向代理和更强的身份验证。

## 常见问题

### 1. 为什么网页提示 AI 未配置？

打开“系统设置”，填写接口地址、文本模型、视觉模型和 API Key，然后点击模型测试。

### 2. 文本模型和视觉模型可以相同吗？

可以，但该模型必须真正支持图片输入。使用“测试视觉模型”确认。

### 3. 没有 Tavily 能用吗？

可以。关闭“强制公司研究”后，流程会记录为研究降级，不会虚构外部信息。

### 4. 为什么 BOSS 或猎聘链接抓取失败？

这些平台通常需要登录、Cookie、验证码或设备验证。请复制完整岗位描述并粘贴到网页。

### 5. 为什么 Docker 第一次构建很慢？

镜像包含完整 TeX Live、字体和 PDF 工具，下载和安装时间较长。

### 6. 为什么任务显示最终核验失败？

下载 `final_report.json`、`compile_report.json`、`visual_report.json` 和 `ats_report.json` 查看具体原因。

### 7. 配置保存在哪里？

保存在：

```text
web-data/app.sqlite3
```

### 8. 修改管理员密码后需要重启吗？

不需要，保存后立即生效。当前网页会更新本次会话使用的登录凭据。

## 开发与测试

运行源码级测试：

```cmd
python -m unittest discover -s tests -t . -v
```

测试包括：

- Python 源码语法检查；
- 完整 `/apply` 阶段顺序；
- FastAPI 路由和前端调用检查；
- 系统设置路由检查；
- 密钥不回显检查；
- LaTeX 和 Poppler 命令标记检查；
- Git 和 Docker 隐私忽略规则检查。

真实端到端测试仍需要：

- 可用的模型 API；
- 支持图片输入的视觉模型；
- 成功构建 Docker 镜像；
- 实际岗位描述；
- 完整候选人资料。

## 项目结构补充

```text
webapp/
├── main.py                # 原基础 Web API、档案和岗位搜索
├── full_app.py            # 完整 Web 入口与路由组合
├── full_apply.py          # 完整 /apply 后台状态机
├── apply_common.py        # 配置、模型、SQLite 和安全抓取
├── apply_documents.py     # 解析、评估、初稿、复审和修订
├── apply_pdf.py           # LaTeX、PDF、视觉和 ATS 检查
├── settings_service.py    # 服务端设置持久化与动态应用
├── settings_api.py        # 系统设置 API
└── index.html             # 中文网页版界面
```

## 当前开发状态

网页版与中文文档当前位于分支：

```text
agent/web-ai-mvp
```

对应 Draft PR：

```text
#1 web: complete /apply with secure browser settings
```

在 PR 合并前，默认 `master` 分支仍主要是原始 Claude Code 英文版本。