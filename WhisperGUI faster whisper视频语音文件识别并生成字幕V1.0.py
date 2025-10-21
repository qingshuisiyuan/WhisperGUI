# WhisperGUI 带超详细注释的完整脚本（注意：这是整个可运行文件）
# 目的：对选中的音视频文件使用 faster-whisper 转写并输出 SRT/TXT 字幕文件
# 说明：如果要运行，请确保已安装：faster-whisper、torch、ffmpeg（系统命令可用）、psutil（可选）等。

import os
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk
import time
from datetime import datetime
from faster_whisper import WhisperModel   # faster-whisper 的模型接口
import torch                              # 用于判断是否有 CUDA / GPU
import subprocess                         # 用于调用 ffmpeg / ffprobe
import json                               # 解析 ffprobe 的 JSON 输出
import psutil                             # （可选）用于查看系统/进程内存/CPU 信息

# ---------------------- 全局变量 ----------------------
# 下面这些变量用于保存 GUI 状态、选中文件列表、处理进度等。
selected_files = []      # 列表：累积的音视频文件路径（用户选择）
current_file_index = 0   # 当前已处理的文件索引（用于进度/状态显示）
total_files = 0          # 总任务数量（len(selected_files)）
processing = False       # 标识：程序是否正在处理任务
supported_extensions = ( # 支持的音视频文件扩展名（便于从文件夹批量加入）
    ".m4a", ".mp3", ".mp4", ".wav", ".avi", ".vob",
    ".mov", ".mkv", ".aac", ".flac", ".ogg", ".webm",
    ".flv", ".rmvb", ".wmv"
)

# ---------------------- Tkinter 初始化 ----------------------
# 创建主窗口，并设置标题与默认大小
root = tk.Tk()
root.title("WhisperGUI faster whisper视频/语音文件识别并生成字幕")
root.geometry("900x600")  # 设置窗口大小（宽900，高600）

# 使用 ttk 的主题，让界面更现代一点（Windows下 "vista" 主题通常可用）
style = ttk.Style()
# 可选主题：clam, alt, default, classic, winnative, xpnative, vista
style.theme_use("vista")

# ---------------------- Tkinter 变量 ----------------------
# 下面定义的一批 tk.Variable 用于和界面控件绑定，实时获取/设置用户输入值
lang_var = tk.StringVar(root, value="Auto")   # 语言选项：Auto 或指定语言（如 "zh", "en"）
model_var = tk.StringVar(root)                # 模型名称（faster-whisper 模型名或本地目录名称）
suffix_var = tk.StringVar(root, value="")     # 输出文件名后缀（可选）
export_format_var = tk.StringVar(root, value="SRT")  # 导出格式：SRT 或 TXT
output_folder_var = tk.StringVar(root, value="")     # 统一输出文件夹（当用户选择统一存放时使用）
model_folder_var = tk.StringVar(root, value="")      # 本地模型根目录（如果使用本地模型）
output_mode_var = tk.IntVar(root, value=1)     # 保存方式：1 = 跟随源文件路径，2 = 统一存放到指定文件夹

# ---------------------- 工具函数（format、日志、UI更新） ----------------------

def format_timestamp(seconds):
    """
    将秒数转换为 SRT 时间戳格式：HH:MM:SS,mmm
    注意输入 seconds 可以是 float（带小数），函数会把毫秒部分保留三位。
    """
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{millis:03}"


def log(msg):
    """
    在日志窗口（ScrolledText）中追加一行日志，前缀带本地时间（时:分:秒）
    通过 state 切换实现只读效果，并调用 update_idletasks 确保 UI 及时刷新。
    """
    timestamp = datetime.now().strftime("[%H:%M:%S] ")
    logging_text.config(state=tk.NORMAL)
    logging_text.insert(tk.END, timestamp + msg + "\n")
    logging_text.see(tk.END)            # 自动滚动到末尾
    logging_text.update_idletasks()     # 立即刷新 UI
    logging_text.config(state=tk.DISABLED)


def update_files_text():
    """
    将 selected_files 列表内容刷新显示到文件列表的 Text 控件中。
    此函数会把 Text 设为可编辑、更新文本、再设回只读，以避免用户误输入。
    """
    files_text.config(state=tk.NORMAL)
    files_text.delete("1.0", tk.END)
    for f in selected_files:
        files_text.insert(tk.END, f + "\n")
    files_text.config(state=tk.DISABLED)

# ---------------------- 文件选择/管理函数 ----------------------

def select_files():
    """
    弹出文件选择对话框（支持多选），将用户选择的文件路径加入 selected_files（去重）。
    文件类型筛选器与 supported_extensions 保持一致。
    """
    filenames = filedialog.askopenfilenames(
        title="选择音视频文件",
        filetypes=[("Media Files", "*.m4a *.mp3 *.mp4 *.wav *.avi *.vob *.mov *.mkv *.aac *.flac *.ogg *.webm *.flv *.rmvb *.wmv"),
                   ("All Files", "*.*")]
    )
    if filenames:
        for f in filenames:
            if f not in selected_files:
                selected_files.append(f)
        update_files_text()
        log(f"已选择 {len(filenames)} 个文件，当前总计 {len(selected_files)} 个文件。")


def select_folder():
    """
    弹出文件夹选择对话框，递归扫描文件夹内所有文件，凡是后缀属于 supported_extensions 的就加入 selected_files。
    用于批量导入。
    """
    folder = filedialog.askdirectory(title="选择音视频文件夹")
    if folder:
        for root_dir, dirs, files in os.walk(folder):
            for file in files:
                if file.lower().endswith(supported_extensions):
                    full_path = os.path.join(root_dir, file)
                    if full_path not in selected_files:
                        selected_files.append(full_path)
        update_files_text()
        log(f"从文件夹 {folder} 导入完成，共导入 {len(selected_files)} 个文件。")


def clear_files():
    """清空选中文件列表并刷新 UI。"""
    selected_files.clear()
    update_files_text()
    log("已清空选择的文件。")

# ---------------------- 文件列表控件辅助（上移/下移/删除） ----------------------

def get_selected_line_indices():
    """
    辅助：从 Text 控件中获取当前选中的文本行（返回 start_line, end_line，0 基）
    如果没有选区则返回 (None, None)
    """
    try:
        sel_first = files_text.index("sel.first")
        sel_last = files_text.index("sel.last")
        start_line = int(sel_first.split('.')[0]) - 1
        end_line = int(sel_last.split('.')[0]) - 1
        return start_line, end_line
    except tk.TclError:
        return None, None


def move_up():
    """把选中的行（在 selected_files 中对应的项）上移一行（如果可能）。"""
    start_line, end_line = get_selected_line_indices()
    if start_line is None:
        log("请先选择要上移的文件。")
        return
    if start_line <= 0:
        log("已到顶部，无法上移。")
        return
    block = selected_files[start_line:end_line + 1]
    del selected_files[start_line:end_line + 1]
    new_index = start_line - 1
    for i, item in enumerate(block):
        selected_files.insert(new_index + i, item)
    update_files_text()


def move_down():
    """把选中的行下移一行（如果可能）。"""
    start_line, end_line = get_selected_line_indices()
    if start_line is None:
        log("请先选择要下移的文件。")
        return
    if end_line >= len(selected_files) - 1:
        log("已到底部，无法下移。")
        return
    block = selected_files[start_line:end_line + 1]
    del selected_files[start_line:end_line + 1]
    new_index = start_line + 1
    for i, item in enumerate(block):
        selected_files.insert(new_index + i, item)
    update_files_text()


def delete_selected():
    """删除 selected_files 中被选中的索引区间。"""
    start_line, end_line = get_selected_line_indices()
    if start_line is None:
        log("请先选择要删除的文件。")
        return
    del selected_files[start_line:end_line + 1]
    update_files_text()
    log("已删除选中的文件。")

# ---------------------- 输出路径/模型选择 ----------------------

def select_output_folder():
    """弹出对话框选择输出文件夹（当用户选择“统一输出到指定文件夹”时使用）。"""
    folder = filedialog.askdirectory(title="选择输出文件夹")
    if folder:
        output_folder_var.set(folder)
        output_folder_entry.config(state=tk.NORMAL)
        output_folder_entry.delete(0, tk.END)
        output_folder_entry.insert(0, folder)
    log(f"已选择输出文件夹：{folder}")


def select_model_folder():
    """
    选择 Faster-Whisper 本地模型根目录（脚本会尝试查找该目录下具有 snapshots 子目录的模型子文件夹）
    然后把能用的模型子目录名放进模型下拉框（model_menu）。
    """
    folder = filedialog.askdirectory(title="选择模型文件夹")
    if folder:
        model_folder_var.set(folder)
        model_folder_entry.config(state=tk.NORMAL)
        model_folder_entry.delete(0, tk.END)
        model_folder_entry.insert(0, folder)

        model_dirs = []
        for d in os.listdir(folder):
            full_path = os.path.join(folder, d)
            if os.path.isdir(full_path):
                snapshots_path = os.path.join(full_path, "snapshots")
                if os.path.exists(snapshots_path):
                    model_dirs.append(d)

        if model_dirs:
            model_dirs.sort()
            model_menu['values'] = model_dirs
            model_menu.set(model_dirs[0])
            log(f"导入模型文件夹成功：{folder}，可用模型：{', '.join(model_dirs)}")
        else:
            log("所选文件夹中没有找到任何有效 Faster-Whisper 模型（包含 snapshots）！")


def update_output_folder_state():
    """
    根据 output_mode_var（1 或 2）更新输出路径输入框的可编辑状态：
      - 1：禁用输出路径输入（每个字幕放在源文件同目录）
      - 2：启用输出路径输入（用户需选择一个统一的输出文件夹）
    """
    if output_mode_var.get() == 2:
        output_folder_entry.config(state=tk.NORMAL)
        select_output_folder_button.config(state=tk.NORMAL)
    else:
        output_folder_entry.config(state=tk.DISABLED)
        select_output_folder_button.config(state=tk.DISABLED)
    log("已更新输出文件夹控件状态。")

# ---------------------- 控件启用/禁用（处理时保护 UI） ----------------------

def disable_all_controls():
    """
    任务开始时禁用所有会干扰状态的控件（避免用户在处理中修改设置）。
    这里列举并禁用主要的按钮和输入框。
    """
    start_button.config(state=tk.DISABLED)
    select_files_button.config(state=tk.DISABLED)
    select_folder_button.config(state=tk.DISABLED)
    clear_files_button.config(state=tk.DISABLED)
    output_folder_entry.config(state=tk.DISABLED)
    select_output_folder_button.config(state=tk.DISABLED)
    select_model_folder_button.config(state=tk.DISABLED)
    lang_menu.config(state=tk.DISABLED)
    model_menu.config(state=tk.DISABLED)
    suffix_entry.config(state=tk.DISABLED)
    model_folder_entry.config(state=tk.DISABLED)
    files_text.config(state=tk.DISABLED)
    up_btn.config(state=tk.DISABLED)
    down_btn.config(state=tk.DISABLED)
    del_btn.config(state=tk.DISABLED)
    export_format_menu.config(state=tk.DISABLED)
    radio1.config(state=tk.DISABLED)
    radio2.config(state=tk.DISABLED)


def enable_all_controls():
    """
    任务结束后恢复控件可用性；根据保存方式恢复输出路径状态。
    """
    start_button.config(state=tk.NORMAL)
    select_files_button.config(state=tk.NORMAL)
    select_folder_button.config(state=tk.NORMAL)
    clear_files_button.config(state=tk.NORMAL)
    select_model_folder_button.config(state=tk.NORMAL)
    lang_menu.config(state=tk.NORMAL)
    model_menu.config(state=tk.NORMAL)
    suffix_entry.config(state=tk.NORMAL)
    model_folder_entry.config(state=tk.NORMAL)
    files_text.config(state=tk.NORMAL)
    up_btn.config(state=tk.NORMAL)
    down_btn.config(state=tk.NORMAL)
    del_btn.config(state=tk.NORMAL)
    export_format_menu.config(state="readonly")
    radio1.config(state=tk.NORMAL)
    radio2.config(state=tk.NORMAL)
    update_output_folder_state()

# ---------------------- 其他辅助函数（时间、文件大小、时长） ----------------------

def format_hms(seconds):
    """
    将秒转换为更易读的字符串，例如：
      - 3661 -> "1小时1分1秒"
      - 125  -> "2分5秒"
      - 9    -> "9秒"
    """
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}小时{m}分{s}秒"
    elif m > 0:
        return f"{m}分{s}秒"
    else:
        return f"{s}秒"


def get_total_size_mb(file_list):
    """
    计算 file_list 中所有文件的总大小（以 MB 为单位）。
    用于估算处理速度 / 进度（可选）。
    """
    total_bytes = sum(os.path.getsize(f) for f in file_list if os.path.exists(f))
    return total_bytes / (1024 * 1024)


def get_audio_duration(file_path):
    """
    使用 ffprobe（ffmpeg 的子工具）以 JSON 模式查询音频/视频文件的时长（秒）。
    优点：不需要把整个文件加载到内存，快速且准确。
    返回 float 时长（秒），出错则返回 0。
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception:
        return 0

# ---------------------- 状态刷新线程 ----------------------

def update_status(stop_event, log_func, total_files, processed_files_func):
    """
    后台线程：每60秒刷新一次状态（写入日志窗口）。
    参数：
      - stop_event：threading.Event，用于停止循环
      - log_func：用于写日志的函数（可传 log）
      - total_files：任务总数
      - processed_files_func：返回已处理文件数的函数（通常 lambda: current_file_index）
    说明：这个线程只负责周期性写状态日志，不参与转写工作。
    """
    while not stop_event.is_set():
        try:
            processed = processed_files_func()
            pending = total_files - processed
            log_func(f"状态：正在处理任务数量：1，已处理任务数量：{processed}，待处理任务数量：{pending}")
        except Exception as e:
            log_func(f"状态刷新出错：{e}")
        # sleep 分段进行可以更快响应 stop_event
        for _ in range(60):
            if stop_event.is_set():
                break
            time.sleep(1)

# ---------------------- 分段转写函数（避免一次加载长音频导致内存暴涨） ----------------------

def transcribe_in_chunks(model, input_file, lang_option, chunk_duration=60):
    """
    将长音频按若干 chunk（默认 60 秒）分割，每个 chunk 单独用 model.transcribe 转写。
    主要目的是避免把整个长音频一次性加载到内存或一次性让模型处理导致内存/显存占用异常。
    使用 ffmpeg 截取片段到临时 wav 文件，识别后删除临时文件。
    参数：
      - model：WhisperModel 实例（已加载）
      - input_file：输入文件路径（音频或视频）
      - lang_option：语言参数（"Auto" -> None）
      - chunk_duration：每个片段的持续时间（秒）
    返回：
      - all_segments：合并了所有片段并修正时间戳后的 segments 列表
    注意：
      - chunk_duration 越小，内存压力越小，但识别上下文（跨片段）无法共享，可能略微影响连贯性。
      - 如果你需要跨片段更好的连贯，可考虑 overlap（重叠）策略，但会稍微增加运算量。
    """
    total_duration = get_audio_duration(input_file)
    all_segments = []
    current_start = 0.0
    index = 1

    # 循环直到覆盖整个音频时长
    while current_start < total_duration:
        # 使用 ffmpeg 提取从 current_start 开始，长度为 chunk_duration 的音频片段
        temp_chunk = f"temp_chunk_{index}.wav"  # 临时 wav 文件名（写在当前工作目录）
        cmd = [
            "ffmpeg",
            "-y",                    # 覆盖输出文件（如果存在）
            "-ss", str(current_start),  # 起始时间（秒）
            "-t", str(chunk_duration),   # 持续时长（秒）
            "-i", input_file,        # 输入文件
            "-ac", "1",              # 单声道（1 通道）
            "-ar", "16000",          # 采样率 16kHz（很多 ASR 更稳定）
            temp_chunk,
            "-loglevel", "error"     # 仅在出错时显示 ffmpeg 信息，保持日志清爽
        ]
        # 运行 ffmpeg，提取片段到磁盘（注意：对非常大的文件，磁盘 IO 较大）
        subprocess.run(cmd)

        # 转写这个临时片段
        # 注意：word_timestamps=False（不开启逐词时间戳会更快），vad_filter=False（不做语音活动检测）
        segments, _ = model.transcribe(
            temp_chunk,
            language=None if lang_option.lower() == "auto" else lang_option,
            task="transcribe",
            word_timestamps=False,
            vad_filter=False
        )

        # 转写结果时间戳是相对于 temp_chunk 的（从 0 开始），所以要把每段时间加上 current_start
        for seg in segments:
            seg.start += current_start
            seg.end += current_start
            all_segments.append(seg)

        # 删除临时文件以释放磁盘空间（及时清理）
        try:
            os.remove(temp_chunk)
        except Exception:
            # 如果删除失败也不影响继续处理，只记录日志
            log(f"警告：无法删除临时文件 {temp_chunk}（请手动删除）。")

        # 前进到下一个片段
        current_start += chunk_duration
        index += 1

    return all_segments

# ---------------------- 主处理函数（循环处理 selected_files） ----------------------

def process_files_func():
    """
    主工作流程：
      1. 禁用 UI 控件
      2. 启动后台状态更新线程（每60秒写一次状态）
      3. 加载 faster-whisper 模型（支持加载本地 snapshot 或直接模型名）
      4. 对每个文件执行 transcribe_in_chunks（分片转写）
      5. 把 segments 写入 SRT 或 TXT 文件
      6. 最终恢复 UI
    重要：为了防止 GUI 阻塞，这个函数应在单独线程中运行（start_recognition 已在新线程中启动它）
    """
    global current_file_index, total_files, processing
    disable_all_controls()
    current_file_index = 0
    total_files = len(selected_files)
    processing = True

    # 启动周期性状态刷新线程
    stop_event = threading.Event()
    status_thread = threading.Thread(
        target=update_status,
        args=(stop_event, log, total_files, lambda: current_file_index),
        daemon=True
    )
    status_thread.start()

    # 统计变量（用于估算）
    processed_durations = []
    processing_times = []
    start_overall = time.time()

    try:
        # 读取用户选项：语言、模型名，并判断是否有 CUDA（GPU）
        lang_option = lang_var.get().strip()
        selected_model_name = model_var.get().strip()
        device = "cuda" if torch.cuda.is_available() else "cpu"

        # ========== 加载模型 ==========
        try:
            # 如果用户指定了本地模型文件夹（model_folder_var 非空），尝试从里面加载
            if model_folder_var.get().strip():
                model_base_folder = os.path.join(model_folder_var.get().strip(), selected_model_name)
                snapshots_path = os.path.join(model_base_folder, "snapshots")
                if not os.path.exists(snapshots_path):
                    log(f"错误：模型 {selected_model_name} 没有 snapshots 目录")
                    return

                # 取 snapshots 子目录下的第一个 snapshot（你可以改成选择最新/最大等策略）
                snapshot_dirs = [d for d in os.listdir(snapshots_path) if os.path.isdir(os.path.join(snapshots_path, d))]
                if not snapshot_dirs:
                    log(f"错误：snapshots 目录为空")
                    return

                model_path = os.path.join(snapshots_path, snapshot_dirs[0])
                log(f"正在加载本地 Faster-Whisper 模型目录：{model_path}")
                # compute_type: GPU 使用 float16 可以节省显存，CPU 可使用 int8
                model = WhisperModel(model_path, device=device, compute_type="float16" if device == "cuda" else "int8")
            else:
                # 直接使用官方模型名加载（例如 "tiny", "base", "small", "medium", "large-v3-turbo" 等）
                log(f"正在加载官方 Faster-Whisper 模型：{selected_model_name}")
                model = WhisperModel(selected_model_name, device=device, compute_type="float16" if device == "cuda" else "int8")
            log("模型加载成功。")
        except Exception as e:
            log(f"加载模型失败：{e}")
            return

        # ========== 逐文件处理 ==========
        for i, file in enumerate(selected_files):
            current_file_index = i
            task_name = os.path.basename(file)
            log(f"开始处理任务 {i+1}/{total_files}：{task_name}")
            file_start = time.time()

            # 输出路径逻辑：如果选择统一存放，则使用 output_folder_var，否则使用源文件目录
            if output_mode_var.get() == 2:
                output_folder = output_folder_var.get().strip()
                if not output_folder:
                    log("请选择输出文件夹！")
                    continue
            else:
                output_folder = os.path.dirname(file)

            # 生成输出文件名（name[.suffix].ext）
            name, _ = os.path.splitext(os.path.basename(file))
            suffix = suffix_var.get().strip()
            ext = "txt" if export_format_var.get() == "TXT" else "srt"
            output_filename = f"{name}.{suffix}.{ext}" if suffix else f"{name}.{ext}"
            output_path = os.path.join(output_folder, output_filename)
            log(f"字幕文件将保存至：{output_path}")

            # 获取音频时长（用于估算与日志）
            try:
                duration_sec = get_audio_duration(file)
            except Exception:
                duration_sec = 0

            # ========== 分片转写（核心）==========
            try:
                segments = transcribe_in_chunks(model, file, lang_option, chunk_duration=60)
            except Exception as e:
                log(f"处理文件 {file} 失败：{e}")
                continue

            # ========== 写入字幕文件 ==========
            try:
                if export_format_var.get() == "TXT":
                    with open(output_path, "w", encoding="utf-8") as f:
                        for seg in segments:
                            # seg.text 是识别出的文本（可能包含换行）
                            f.write(seg.text.strip() + "\n")
                else:
                    # SRT 格式：编号 \n start --> end \n 文本 \n\n
                    with open(output_path, "w", encoding="utf-8") as f:
                        for j, seg in enumerate(segments, start=1):
                            f.write(f"{j}\n")
                            f.write(f"{format_timestamp(seg.start)} --> {format_timestamp(seg.end)}\n")
                            f.write(f"{seg.text.strip()}\n\n")
                log(f"✅ 完成处理文件：{task_name}")
            except Exception as e:
                log(f"写入字幕文件失败：{e}")
                continue

            # ========== 统计与 ETA（简单估算） ==========
            file_elapsed = time.time() - file_start
            processing_times.append(file_elapsed)
            processed_durations.append(duration_sec)
            log(f"⏱ 当前文件用时：{format_hms(file_elapsed)}，音频时长：{format_hms(duration_sec)}")

            if len(processing_times) >= 2 and sum(processed_durations) > 0:
                # 平均每秒处理耗时（秒处理比） = 总耗时 / 总音频秒数
                avg_speed = sum(processing_times) / sum(processed_durations)
                remaining_files = selected_files[i+1:]
                remaining_dur = 0
                for f in remaining_files:
                    try:
                        remaining_dur += get_audio_duration(f)
                    except Exception:
                        pass
                if remaining_dur > 0:
                    eta = remaining_dur * avg_speed
                    log(f"⏳ 预计剩余时间：约 {format_hms(eta)}（基于历史平均速率）")

            log("-" * 50)
            time.sleep(0.2)  # 给 UI 一点空隙，保持响应

    finally:
        # 停止状态线程并等待线程退出
        stop_event.set()
        status_thread.join()

        processing = False
        total_time = time.time() - start_overall
        log(f"🎉 所有文件处理完毕，总耗时：{format_hms(total_time)}。")
        enable_all_controls()

# ---------------------- 启动入口与环境检测 ----------------------

def start_recognition():
    """
    点击“开始识别”按钮的回调：
      - 检查是否已选择文件
      - 如果选择了统一输出模式，则确保输出文件夹已选择
      - 在单独线程中运行 process_files_func，避免阻塞主线程（GUI）
    """
    if not selected_files:
        log("请先选择音视频文件或文件夹！")
        return
    if output_mode_var.get() == 2 and not output_folder_var.get().strip():
        log("请选择输出文件夹！")
        return
    threading.Thread(target=process_files_func, daemon=True).start()


def check_cuda_pytorch():
    """在 GUI 启动时显示 CUDA 是否可用以及 PyTorch 版本，便于排错/确认 GPU 可用性。"""
    try:
        log(f"CUDA是否可用：{torch.cuda.is_available()}")
        log(f"PyTorch版本：{torch.__version__}")
        # 这些 print 主要方便控制台查看（不是必需）
        print("CUDA available:", torch.cuda.is_available())
        print("PyTorch version:", torch.__version__)
    except Exception as e:
        log(f"检查CUDA和PyTorch失败：{e}")

# ---------------------- GUI 布局（完整） ----------------------

main_frame = ttk.Frame(root)
main_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

# ---- 行0：文件操作按钮 ----
ttk.Label(main_frame, text="选择音视频文件：").grid(row=0, column=0, sticky="w", padx=5, pady=5)
select_files_button = ttk.Button(main_frame, text="选择文件", command=select_files)
select_files_button.grid(row=0, column=1, sticky="w", padx=5, pady=5)
select_folder_button = ttk.Button(main_frame, text="选择文件夹", command=select_folder)
select_folder_button.grid(row=0, column=2, sticky="w", padx=5, pady=5)
clear_files_button = ttk.Button(main_frame, text="清空", command=clear_files)
clear_files_button.grid(row=0, column=3, sticky="w", padx=5, pady=5)

# ---- 行1：文件列表显示（Text） ----
files_text = tk.Text(main_frame, width=80, height=10, wrap='word')
files_text.grid(row=1, column=0, columnspan=4, sticky="we", padx=5, pady=(0,5))
# 阻止用户在 Text 中编辑（只允许选择）
files_text.bind("<Key>", lambda e: "break")
update_files_text()

# ---- 行2：上移/下移/删除按钮 ----
btn_frame = ttk.Frame(main_frame)
btn_frame.grid(row=2, column=0, columnspan=4, pady=(0,10))
up_btn = ttk.Button(btn_frame, text="上移", command=move_up)
up_btn.pack(side=tk.LEFT, padx=5)
down_btn = ttk.Button(btn_frame, text="下移", command=move_down)
down_btn.pack(side=tk.LEFT, padx=5)
del_btn = ttk.Button(btn_frame, text="删除", command=delete_selected)
del_btn.pack(side=tk.LEFT, padx=5)

# ---- 行3：语言 & 模型下拉 ----
ttk.Label(main_frame, text="语言选项：").grid(row=3, column=0, sticky="w", padx=5, pady=5)
lang_menu = ttk.Combobox(main_frame, textvariable=lang_var,
                         values=["Auto", "en", "zh", "fr", "de", "es", "it", "ja", "ko", "ru"],
                         state="readonly", width=10)
lang_menu.grid(row=3, column=1, sticky="w", padx=5, pady=5)
lang_menu.set("Auto")
ttk.Label(main_frame, text="选择模型：").grid(row=3, column=2, sticky="w", padx=5, pady=5)
default_models = ["tiny.en", "tiny", "base.en", "base", "small.en", "small",
                  "medium.en", "medium", "large-v1", "large-v2", "large-v3",
                  "large", "distil-large-v2", "distil-medium.en", "distil-small.en",
                  "distil-large-v3", "distil-large-v3.5", "large-v3-turbo", "turbo"]
model_menu = ttk.Combobox(main_frame, textvariable=model_var,
                          values=default_models, state="readonly", width=40)
model_menu.grid(row=3, column=3, sticky="w", padx=5, pady=5)
model_menu.set(default_models[0])

# ---- 行4：本地模型文件夹选择 ----
ttk.Label(main_frame, text="模型文件夹：").grid(row=4, column=0, sticky="w", padx=5, pady=5)
model_folder_entry = ttk.Entry(main_frame, textvariable=model_folder_var, width=60)
model_folder_entry.grid(row=4, column=1, columnspan=2, sticky="w", padx=5, pady=5)
select_model_folder_button = ttk.Button(main_frame, text="选择模型文件夹", command=select_model_folder)
select_model_folder_button.grid(row=4, column=3, sticky="w", padx=5, pady=5)

# ---- 行5：导出格式 ----
ttk.Label(main_frame, text="导出格式：").grid(row=5, column=0, sticky="w", padx=5, pady=5)
export_format_menu = ttk.Combobox(main_frame, textvariable=export_format_var,
                                  values=["SRT", "TXT"], state="readonly", width=10)
export_format_menu.grid(row=5, column=1, sticky="w", padx=5, pady=5)
export_format_menu.set("SRT")

# ---- 行6：输出文件名后缀 ----
ttk.Label(main_frame, text="输出文件名后缀：").grid(row=6, column=0, sticky="w", padx=5, pady=5)
suffix_entry = ttk.Entry(main_frame, textvariable=suffix_var, width=20)
suffix_entry.grid(row=6, column=1, sticky="w", padx=5, pady=5)

# ---- 行7/8：保存方式 & 输出文件夹 ----
ttk.Label(main_frame, text="保存位置：").grid(row=7, column=0, sticky="w", padx=5, pady=5)
radio1 = ttk.Radiobutton(main_frame, text="跟随源文件路径保存", variable=output_mode_var, value=1,
                         command=update_output_folder_state)
radio1.grid(row=7, column=1, sticky="w", padx=(5,2), pady=5)
radio2 = ttk.Radiobutton(main_frame, text="统一存放到指定文件夹", variable=output_mode_var, value=2,
                         command=update_output_folder_state)
radio2.grid(row=7, column=2, sticky="w", padx=(2,5), pady=5)
ttk.Label(main_frame, text="输出文件夹：").grid(row=8, column=0, sticky="w", padx=5, pady=5)
output_folder_entry = ttk.Entry(main_frame, textvariable=output_folder_var, width=60, state="disabled")
output_folder_entry.grid(row=8, column=1, columnspan=2, sticky="w", padx=5, pady=5)
select_output_folder_button = ttk.Button(main_frame, text="选择文件夹", command=select_output_folder, state="disabled")
select_output_folder_button.grid(row=8, column=3, sticky="w", padx=5, pady=5)

# ---- 行9：开始识别按钮 ----
start_button = ttk.Button(main_frame, text="开始识别", command=start_recognition, width=15)
start_button.grid(row=9, column=0, columnspan=4, pady=10)

# ---- 行10：日志区域（滚动） ----
logging_text = scrolledtext.ScrolledText(main_frame, width=80, height=8, state=tk.DISABLED)
logging_text.grid(row=10, column=0, columnspan=4, sticky="nsew", padx=5, pady=5)
# 右键菜单示例：在日志窗口右键可以全选
log_menu = tk.Menu(root, tearoff=0)
log_menu.add_command(label="全选", command=lambda: logging_text.tag_add("sel", "1.0", "end"))
logging_text.bind("<Button-3>", lambda e: (log_menu.tk_popup(e.x_root, e.y_root), log_menu.grab_release()))

# 让日志区域随窗口拉伸
main_frame.rowconfigure(10, weight=1)
main_frame.columnconfigure(3, weight=1)

# 启动时检查 CUDA / PyTorch 信息
check_cuda_pytorch()

# 启动 GUI 主循环（阻塞直到窗口关闭）
root.mainloop()
