# AI Job Search 网页版中文部署与使用说明

[English](WEB_APP.md) | **简体中文**

本文档说明 `agent/web-ai-mvp` 分支提供的网页版功能、安装方法、系统设置、完整 `/apply` 流程、生成文件和常见故障。

## 1. 网页版定位

网页版是在原 Claude Code 求职工作流之外增加的可选入口，不会删除或替换原有命令。

两种使用方式可以并存：

```text
Claude Code：/setup、/scrape、/apply、/interview
网页版：档案管理、岗位搜索、完整 /apply、历史记录、系统设置
```

网页版技术栈：

- FastAPI；
- Uvicorn；
- SQLite；
- OpenAI 兼容 API；
- Docker Compose；
- Bun 岗位搜索工具；
- TeX Live；
- Poppler；
- Ghostscript。

## 2. 网页功能

左侧菜单包括：

### 候选人档案

- 导入 `/setup` 生成的本地候选人档案；
- 直接编辑 Markdown 格式资料；
- 保存到 SQLite；
- 后续所有岗位评估和材料生成都会使用该档案。

### 岗位搜索

- 调用仓库内现有 LinkedIn 和 FreeHire 搜索工具；
- 按关键词、地点和发布时间搜索；
- 合并和去重结果；
- 将岗位信息带入完整 `/apply` 页面。

### 完整 `/apply`

- 输入公司、岗位、部门、地点；
- 粘贴完整 JD；
- 可选填写公开岗位链接；
- 先进行匹配度评估；
- 必须由用户确认后才生成申请材料；
- 实时展示后台执行步骤；
- 完成后下载 PDF、TeX、报告和 ZIP。

### 历史记录

- 查看岗位搜索记录；
- 查看匹配度评估记录；
- 查看已有 AI 生成记录。

### 系统设置

- 配置 OpenAI 兼容接口；
- 配置文本模型和视觉模型；
- 保存 OpenAI API Key；
- 配置 Tavily；
- 开关严格模式；
- 修改自动修复次数；
- 修改管理员账号密码；
- 测试文本、视觉和 Tavily 连通性。

## 3. 完整 `/apply` 执行顺序

网页版后台严格按照以下顺序执行：

1. 解析岗位信息；
2. 提取必需和优先关键词；
3. 评估技能、经验、行为风格、地点和薪资匹配；
4. 等待用户确认；
5. 生成英文 CV 和岗位语言对应的求职信；
6. 研究公司、团队和相关动态；
7. 独立 Reviewer 复审；
8. 根据复审意见修订；
9. 使用 `lualatex` 编译 CV；
10. 使用 `xelatex` 编译求职信；
11. 强制检查 CV 为 2 页；
12. 强制检查求职信为 1 页；
13. 将 PDF 页面渲染为 PNG；
14. 使用视觉模型检查遮挡、截断、孤立标题、留白和签名；
15. 在限定次数内自动修复并重新编译；
16. 使用 `pdftotext -layout` 提取 ATS 文本层；
17. 检查联系方式、乱码、阅读顺序、日期和关键词；
18. 只补充候选人真实掌握但材料漏写的关键词；
19. 执行最终事实、针对性、一致性、质量、PDF 和 ATS 核验；
20. 生成下载包。

## 4. Windows Docker 安装

### 4.1 切换到网页版分支

```cmd
cd /d "D:\项目\docker\ai-job-search"
git fetch origin
git switch agent/web-ai-mvp
git pull origin agent/web-ai-mvp
```

### 4.2 创建启动配置

```cmd
copy .env.web.example .env.web
notepad .env.web
```

首次只需要填写：

```env
SERVER_PORT=8000
WEB_USERNAME=admin
WEB_PASSWORD=请修改成至少8位密码
```

模型设置可以启动后在网页中填写。

### 4.3 构建和启动

```cmd
docker compose --env-file .env.web -f docker-compose.web.yml up -d --build
```

第一次构建会安装 TeX Live、字体和 PDF 工具，耗时较长。

### 4.4 查看状态

```cmd
docker compose --env-file .env.web -f docker-compose.web.yml ps
```

查看日志：

```cmd
docker compose --env-file .env.web -f docker-compose.web.yml logs -f app
```

### 4.5 访问网页

```text
http://127.0.0.1:8000
```

### 4.6 停止服务

```cmd
docker compose --env-file .env.web -f docker-compose.web.yml down
```

## 5. 系统设置填写说明

### OpenAI 兼容接口地址

官方 OpenAI 可以填写：

```text
https://api.openai.com/v1
```

部分兼容服务有自己的地址，应以服务商文档为准。

留空时使用 SDK 默认地址。

### 文本模型

用于：

- 岗位解析；
- 匹配度评估；
- CV 和求职信生成；
- Reviewer 复审；
- 修订；
- ATS 关键词分析；
- 最终核验。

### 视觉模型

用于读取 PDF 渲染出的页面图片并检查排版。模型必须支持图片输入。

可以与文本模型相同，但必须点击“测试视觉模型”确认。

### OpenAI API Key

- 输入框为空：保留已保存密钥；
- 输入新值：替换旧密钥；
- 勾选清除：删除密钥；
- 页面不会显示旧密钥明文。

### 请求超时

允许范围：

```text
10 到 600 秒
```

完整简历生成和视觉检查可能耗时较长，推荐 120 到 300 秒。

### 严格模式

开启后：

- TeX 工具缺失会失败；
- Poppler 工具缺失会失败；
- 视觉模型检查失败会失败；
- CV 不是 2 页会失败；
- 求职信不是 1 页会失败；
- ATS 严重错误会失败；
- 最终核验不通过会失败。

推荐保持开启。

### 自动修复次数

允许范围：

```text
1 到 10 次
```

推荐：

```text
3 次
```

### Tavily API Key

用于补充公司官网、团队、新闻、战略和近期项目研究。

未配置时仍可以使用岗位页面本身，但外部公司研究会降级。

### 强制公司研究

关闭：

- Tavily 缺失时继续；
- 报告中明确标记降级；
- 不虚构公司信息。

开启：

- Tavily 未配置或请求失败时停止任务。

### 管理员账号密码

- 用户名至少 3 个字符；
- 密码至少 8 个字符；
- 修改后立即生效；
- 不需要重启容器。

## 6. 配置优先级

配置来源按以下优先级生效：

```text
网页保存到 SQLite 的设置
        ↓
.env.web 环境变量
        ↓
代码默认值
```

网页设置保存在：

```text
web-data/app.sqlite3
```

数据库目录通过 Docker volume 挂载，因此容器重建后仍然保留。

## 7. 模型连通测试

### 测试文本模型

会发送一个最小文本请求，返回模型名、响应内容和延迟。

### 测试视觉模型

会发送一个 1×1 PNG 图片，验证模型是否接受 `image_url` 类型输入。

仅文本模型即使名称可调用，也可能不支持此测试。

### 测试 Tavily

会执行一次最小公开搜索，返回结果数量和延迟。

测试错误会在服务端做密钥脱敏，避免把 API Key 返回到网页。

## 8. 使用完整 `/apply`

### 8.1 准备候选人档案

打开“候选人档案”，点击：

```text
从 Claude Code 档案导入
```

也可以直接粘贴完整档案并保存。

### 8.2 填写岗位信息

建议至少填写：

- 公司；
- 岗位；
- 地点；
- 完整 JD。

公开岗位链接是可选项。

对于 BOSS直聘、猎聘、智联招聘等平台，推荐直接复制完整 JD，不要只填写链接。

### 8.3 评估

点击：

```text
第 1 步：评估匹配度
```

系统返回：

- 技能匹配；
- 经验匹配；
- 行为和文化匹配；
- 地点匹配；
- 可选薪资参考；
- 关键词覆盖；
- 总分；
- 推荐结论；
- 真实差距。

### 8.4 确认继续

确认评估结果后点击：

```text
确认并执行完整 /apply
```

后台开始生成材料。

### 8.5 查看进度

页面每 2 秒轮询一次任务状态，并显示：

```text
解析
评估
确认
初稿
公司研究
Reviewer
修订
编译
视觉检查
ATS
最终核验
```

### 8.6 下载结果

任务完成后可单独下载文件，也可以下载：

```text
application_bundle.zip
```

## 9. 文件输出位置

```text
web-data/applications/<id>_<company>_<role>/
```

主要文件：

```text
job.json                    岗位解析结果
evaluation.json             匹配度评估
company_research.json       公司研究
review.json                 Reviewer 意见
revision_notes.json         修订记录
compile_report.json         编译与自动修复报告
visual_report.json          PDF 视觉检查
ats_report.json             ATS 检查
final_report.json           最终结构化核验
final_report.md             最终可读报告
application_bundle.zip      完整下载包
cv/*.tex                    CV LaTeX
cv/*.pdf                    CV PDF
cover_letters/*.tex         求职信 LaTeX
cover_letters/*.pdf         求职信 PDF
```

## 10. 国内招聘网站使用建议

项目不会执行以下行为：

- 自动登录招聘账号；
- 绕过短信验证码；
- 绕过滑块或图形验证码；
- 模拟设备指纹；
- 绕过访问频率限制；
- 自动向招聘方发消息；
- 自动批量投递。

推荐流程：

```text
在 BOSS/猎聘浏览器中找到岗位
        ↓
复制公司、岗位和完整 JD
        ↓
粘贴到网页完整 /apply
        ↓
评估、生成和核验材料
        ↓
人工确认后投递
```

## 11. 常见故障

### 登录失败

检查 `.env.web` 中：

```env
WEB_USERNAME=
WEB_PASSWORD=
```

如果网页中修改过登录信息，应使用 SQLite 中最新保存的账号密码。

### 页面提示 AI 未配置

进入系统设置，填写：

```text
API Key
接口地址
文本模型
视觉模型
```

保存后先执行模型测试。

### 文本模型测试失败

检查：

- API Key 是否有效；
- Base URL 是否包含正确 `/v1` 路径；
- 模型名称是否由服务商提供；
- 服务商是否兼容 Chat Completions；
- 网络代理是否允许容器访问外网。

### 视觉模型测试失败

可能原因：

- 模型不支持图片；
- 接口兼容文本但不兼容多模态格式；
- 服务商使用了不同的图片字段规范。

请换用明确支持 OpenAI `image_url` 消息格式的模型。

### Tavily 测试失败

检查：

- Key 是否正确；
- 是否存在余额或调用额度；
- Docker 网络是否可以访问 Tavily。

### 岗位 URL 无法抓取

原因可能包括：

- 需要登录；
- Cloudflare；
- 验证码；
- Cookie 检查；
- 设备验证；
- 网站禁止自动访问。

处理方法：复制完整 JD。

### LaTeX 编译失败

查看任务目录中的报告和日志摘要。常见原因：

- 模型输出了未转义的 `_`、`&`、`%`；
- 中文求职信缺少 CJK 字体；
- 模型改变了模板结构；
- 内容过长；
- TeX 包未正确安装。

### CV 不是 2 页

系统会自动修复。达到最大次数仍失败时，任务保留所有诊断文件，需人工压缩或调整内容。

### 求职信超过 1 页

通常需要删除重复内容、降低低相关信息或缩短公司介绍，不能通过极端缩小字体解决。

### ATS 检查失败

重点查看：

- 邮箱和手机号是否为可提取文本；
- 是否出现 `(cid:NNN)`；
- 是否出现 `�`；
- 阅读顺序是否混乱；
- 日期是否丢失；
- 必需关键词是否缺失。

## 12. 数据安全

### 不会提交到 Git 的数据

- `.env.web`；
- `web-data/`；
- 本地简历；
- 证书；
- 个人档案；
- 求职跟踪记录；
- 生成的 PDF 和 TeX；
- API Key。

### 不会进入 Docker 镜像的数据

`.dockerignore` 排除了个人资料、密钥、SQLite 数据和生成材料。

### 公网部署风险

当前认证方式是 HTTP Basic，更适合本机和可信内网。公网部署至少应增加：

- HTTPS；
- Nginx、Caddy 或其他反向代理；
- 更强身份验证；
- 访问控制；
- 日志脱敏；
- 定期备份和密钥轮换。

## 13. 本地开发

不用 Docker 时，需要自行安装 Python、Bun、TeX 和 Poppler。

Windows：

```cmd
cd /d "D:\项目\docker\ai-job-search"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-web.txt
python -m webapp.full_app
```

浏览器访问：

```text
http://127.0.0.1:8000
```

## 14. 测试

```cmd
python -m unittest discover -s tests -t . -v
```

源码测试不会替代真实端到端测试。正式使用前还应实际验证：

- Docker 构建；
- 文本模型；
- 视觉模型；
- LaTeX 编译；
- PDF 页数；
- ATS 提取；
- 下载文件；
- 容器重启后的设置保留。

## 15. 当前状态

完整网页版和本文档当前位于：

```text
分支：agent/web-ai-mvp
Draft PR：#1
```

在 PR 合并前，默认 `master` 分支不会自动包含这些网页版文件和中文文档。