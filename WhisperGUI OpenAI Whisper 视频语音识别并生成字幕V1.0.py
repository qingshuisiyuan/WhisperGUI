# WhisperGUI - OpenAI whisper 版
# 功能：
#  - 使用 openai-whisper (whisper.load_model / model.transcribe) 转写音视频
#  - 支持从本地模型文件夹加载 .pt（通过 download_root 参数）
#  - 输出 SRT / TXT，文件名格式：name[.suffix].srt 或 .txt
# 注意：需要系统安装 ffmpeg/ffprobe（脚本使用 ffprobe 获取时长）

import os
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk
import time
from datetime import datetime
import whisper            # pip install -U openai-whisper
import torch
import subprocess
import json

# ---------------------- 全局变量 ----------------------
selected_files = []      # 列表：累积的音视频文件路径（用户选择）
current_file_index = 0   # 当前已处理的文件索引（用于进度/状态显示）
total_files = 0          # 总任务数量（len(selected_files)）
processing = False       # 标识：程序是否正在处理任务
supported_extensions = ( # 支持的音视频文件扩展名
    ".m4a", ".mp3", ".mp4", ".wav", ".avi", ".vob",
    ".mov", ".mkv", ".aac", ".flac", ".ogg", ".webm",
    ".flv", ".rmvb", ".wmv"
)

# ---------------------- Tkinter 初始化 ----------------------
root = tk.Tk()
root.title("WhisperGUI OpenAI Whisper 视频/语音识别并生成字幕")
root.geometry("900x600")

style = ttk.Style()
style.theme_use("vista")

# ---------------------- Tkinter 变量 ----------------------
lang_var = tk.StringVar(root, value="Auto")
model_var = tk.StringVar(root)
suffix_var = tk.StringVar(root, value="")
export_format_var = tk.StringVar(root, value="SRT")
output_folder_var = tk.StringVar(root, value="")
model_folder_var = tk.StringVar(root, value="")
output_mode_var = tk.IntVar(root, value=1)

# ---------------------- 工具函数 ----------------------
def format_timestamp(seconds):
    """将秒数转换为 SRT 时间戳 HH:MM:SS,mmm"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{millis:03}"

def format_hms(seconds):
    """把秒格式化成人类可读格式（用于日志 ETA）"""
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

def log(msg):
    """在日志窗口中追加一行，带时间戳"""
    timestamp = datetime.now().strftime("[%H:%M:%S] ")
    logging_text.config(state=tk.NORMAL)
    logging_text.insert(tk.END, timestamp + msg + "\n")
    logging_text.see(tk.END)
    logging_text.update_idletasks()
    logging_text.config(state=tk.DISABLED)

# ---------------------- 文件操作 ----------------------
def update_files_text():
    files_text.config(state=tk.NORMAL)
    files_text.delete("1.0", tk.END)
    for f in selected_files:
        files_text.insert(tk.END, f + "\n")
    files_text.config(state=tk.DISABLED)

def select_files():
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
    selected_files.clear()
    update_files_text()
    log("已清空选择的文件。")

# ---------------------- 文件列表控件辅助 ----------------------
def get_selected_line_indices():
    try:
        sel_first = files_text.index("sel.first")
        sel_last = files_text.index("sel.last")
        start_line = int(sel_first.split('.')[0]) - 1
        end_line = int(sel_last.split('.')[0]) - 1
        return start_line, end_line
    except tk.TclError:
        return None, None

def move_up():
    start_line, end_line = get_selected_line_indices()
    if start_line is None:
        log("请先选择要上移的文件。")
        return
    if start_line <= 0:
        log("已到顶部，无法上移。")
        return
    block = selected_files[start_line:end_line+1]
    del selected_files[start_line:end_line+1]
    new_index = start_line - 1
    for i, item in enumerate(block):
        selected_files.insert(new_index + i, item)
    update_files_text()

def move_down():
    start_line, end_line = get_selected_line_indices()
    if start_line is None:
        log("请先选择要下移的文件。")
        return
    if end_line >= len(selected_files) - 1:
        log("已到底部，无法下移。")
        return
    block = selected_files[start_line:end_line+1]
    del selected_files[start_line:end_line+1]
    new_index = start_line + 1
    for i, item in enumerate(block):
        selected_files.insert(new_index + i, item)
    update_files_text()

def delete_selected():
    start_line, end_line = get_selected_line_indices()
    if start_line is None:
        log("请先选择要删除的文件。")
        return
    del selected_files[start_line:end_line+1]
    update_files_text()
    log("已删除选中的文件。")

# ---------------------- 输出/模型选择 ----------------------
def select_output_folder():
    folder = filedialog.askdirectory(title="选择输出文件夹")
    if folder:
        output_folder_var.set(folder)
        output_folder_entry.config(state=tk.NORMAL)
        output_folder_entry.delete(0, tk.END)
        output_folder_entry.insert(0, folder)
    log(f"已选择输出文件夹：{folder}")

def select_model_folder():
    """
    扫描指定文件夹下的 .pt 文件并把文件名（去掉 .pt）放到模型下拉框中。
    这样用户可以直接选择本地 .pt 模型（结合 whisper.load_model 的 download_root 使用）。
    """
    folder = filedialog.askdirectory(title="选择模型文件夹")
    if folder:
        model_folder_var.set(folder)
        model_folder_entry.config(state=tk.NORMAL)
        model_folder_entry.delete(0, tk.END)
        model_folder_entry.insert(0, folder)
        pt_files = []
        for f in os.listdir(folder):
            if f.lower().endswith(".pt"):
                try:
                    size = os.path.getsize(os.path.join(folder, f))
                    pt_files.append((f, size))
                except Exception:
                    pt_files.append((f, 0))
        if pt_files:
            pt_files.sort(key=lambda x: x[1], reverse=True)
            models = [os.path.splitext(f)[0] for f, _ in pt_files]
            model_menu['values'] = models
            model_menu.set(models[0])
            log(f"导入模型文件夹成功：{folder}，可用模型（按大小排序）：{', '.join(models)}")
        else:
            log("所选文件夹中没有找到任何 .pt 文件！")

def update_output_folder_state():
    if output_mode_var.get() == 2:
        output_folder_entry.config(state=tk.NORMAL)
        select_output_folder_button.config(state=tk.NORMAL)
    else:
        output_folder_entry.config(state=tk.DISABLED)
        select_output_folder_button.config(state=tk.DISABLED)
    log("已更新输出文件夹控件状态。")

# ---------------------- 控件启用/禁用 ----------------------
def disable_all_controls():
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

# ---------------------- 时长 / 大小 等辅助 ----------------------
def format_hms_short(seconds):
    """格式化成 HH:MM:SS（更适合显示耗时）"""
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

def get_audio_duration(file_path):
    """
    使用 ffprobe 获取文件时长（秒）。需要系统安装 ffmpeg/ffprobe。
    如果出错返回 0。
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

# ---------------------- 周期状态刷新线程 ----------------------
def update_status(stop_event, log_func, total_files, processed_files_func):
    """
    后台线程：每60秒刷新一次任务状态（写入日志）。
    stop_event 用于通知线程退出（当处理结束）。
    """
    while not stop_event.is_set():
        try:
            processed = processed_files_func()
            pending = total_files - processed
            log_func(f"状态：正在处理任务数量：1，已处理任务数量：{processed}，待处理任务数量：{pending}")
        except Exception as e:
            log_func(f"状态刷新出错：{e}")
        # 分段sleep以便快速响应 stop_event
        for _ in range(60):
            if stop_event.is_set():
                break
            time.sleep(1)

# ---------------------- 主处理逻辑（OpenAI whisper 版） ----------------------
def process_files_func():
    """
    主要流程：
      - 禁用界面控件
      - 启动状态刷新线程
      - 加载 openai-whisper 模型（支持本地 .pt，通过 download_root）
      - 对每个文件调用 model.transcribe(...)（不做分片）
      - 写入 SRT 或 TXT
      - 统计耗时 / 估算 ETA
      - 恢复控件
    """
    global current_file_index, total_files, processing
    disable_all_controls()
    current_file_index = 0
    total_files = len(selected_files)
    processing = True

    stop_event = threading.Event()
    status_thread = threading.Thread(
        target=update_status,
        args=(stop_event, log, total_files, lambda: current_file_index),
        daemon=True
    )
    status_thread.start()

    processed_durations = []
    processing_times = []
    start_overall = time.time()

    try:
        lang_option = lang_var.get().strip()
        selected_model_name = model_var.get().strip()
        # ========== 加载模型（支持本地 .pt 通过 download_root） ==========
        try:
            log(f"加载模型 {selected_model_name} …")
            if model_folder_var.get().strip():
                # 如果你选择了一个本地模型文件夹，并且下拉框值对应该文件夹中 .pt 的基名（如 large-v3）
                # whisper.load_model 会在 download_root 目录下查找 <name>.pt
                model = whisper.load_model(selected_model_name, device="cuda" if torch.cuda.is_available() else "cpu", download_root=model_folder_var.get().strip())
            else:
                model = whisper.load_model(selected_model_name, device="cuda" if torch.cuda.is_available() else "cpu")
            log("模型加载成功。")
        except Exception as e:
            log(f"加载模型失败：{e}")
            return

        # ========== 遍历文件进行转写（不分片） ==========
        for i, file in enumerate(selected_files):
            current_file_index = i
            task_name = os.path.basename(file)
            log(f"开始处理任务 {i+1}/{total_files}：{task_name}")
            file_start = time.time()

            # 输出路径逻辑
            if output_mode_var.get() == 2:
                output_folder = output_folder_var.get().strip()
                if not output_folder:
                    log("请选择输出文件夹！")
                    continue
            else:
                output_folder = os.path.dirname(file)

            name, _ = os.path.splitext(os.path.basename(file))
            suffix = suffix_var.get().strip()
            ext = "txt" if export_format_var.get() == "TXT" else "srt"
            output_filename = f"{name}.{suffix}.{ext}" if suffix else f"{name}.{ext}"
            output_path = os.path.join(output_folder, output_filename)
            log(f"字幕文件将保存至：{output_path}")

            # 获取音频时长（用于 ETA）
            try:
                duration_sec = get_audio_duration(file)
            except Exception:
                duration_sec = 0

            # ========== 转写调用：严格按照你指定的参数 ==========
            try:
                result = model.transcribe(
                    file,
                    language=None if lang_option.lower() == "auto" else lang_option,
                    condition_on_previous_text=False,   # ✅ 防止重复
                    word_timestamps=True                # ✅ 保留时间轴
                )
            except Exception as e:
                log(f"处理文件 {file} 失败：{e}")
                continue

            # ========== 写字幕文件 ==========
            try:
                if export_format_var.get() == "TXT":
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(result.get("text", ""))
                else:
                    segments = result.get("segments", [])
                    if not segments:
                        log("无可用字幕段。")
                    with open(output_path, "w", encoding="utf-8") as f:
                        for j, seg in enumerate(segments, start=1):
                            start_sec = seg.get("start", 0.0)
                            end_sec = seg.get("end", 0.0)
                            text_seg = seg.get("text", "").strip()
                            f.write(f"{j}\n")
                            f.write(f"{format_timestamp(start_sec)} --> {format_timestamp(end_sec)}\n")
                            f.write(f"{text_seg}\n\n")
                log(f"✅ 完成处理文件：{task_name}")
            except Exception as e:
                log(f"写入字幕文件失败：{e}")
                continue

            # ========== 统计耗时与 ETA ==========
            file_elapsed = time.time() - file_start
            processing_times.append(file_elapsed)
            processed_durations.append(duration_sec)
            log(f"⏱ 当前文件用时：{format_hms(file_elapsed)}，音频时长：{format_hms(duration_sec)}")

            if len(processing_times) >= 2 and sum(processed_durations) > 0:
                avg_speed = sum(processing_times) / sum(processed_durations)  # 秒模型耗时 / 秒音频
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
            time.sleep(0.2)

    finally:
        # 停止状态线程
        stop_event.set()
        status_thread.join()

        processing = False
        total_time = time.time() - start_overall
        log(f"🎉 所有文件处理完毕，总耗时：{format_hms(total_time)}。")
        enable_all_controls()

# ---------------------- 启动识别 ----------------------
def start_recognition():
    if not selected_files:
        log("请先选择音视频文件或文件夹！")
        return
    if output_mode_var.get() == 2 and not output_folder_var.get().strip():
        log("请选择输出文件夹！")
        return
    threading.Thread(target=process_files_func, daemon=True).start()

def check_cuda_pytorch():
    try:
        log(f"CUDA是否可用：{torch.cuda.is_available()}")
        log(f"PyTorch版本：{torch.__version__}")
        print("CUDA available:", torch.cuda.is_available())
        print("PyTorch version:", torch.__version__)
    except Exception as e:
        log(f"检查CUDA和PyTorch失败：{e}")

# ---------------------- GUI 布局（与 F 版本一致） ----------------------
main_frame = ttk.Frame(root)
main_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

# 行0：文件操作
ttk.Label(main_frame, text="选择音视频文件：").grid(row=0, column=0, sticky="w", padx=5, pady=5)
select_files_button = ttk.Button(main_frame, text="选择文件", command=select_files)
select_files_button.grid(row=0, column=1, sticky="w", padx=5, pady=5)
select_folder_button = ttk.Button(main_frame, text="选择文件夹", command=select_folder)
select_folder_button.grid(row=0, column=2, sticky="w", padx=5, pady=5)
clear_files_button = ttk.Button(main_frame, text="清空", command=clear_files)
clear_files_button.grid(row=0, column=3, sticky="w", padx=5, pady=5)

# 行1：文件列表显示
files_text = tk.Text(main_frame, width=80, height=10, wrap='word')
files_text.grid(row=1, column=0, columnspan=4, sticky="we", padx=5, pady=(0,5))
files_text.bind("<Key>", lambda e: "break")
update_files_text()

# 行2：上移/下移/删除
btn_frame = ttk.Frame(main_frame)
btn_frame.grid(row=2, column=0, columnspan=4, pady=(0,10))
up_btn = ttk.Button(btn_frame, text="上移", command=move_up)
up_btn.pack(side=tk.LEFT, padx=5)
down_btn = ttk.Button(btn_frame, text="下移", command=move_down)
down_btn.pack(side=tk.LEFT, padx=5)
del_btn = ttk.Button(btn_frame, text="删除", command=delete_selected)
del_btn.pack(side=tk.LEFT, padx=5)

# 行3：语言与模型
ttk.Label(main_frame, text="语言选项：").grid(row=3, column=0, sticky="w", padx=5, pady=5)
lang_menu = ttk.Combobox(main_frame, textvariable=lang_var,
                         values=["Auto", "en", "zh", "fr", "de", "es", "it", "ja", "ko", "ru"],
                         state="readonly", width=10)
lang_menu.grid(row=3, column=1, sticky="w", padx=5, pady=5)
lang_menu.set("Auto")
ttk.Label(main_frame, text="选择模型：").grid(row=3, column=2, sticky="w", padx=5, pady=5)
default_models = ["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo", "large-v2"]
model_menu = ttk.Combobox(main_frame, textvariable=model_var,
                          values=default_models, state="readonly", width=40)
model_menu.grid(row=3, column=3, sticky="w", padx=5, pady=5)
model_menu.set(default_models[0])

# 行4：本地模型文件夹
ttk.Label(main_frame, text="模型文件夹：").grid(row=4, column=0, sticky="w", padx=5, pady=5)
model_folder_entry = ttk.Entry(main_frame, textvariable=model_folder_var, width=60)
model_folder_entry.grid(row=4, column=1, columnspan=2, sticky="w", padx=5, pady=5)
select_model_folder_button = ttk.Button(main_frame, text="选择模型文件夹", command=select_model_folder)
select_model_folder_button.grid(row=4, column=3, sticky="w", padx=5, pady=5)

# 行5：导出格式
ttk.Label(main_frame, text="导出格式：").grid(row=5, column=0, sticky="w", padx=5, pady=5)
export_format_menu = ttk.Combobox(main_frame, textvariable=export_format_var,
                                  values=["SRT", "TXT"], state="readonly", width=10)
export_format_menu.grid(row=5, column=1, sticky="w", padx=5, pady=5)
export_format_menu.set("SRT")

# 行6：输出文件名后缀
ttk.Label(main_frame, text="输出文件名后缀：").grid(row=6, column=0, sticky="w", padx=5, pady=5)
suffix_entry = ttk.Entry(main_frame, textvariable=suffix_var, width=20)
suffix_entry.grid(row=6, column=1, sticky="w", padx=5, pady=5)

# 行7/8：保存方式 & 输出文件夹
ttk.Label(main_frame, text="保存位置：").grid(row=7, column=0, sticky="w", padx=5, pady=5)
radio1 = ttk.Radiobutton(main_frame, text="跟随源文件路径保存", variable=output_mode_var, value=1, command=update_output_folder_state)
radio1.grid(row=7, column=1, sticky="w", padx=(5,2), pady=5)
radio2 = ttk.Radiobutton(main_frame, text="统一存放到指定文件夹", variable=output_mode_var, value=2, command=update_output_folder_state)
radio2.grid(row=7, column=2, sticky="w", padx=(2,5), pady=5)
ttk.Label(main_frame, text="输出文件夹：").grid(row=8, column=0, sticky="w", padx=5, pady=5)
output_folder_entry = ttk.Entry(main_frame, textvariable=output_folder_var, width=60, state="disabled")
output_folder_entry.grid(row=8, column=1, columnspan=2, sticky="w", padx=5, pady=5)
select_output_folder_button = ttk.Button(main_frame, text="选择文件夹", command=select_output_folder, state="disabled")
select_output_folder_button.grid(row=8, column=3, sticky="w", padx=5, pady=5)

# 行9：开始识别
start_button = ttk.Button(main_frame, text="开始识别", command=start_recognition, width=15)
start_button.grid(row=9, column=0, columnspan=4, pady=10)

# 行10：日志区域
logging_text = scrolledtext.ScrolledText(main_frame, width=80, height=8, state=tk.DISABLED)
logging_text.grid(row=10, column=0, columnspan=4, sticky="nsew", padx=5, pady=5)
log_menu = tk.Menu(root, tearoff=0)
log_menu.add_command(label="全选", command=lambda: logging_text.tag_add("sel", "1.0", "end"))
logging_text.bind("<Button-3>", lambda e: (log_menu.tk_popup(e.x_root, e.y_root), log_menu.grab_release()))

main_frame.rowconfigure(10, weight=1)
main_frame.columnconfigure(3, weight=1)

# 启动时检查 CUDA / PyTorch 信息
check_cuda_pytorch()

# 启动 GUI 主循环
root.mainloop()
