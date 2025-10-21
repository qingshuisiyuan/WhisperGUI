# WhisperGUI
python实现的Whisper的GUI，支持视频、语音文件识别字幕并生成
![image](https://github.com/user-attachments/assets/f7b13ac6-ddcc-4531-8279-1459fd1451f4) 
下面是为该项目 WhisperGUI（repo: qingshuisiyuan/WhisperGUI）撰写的 README 文档范本。你可根据实际需要在 GitHub 仓库中保存为 `README.md` 并做适当调整。

---

# WhisperGUI

> 视频／音频文件识别字幕生成工具（基于 whisper 或 faster‑whisper）
> 开发者：@qingshuisiyuan

---

## 功能简介

* 通过 GUI（基于 Tkinter）选择单个或批量音视频文件（支持多种格式如 `.mp4`、`.aac`、`.wav` 等）。
* 使用 Whisper 模型（可选 openai-whisper 或 faster-whisper）对音频进行识别，生成字幕。
* 支持两种输出格式：

  * **SRT**：带时间轴的字幕文件。
  * **TXT**：纯文本字幕。
* 支持 GPU（CUDA）加速及纯 CPU 模式。
* 支持指定模型文件夹（例如已离线下载的 `.pt` 模型文件），并可从中选择。
* 支持语言选项（Auto 自动识别或手动指定语言代码如 `zh`、`en` 等）。
* 显示识别任务状态、已处理/待处理文件数、估算剩余时间。
* 支持队列文件顺序调整（上移／下移／删除）。

---

## 支持的文件格式

包含但不限于：
`.m4a`, `.mp3`, `.mp4`, `.wav`, `.avi`, `.vob`, `.mov`, `.mkv`,
`.aac`, `.flac`, `.ogg`, `.webm`, `.flv`, `.rmvb`, `.wmv`

---

## 快速开始

### 安装依赖

```bash
pip install -U openai-whisper torch pydub
# 若使用 faster-whisper 模式，则：
# pip install faster-whisper
```

另外请确保系统中已安装 **FFmpeg/ffprobe**：

* Windows：从 ffmpeg.org 下载 zip 包，解压后将 bin 目录添加至 系统 PATH。
* Linux/macOS：可通过 apt, brew 等安装。

---

### 运行程序

1. 下载或克隆本仓库：

   ```bash
   git clone https://github.com/qingshuisiyuan/WhisperGUI.git
   cd WhisperGUI
   ```
2. 打开 `WhisperGUI … .py` 文件（根据版本选择 openai 或 faster）。
3. 运行脚本：

   ```bash
   python WhisperGUI_V1.x.py
   ```
4. 在 GUI 中：

   * 点击「选择文件」或「选择文件夹」导入音视频。
   * 在「语言选项」选择 Auto 或手动语言。
   * 在「选择模型」选择模型（如 base、small、large-v3）或指定模型文件夹。
   * 在「导出格式」选择 SRT 或 TXT。
   * 选择「保存位置」方式：跟随源路径 / 统一输出。
   * 点击「开始识别」。
   * 识别过程中可查看日志区域实时输出。

---

## 示例截图

> （建议添加项目中的实际界面截图，方便用户直观了解）

---

## 高级说明

### 模型文件夹离线使用

如果你已事先下载 `.pt` 模型文件（例如 `large-v3.pt`），可点击「模型文件夹」选择所在目录，然后下拉列表会自动显示该文件名称。选择后程序加载该离线模型，无需重新下载。

### 识别设置说明 (openai-whisper 模式)

```python
result = model.transcribe(
    file,
    language=None if lang_option.lower()=="auto" else lang_option,
    condition_on_previous_text=False,   # 防止重复识别
    word_timestamps=True                 # 保留时间戳，用于生成 SRT
)
```

* `condition_on_previous_text=False` 为关键参数，可有效避免只识别第一句然后重复的问题。
* `word_timestamps=True` 可在 `result["segments"]` 中取出每一句话的起止时间。

### 状态 & ETA 显示

程序会启动后台线程，每 60 秒在日志中输出：

```
状态：正在处理任务数量：1，已处理任务数量：X，待处理任务数量：Y
```

识别完成每个文件后，会输出：

```
⏱ 当前文件用时：…，音频时长：…  
⏳ 预计剩余时间：约 …
```

识别全部完成时，会输出总耗时：

```
🎉 所有文件处理完毕，总耗时：…
```

---

## 常见问题 (FAQ)

**Q：识别结果只有一句话反复出现？**
A：请确保 `condition_on_previous_text=False` 已启用。若仍有问题，尝试切换模型至 small/medium 并确认音频质量。

**Q：没有 GPU 也可以用吗？**
A：可。程序会自动检测 CUDA 可用性。若无 GPU，则退为 CPU 模式，仅速度较慢。

**Q：TXT 输出的文本为何没有标点？**
A：这是 whisper 模型当前版本的限制：TXT 模式输出为连续识别文本，不保证标点完整。建议使用 SRT 获取最佳时间轴 + 字幕体验。

**Q：导出的 SRT 无法与视频同步？**
A：请确保音频文件为原始整段、未剪切且采样率标准。如有偏差，可使用 ffmpeg 预处理音频确保时长与原视频一致。

---

## 许可证 & 致谢

此项目遵循 MIT 许可证。
感谢 OpenAI Whisper 模型及社区贡献者。
如果你喜欢此项目，欢迎 ⭐ Star 并转发给需要字幕处理的朋友！

---

## 贡献指南

欢迎提交 Issue 或 Pull Request！
建议的贡献流程：

1. Fork 本仓库。
2. 创建 feature 分支 (`git checkout -b feature-xxx`)。
3. 提交代码与测试。
4. 提交 PR 并描述改动。

---

希望这个 README.md 能帮助用户快速上手，并对项目功能、使用方式、注意事项有清晰了解。你如果需要我进一步撰写项目示例截图、视频演示链接、或详细代码注释说明，我也可以帮你。
