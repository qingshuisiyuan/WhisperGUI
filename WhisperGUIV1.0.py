import os
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk
import time
from datetime import datetime
import whisper #pip install -U openai-whisper

# 创建根窗口
root = tk.Tk()
root.title("WhisperGUI视频-语音文件识别字幕并生成str")

# 全局变量
selected_files = []      # 累计选择的音视频文件列表
current_file_index = 0   # 已处理任务数量
total_files = 0          # 总任务数量
processing = False       # 是否处于任务处理阶段

# 创建 Tkinter 变量（指定 master 为 root）
lang_var = tk.StringVar(root, value="Auto")  # 语言选项（默认自动识别）
model_var = tk.StringVar(root, value="")   # 模型下拉框，内容由导入模型文件夹更新
suffix_var = tk.StringVar(root, value="")   # 输出文件名后缀（可选）
output_folder_var = tk.StringVar(root, value="")  # 指定的输出文件夹（可选）
model_folder_var = tk.StringVar(root, value="")   # 模型文件夹路径

def format_timestamp(seconds):
    """将秒数转换为 SRT 格式时间（HH:MM:SS,mmm）"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{millis:03}"

def log(msg):
    """在日志窗口中追加带时间标志的文本"""
    timestamp = datetime.now().strftime("[%H:%M:%S] ")
    logging_text.insert(tk.END, timestamp + msg + "\n")
    logging_text.see(tk.END)
    logging_text.update_idletasks()

def select_files():
    """选择单个或多个音视频文件（累加方式）"""
    filenames = filedialog.askopenfilenames(
        title="选择音视频文件",
        filetypes=[("Media Files", "*.m4a *.mp3 *.mp4 *.wav *.avi *.mov"), ("All Files", "*.*")]
    )
    if filenames:
        # 累加添加，不自动清空已有文件
        for f in filenames:
            if f not in selected_files:
                selected_files.append(f)
        files_list.delete(0, tk.END)
        for f in selected_files:
            files_list.insert(tk.END, f)

def clear_files():
    """清空已选择的文件列表"""
    selected_files.clear()
    files_list.delete(0, tk.END)
    log("已清空选择的文件。")

def on_file_list_right_click(event):
    """右键删除文件列表中的某项"""
    try:
        index = files_list.nearest(event.y)
        file_to_remove = files_list.get(index)
        if file_to_remove in selected_files:
            selected_files.remove(file_to_remove)
        files_list.delete(index)
        log(f"已删除文件：{file_to_remove}")
    except Exception as e:
        log(f"删除文件失败：{e}")

def select_output_folder():
    """选择输出字幕文件保存的文件夹"""
    folder = filedialog.askdirectory(title="选择输出文件夹")
    if folder:
        output_folder_var.set(folder)
        output_folder_entry.config(state=tk.NORMAL)
        output_folder_entry.delete(0, tk.END)
        output_folder_entry.insert(0, folder)

def select_model_folder():
    """选择包含 .pt 模型文件的文件夹，并更新模型下拉框及显示路径"""
    folder = filedialog.askdirectory(title="选择模型文件夹")
    if folder:
        model_folder_var.set(folder)
        model_folder_entry.config(state=tk.NORMAL)
        model_folder_entry.delete(0, tk.END)
        model_folder_entry.insert(0, folder)
        # 扫描该文件夹中所有 .pt 文件，并按文件大小从大到小排序
        pt_files = []
        for f in os.listdir(folder):
            if f.lower().endswith(".pt"):
                full_path = os.path.join(folder, f)
                try:
                    size = os.path.getsize(full_path)
                    pt_files.append((f, size))
                except Exception:
                    continue
        if pt_files:
            pt_files.sort(key=lambda x: x[1], reverse=True)
            models = [os.path.splitext(f)[0] for f, _ in pt_files]
            model_menu['values'] = models
            model_menu.set(models[0])
            log(f"导入模型文件夹成功：{folder}，可用模型（按大小排序）：{', '.join(models)}")
        else:
            log("所选文件夹中没有找到任何 .pt 文件！")

def disable_all_controls():
    """任务开始时禁用除日志外的所有控件"""
    start_button.config(state=tk.DISABLED)
    select_files_button.config(state=tk.DISABLED)
    clear_files_button.config(state=tk.DISABLED)
    select_output_folder_button.config(state=tk.DISABLED)
    select_model_folder_button.config(state=tk.DISABLED)
    lang_menu.config(state=tk.DISABLED)
    model_menu.config(state=tk.DISABLED)
    suffix_entry.config(state=tk.DISABLED)
    output_folder_entry.config(state=tk.DISABLED)
    model_folder_entry.config(state=tk.DISABLED)
    files_list.config(state=tk.DISABLED)

def enable_all_controls():
    """任务结束后恢复所有控件"""
    start_button.config(state=tk.NORMAL)
    select_files_button.config(state=tk.NORMAL)
    clear_files_button.config(state=tk.NORMAL)
    select_output_folder_button.config(state=tk.NORMAL)
    select_model_folder_button.config(state=tk.NORMAL)
    lang_menu.config(state=tk.NORMAL)
    model_menu.config(state=tk.NORMAL)
    suffix_entry.config(state=tk.NORMAL)
    output_folder_entry.config(state=tk.NORMAL)
    model_folder_entry.config(state=tk.NORMAL)
    files_list.config(state=tk.NORMAL)

def update_status():
    """每60秒刷新一次任务状态信息"""
    while processing:
        proc_count = 1 if current_file_index < total_files else 0
        processed = current_file_index
        pending = total_files - current_file_index - (1 if proc_count == 1 else 0)
        log(f"状态：正在处理任务数量：{proc_count}，待处理任务数量：{pending}，已处理任务数量：{processed}")
        time.sleep(60)

def process_files_func():
    global current_file_index, total_files, processing
    disable_all_controls()
    current_file_index = 0
    total_files = len(selected_files)
    processing = True
    # 启动状态更新线程（仅启动一次）
    status_thread = threading.Thread(target=update_status, daemon=True)
    status_thread.start()

    # 在开始任务前加载模型一次（复用后续任务）
    selected_model = model_menu.get().strip()   # 来自模型下拉框
    lang_option = lang_var.get().strip()         # 语言选项
    try:
        log(f"加载模型 {selected_model} …")
        model = whisper.load_model(selected_model, download_root=model_folder_var.get())
        log("模型加载成功。")
    except Exception as e:
        log(f"加载模型失败：{e}")
        processing = False
        enable_all_controls()
        return

    # 遍历所有文件任务
    for file in selected_files:
        task_name = os.path.basename(file)
        log(f"开始处理任务：{task_name}")
        # 如果用户指定了输出文件夹，则所有字幕文件放在同一文件夹，
        # 否则使用当前源文件所在文件夹
        output_folder = output_folder_var.get().strip() or os.path.dirname(file)
        base_name = os.path.basename(file)
        name, ext = os.path.splitext(base_name)
        suffix = suffix_var.get().strip()
        output_filename = f"{name}.{suffix}.srt" if suffix else f"{name}.srt"
        output_path = os.path.join(output_folder, output_filename)
        log(f"字幕文件将保存至：{output_path}")

        try:
            if lang_option.lower() != "auto":
                result = model.transcribe(file, language=lang_option)
            else:
                result = model.transcribe(file)
        except Exception as e:
            log(f"处理文件 {file} 失败：{e}")
            continue

        segments = result.get("segments", [])
        if not segments:
            log("无可用字幕段。")
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                for i, segment in enumerate(segments, start=1):
                    start_sec = segment["start"]
                    end_sec = segment["end"]
                    text_seg = segment["text"].strip()
                    f.write(f"{i}\n")
                    f.write(f"{format_timestamp(start_sec)} --> {format_timestamp(end_sec)}\n")
                    f.write(f"{text_seg}\n\n")
                    root.update_idletasks()
            log(f"完成处理文件：{file}")
        except Exception as e:
            log(f"写入文件 {output_path} 失败：{e}")

        current_file_index += 1
        time.sleep(0.5)

    processing = False
    log("所有文件处理完毕。")
    enable_all_controls()

def start_recognition():
    if not selected_files:
        log("请先选择音视频文件！")
        return
    threading.Thread(target=process_files_func, daemon=True).start()

def show_log_menu(event):
    """在日志窗口显示右键菜单，实现全选复制功能"""
    try:
        log_menu.tk_popup(event.x_root, event.y_root)
    finally:
        log_menu.grab_release()

# ---------------------- 布局区域 ----------------------
frame = tk.Frame(root)
frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

# 文件选择区域
tk.Label(frame, text="选择音视频文件：").grid(row=0, column=0, sticky="w")
select_files_button = tk.Button(frame, text="选择文件", command=select_files)
select_files_button.grid(row=0, column=1, sticky="w")
clear_files_button = tk.Button(frame, text="清空", command=clear_files)
clear_files_button.grid(row=0, column=2, sticky="w")
files_list = tk.Listbox(frame, width=80, height=5)
files_list.grid(row=1, column=0, columnspan=3, pady=5)
files_list.bind("<Button-3>", on_file_list_right_click)  # 右键删除项

# 语言选择
tk.Label(frame, text="语言选项：").grid(row=2, column=0, sticky="w")
lang_menu = ttk.Combobox(frame, textvariable=lang_var,
                         values=["Auto", "en", "zh", "fr", "de", "es", "it", "ja", "ko", "ru"],
                         state="readonly", width=10)
lang_menu.grid(row=2, column=1, sticky="w")
lang_menu.set("Auto")

# 模型选择
tk.Label(frame, text="模型选择：").grid(row=3, column=0, sticky="w")
model_menu = ttk.Combobox(frame, textvariable=model_var, values=[], state="readonly", width=10)
model_menu.grid(row=3, column=1, sticky="w")

# 模型文件夹选择区域
tk.Label(frame, text="模型文件夹：").grid(row=4, column=0, sticky="w")
model_folder_entry = tk.Entry(frame, textvariable=model_folder_var, width=60)
model_folder_entry.grid(row=4, column=1, sticky="w")
select_model_folder_button = tk.Button(frame, text="选择模型文件夹", command=select_model_folder)
select_model_folder_button.grid(row=4, column=2, sticky="w")

# 输出文件名后缀
tk.Label(frame, text="输出文件名后缀：").grid(row=5, column=0, sticky="w")
suffix_entry = tk.Entry(frame, textvariable=suffix_var, width=20)
suffix_entry.grid(row=5, column=1, sticky="w")

# 输出文件夹选择
tk.Label(frame, text="输出文件夹：").grid(row=6, column=0, sticky="w")
output_folder_entry = tk.Entry(frame, textvariable=output_folder_var, width=60)
output_folder_entry.grid(row=6, column=1, sticky="w")
select_output_folder_button = tk.Button(frame, text="选择文件夹", command=select_output_folder)
select_output_folder_button.grid(row=6, column=2, sticky="w")

# 控制按钮区域 —— “开始识别”按钮居中显示
start_button = tk.Button(frame, text="开始识别", command=start_recognition)
start_button.grid(row=7, column=1, pady=10)

# 日志窗口
tk.Label(frame, text="日志：").grid(row=8, column=0, sticky="w")
logging_text = scrolledtext.ScrolledText(frame, width=80, height=10)
logging_text.grid(row=9, column=0, columnspan=3, pady=5)
# 添加右键菜单（全选功能）
log_menu = tk.Menu(root, tearoff=0)
log_menu.add_command(label="全选", command=lambda: logging_text.tag_add("sel", "1.0", "end"))
logging_text.bind("<Button-3>", show_log_menu)

root.mainloop()
