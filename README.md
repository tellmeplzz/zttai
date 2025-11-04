# ZTT 工业智能体一体机 Demo

本项目是基于 **Streamlit + LangChain** 的多智能体工业场景示例，涵盖 OCR 文档识别、运维问答 Agent、人机协同标注与数智人语音播报等模块，支持离线运行和在线模型切换。所有界面文案均为中文，一键运行 `streamlit run streamlit_app.py` 即可体验。

![界面占位图](assets/ai_bg.png)

---

## 功能亮点

- 📄 **OCR 文档管理**：批量上传 PDF/图片，使用 PaddleOCR 或 Tesseract 识别，自动切块并写入 SQLite + Chroma。
- 🛠️ **运维助手 Agent**：结合会话记忆与知识库的 RAG 问答，支持反馈闭环（点赞/点踩、是否解决）。
- 🧑‍🏭 **人机协同标注**：实时监听小模型二分类输出，告警样本进入“待标注 → 待审核 → 已归档”流程，可下载原始片段并导出 CSV。
- 🤖 **数智人播报**：悬浮语音助手，可选择 edge-tts / pyttsx3 播报最新回复。
- 🔀 **智能路由**：自然语言意图识别，自动切换到对应智能体工作流。

---

## 标注工作台流程说明

1. **信号监听**：`MonitorService.stream_signal` 模拟小模型输出概率，当概率超过阈值即视为异常。
2. **异常入队**：异常片段会生成波形缩略图与原始 CSV，文件保存在 `data/monitor_artifacts/`，同时写入 `hit_queue` 表并标记状态为“待标注”。
3. **人工标注**：在 Streamlit 页面填写责任人、异常类型、原因等信息，并选择“待审核”或“已归档”状态。
4. **复核记录**：若填写复核人则会记录复核时间，所有操作都会同步到 SQLite 的 `annotations` 表，可随时导出 CSV。
5. **档案管理**：通过队列筛选查看不同状态的数据，完成后的样本可一键下载原始片段或清空目录。

> 若接入真实小模型，仅需在 `MonitorService` 中替换 `stream_signal` 的数据来源与判定逻辑。

---

## 目录结构

```text
.
├── streamlit_app.py                # 主入口
├── config/settings.py              # 配置中心，可切换 LLM/向量库/TTS
├── agents/                         # 多智能体实现
│   ├── __init__.py
│   ├── llm_provider.py             # LLM 适配器
│   └── ops_agent.py                # 运维助手
├── services/                       # 各类服务组件
│   ├── __init__.py
│   ├── feedback_service.py
│   ├── monitor_service.py
│   ├── ocr_service.py
│   ├── rag_service.py
│   ├── router_service.py
│   ├── session_service.py
│   ├── signal_service.py
│   ├── storage.py
│   └── tts_service.py
├── ui/                             # 前端组件
│   ├── __init__.py
│   ├── components.py
│   ├── layout.py
│   └── styles.py
├── assets/                         # 占位 Logo 与背景（运行时自动生成真实图片）
│   ├── generate_assets.py
│   ├── ztt_logo.png                # 文本占位符，首次运行写入 PNG
│   ├── ai_bg.png                   # 文本占位符，首次运行写入 PNG
│   └── ai_bg.jpg                   # 文本占位符，可自行替换 JPG
├── data/
│   ├── docs/设备维护手册_示例.pdf
│   ├── telemetry_samples.json
│   ├── signals/sample1.csv
│   └── monitor_artifacts/README.md   # 运行后生成缩略图与片段的说明
├── tests/smoke_test.py             # 冒烟测试
└── requirements.txt
```

---

## 安装与运行

### 1. 准备 Python 环境

```bash
python3.11 -m venv .venv
source .venv/bin/activate  # Windows 请使用 .venv\Scripts\activate
pip install -r requirements.txt
```

> **国内镜像建议**：可在 `pip` 命令后添加 `-i https://pypi.tuna.tsinghua.edu.cn/simple`。

### 2. OCR 依赖说明

- **推荐**：安装 [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)。如安装时间较长，可只安装 `paddleocr` Python 包并根据官方文档配置模型目录。
- **备选**：Tesseract OCR。
  - macOS：`brew install tesseract`
  - Ubuntu/Debian：`sudo apt-get install tesseract-ocr`
  - Windows：下载官方安装包并将安装路径加入 `PATH`
- **PDF 解析**：推荐安装 `pymupdf` 获得更快的页面渲染；若缺失会自动回退到纯 Python 的 `pypdf` 提取文本。
- 若以上都未安装，系统会尝试使用 PDF 文本抽取作为兜底。

### 3. Sentence-Transformers 模型下载

首次运行会自动下载 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` 模型，若网络受限可提前手动下载并配置 `HF_HOME` 或使用离线模型权重。

### 4. 配置 LLM / 向量库 / TTS

在项目根目录创建 `.streamlit/secrets.toml`，填入如下示例（按需替换）：

```toml
LLM_PROVIDER = "OLLAMA"       # 可选：OPENAI / DEEPSEEK / OLLAMA
LLM_MODEL = "llama3"
EMBEDDING_PROVIDER = "sentence-transformers"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
VECTOR_BACKEND = "chromadb"
VECTOR_PATH = "data/vector_store"
SQLITE_PATH = "data/ztt_agent.db"
TTS_PROVIDER = "pyttsx3"      # 可切换 edge-tts
TTS_VOICE = "default"
TTS_RATE = 180
OPENAI_API_KEY = "sk-..."
DEEPSEEK_API_KEY = "ds-..."
OLLAMA_BASE_URL = "http://localhost:11434"
```

所有敏感信息仅从 `st.secrets` 读取，默认使用 DemoLLM 回退，无需外网亦可体验。

### 5. 一键启动

```bash
streamlit run streamlit_app.py
```

首次运行会自动创建 SQLite、向量库及示例数据。界面左上角可切换浅色/深色主题，右下角悬浮窗口可朗读最新回复。

---

## 常见问题 FAQ

1. **显存不足或模型加载缓慢？**
   - 可将 `LLM_PROVIDER` 调整为 `OLLAMA` 并选择轻量模型，或使用默认 DemoLLM 离线模式。
2. **无法下载嵌入模型？**
   - 在无网络环境下，系统会自动退化为 `FakeEmbeddings`，可用于功能演示但相似度较弱。
3. **中文 OCR 识别不准？**
   - PaddleOCR 支持 GPU 加速与中英文混排，建议启用；Tesseract 可通过自定义语言包 `chi_sim`、增大 DPI 改善效果。
4. **PyMuPDF 未安装如何处理？**
   - `requirements.txt` 已包含 `pypdf`，即使缺少 PyMuPDF 也能完成文本索引；如需 PDF 转图片 OCR，请根据提示额外安装 `pymupdf`。
5. **TTS 无法播放？**
   - `pyttsx3` 依赖系统语音引擎，Linux 需安装 `espeak`；edge-tts 需网络访问微软服务。
6. **向量库体积增长？**
   - 定期清理 `data/vector_store` 并重新索引；支持切换为 FAISS/其他向量库，可在 `config/settings.py` 扩展。

---

## 手工验收清单

- [ ] 能成功启动 Streamlit 页面，并显示自定义主题与 Logo。
- [ ] 在“📄 文档管理”上传示例 PDF，可完成 OCR、切块与索引。
- [ ] 在“🛠️ 运维助手”发起提问，得到回复并显示引用来源卡片。
- [ ] 点赞/点踩后，SQLite `feedback` 表新增记录。
- [ ] 在“🧑‍🏭 标注工作台”运行一次异常检测，生成波形缩略图并提交标注。
- [ ] 右下角“数智助手”可成功朗读最新回复。

---

## 演示素材占位

- 演示动图：`docs/demo.gif`（请录制后替换）
- 截图：`docs/screenshot.png`

欢迎根据企业实际需求进行二次开发与部署！

---

## 占位/空文件说明

仓库中 **不存在真正意义上的 0 字节空文件**。当文档中提到“占位”时，表示这些素材用于提供默认示例，便于直接运行：

- `assets/ztt_logo.png`、`assets/ai_bg.jpg`/`ai_bg.png`：为避免提交二进制资源影响 PR 生成，文件内容以中文说明占位；`assets/generate_assets.py` 会在首次运行时自动生成可视化 PNG，若需要 JPG 可自行替换。
- `data/docs/设备维护手册_示例.pdf`：包含若干段落示例文本，便于 OCR/RAG 流程体验。
- `data/signals/sample1.csv`、`data/telemetry_samples.json`：提供最小化监控与标注样例数据。
- `assets/generated/`：运行程序后自动创建，内含可直接使用的 PNG 素材，默认被 `.gitignore` 忽略。

若需要仅保留目录结构，可自行将文件替换为企业内部素材，或使用 `.gitkeep` 之类的方式显式保留空目录。
