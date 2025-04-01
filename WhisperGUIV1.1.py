import os
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk
import time
from datetime import datetime
import whisper  # pip install -U openai-whisper

# 保存原始的 load_model 函数
_original_load_model = whisper.load_model

def load_model_custom(name, **kwargs):
    # 如果模型名称是自定义名称，则转换为官方对应的名称
    if name == "BELLE-2Belle-whisper-large-v3-turbo-zh":
        name = "turbo"  # 对应于官方的 turbo 模型
    elif name == "BELLE-2Belle-whisper-large-v3-zh-punct":
        name = "large"  # 对应于官方的 large 模型
    return _original_load_model(name, **kwargs)

whisper.load_model = load_model_custom

# ---------------------- 全局变量 ----------------------
selected_files = []      # 累计选择的音视频文件列表
current_file_index = 0   # 已处理任务数量
total_files = 0          # 总任务数量
processing = False       # 是否处于任务处理阶段
supported_extensions = (".m4a", ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv", ".flac", ".ogg", ".webm")

# ---------------------- Tkinter初始化 ----------------------
root = tk.Tk()
root.title("WhisperGUI视频-语音文件识别字幕并生成str")
root.geometry("900x600")  # 整体窗口尺寸设置为900x650

# 使用 ttk 主题，使界面看起来更现代
style = ttk.Style()
style.theme_use("vista") # 可选主题：clam, alt, default, classic，winnative, xpnative, vista

# ---------------------- Tkinter变量 ----------------------
lang_var = tk.StringVar(root, value="Auto")  # 语言选项（默认自动识别）
model_var = tk.StringVar(root)               # 模型下拉框变量
suffix_var = tk.StringVar(root, value="")     # 输出文件名后缀（可选）
output_folder_var = tk.StringVar(root, value="")  # 指定的输出文件夹（可选）
model_folder_var = tk.StringVar(root, value="")   # 模型文件夹路径
output_mode_var = tk.IntVar(root, value=1)    # 输出方式：1-跟随源文件路径，2-统一存放

# ---------------------- 函数区 ----------------------
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
    logging_text.config(state=tk.NORMAL)
    logging_text.insert(tk.END, timestamp + msg + "\n")
    logging_text.see(tk.END)
    logging_text.update_idletasks()
    logging_text.config(state=tk.DISABLED)

def update_files_text():
    """更新文件显示的 Text 控件，每个文件占一行"""
    files_text.config(state=tk.NORMAL)
    files_text.delete("1.0", tk.END)
    for f in selected_files:
        files_text.insert(tk.END, f + "\n")
    files_text.config(state=tk.DISABLED)

def select_files():
    """选择单个或多个音视频文件（累加方式）"""
    filenames = filedialog.askopenfilenames(
        title="选择音视频文件",
        filetypes=[("Media Files", "*.m4a *.mp3 *.mp4 *.wav *.avi *.mov *.mkv *.flac *.ogg *.webm"), ("All Files", "*.*")]
    )
    if filenames:
        for f in filenames:
            if f not in selected_files:
                selected_files.append(f)
        update_files_text()

def select_folder():
    """选择文件夹，递归扫描并导入所有支持的音视频文件"""
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
    """清空已选择的文件列表"""
    selected_files.clear()
    update_files_text()
    log("已清空选择的文件。")

# 下面辅助函数用于获取 Text 控件中选中的行索引（0基）
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
    """上移选中行"""
    start_line, end_line = get_selected_line_indices()
    if start_line is None:
        log("请先选择要上移的文件。")
        return
    if start_line <= 0:
        log("已到顶部，无法上移。")
        return
    block = selected_files[start_line:end_line+1]
    # 移除选中块
    del selected_files[start_line:end_line+1]
    new_index = start_line - 1
    # 插入到上面一行位置
    for i, item in enumerate(block):
        selected_files.insert(new_index + i, item)
    update_files_text()
    # 重新选中调整后的块（Text控件行号为1基）
    files_text.tag_remove("sel", "1.0", tk.END)
    files_text.tag_add("sel", f"{new_index+1}.0", f"{new_index+len(block)}.end")

def move_down():
    """下移选中行"""
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
    files_text.tag_remove("sel", "1.0", tk.END)
    files_text.tag_add("sel", f"{new_index+1}.0", f"{new_index+len(block)}.end")

def delete_selected():
    """删除选中的文件"""
    start_line, end_line = get_selected_line_indices()
    if start_line is None:
        log("请先选择要删除的文件。")
        return
    del selected_files[start_line:end_line+1]
    update_files_text()
    log("已删除选中的文件。")

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
    folder = filedialog.askdirectory(title="模型文件夹")
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

def update_output_folder_state():
    """根据输出方式设置输出文件夹控件状态"""
    if output_mode_var.get() == 2:
        output_folder_entry.config(state=tk.NORMAL)
        select_output_folder_button.config(state=tk.NORMAL)
    else:
        output_folder_entry.config(state=tk.DISABLED)
        select_output_folder_button.config(state=tk.DISABLED)

def disable_all_controls():
    """任务开始时禁用除日志外的所有控件"""
    start_button.config(state=tk.DISABLED)
    select_files_button.config(state=tk.DISABLED)
    select_folder_button.config(state=tk.DISABLED)
    clear_files_button.config(state=tk.DISABLED)
    select_output_folder_button.config(state=tk.DISABLED)
    select_model_folder_button.config(state=tk.DISABLED)
    lang_menu.config(state=tk.DISABLED)
    model_menu.config(state=tk.DISABLED)
    suffix_entry.config(state=tk.DISABLED)
    output_folder_entry.config(state=tk.DISABLED)
    model_folder_entry.config(state=tk.DISABLED)
    files_text.config(state=tk.DISABLED)
    # 新增：禁用上移、下移、删除按钮
    up_btn.config(state=tk.DISABLED)
    down_btn.config(state=tk.DISABLED)
    del_btn.config(state=tk.DISABLED)

def enable_all_controls():
    """任务结束后恢复所有控件"""
    start_button.config(state=tk.NORMAL)
    select_files_button.config(state=tk.NORMAL)
    select_folder_button.config(state=tk.NORMAL)
    clear_files_button.config(state=tk.NORMAL)
    select_output_folder_button.config(state=tk.NORMAL)
    select_model_folder_button.config(state=tk.NORMAL)
    lang_menu.config(state=tk.NORMAL)
    model_menu.config(state=tk.NORMAL)
    suffix_entry.config(state=tk.NORMAL)
    update_output_folder_state()
    model_folder_entry.config(state=tk.NORMAL)
    files_text.config(state=tk.NORMAL)
    # 新增：恢复上移、下移、删除按钮
    up_btn.config(state=tk.NORMAL)
    down_btn.config(state=tk.NORMAL)
    del_btn.config(state=tk.NORMAL)

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
    status_thread = threading.Thread(target=update_status, daemon=True)
    status_thread.start()

    selected_model = model_menu.get().strip()
    lang_option = lang_var.get().strip()

    try:
        log(f"加载模型 {selected_model} …")
        if model_folder_var.get().strip():
            model = whisper.load_model(selected_model, download_root=model_folder_var.get())
        else:
            model = whisper.load_model(selected_model)
        log("模型加载成功。")
    except Exception as e:
        log(f"加载模型失败：{e}")
        processing = False
        enable_all_controls()
        return

    for file in selected_files:
        task_name = os.path.basename(file)
        log(f"开始处理任务：{task_name}")

        if output_mode_var.get() == 2:
            output_folder = output_folder_var.get().strip()
            if not output_folder:
                log("请选择输出文件夹！")
                continue
        else:
            output_folder = os.path.dirname(file)

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
        log("请先选择音视频文件或文件夹！")
        return
    threading.Thread(target=process_files_func, daemon=True).start()

# ---------------------- 界面布局 ----------------------
main_frame = ttk.Frame(root)
main_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

# 行0：文件操作区域
ttk.Label(main_frame, text="选择音视频文件：").grid(row=0, column=0, sticky="w", padx=5, pady=5)
select_files_button = ttk.Button(main_frame, text="选择文件", command=select_files)
select_files_button.grid(row=0, column=1, sticky="w", padx=5, pady=5)
select_folder_button = ttk.Button(main_frame, text="选择文件夹", command=select_folder)
select_folder_button.grid(row=0, column=2, sticky="w", padx=5, pady=5)
clear_files_button = ttk.Button(main_frame, text="清空", command=clear_files)
clear_files_button.grid(row=0, column=3, sticky="w", padx=5, pady=5)

# 行1：文件列表显示（使用 Text 控件，设置自动换行，并设为只读）
files_text = tk.Text(main_frame, width=80, height=10, wrap='word')
files_text.grid(row=1, column=0, columnspan=4, sticky="we", padx=5, pady=(0,5))
# 设置 Text 为只读，但允许选择：拦截按键事件
files_text.bind("<Key>", lambda e: "break")
update_files_text()

# 行2：在文件窗口下方增加三个按钮：上移、下移、删除
btn_frame = ttk.Frame(main_frame)
btn_frame.grid(row=2, column=0, columnspan=4, pady=(0,10))
up_btn = ttk.Button(btn_frame, text="上移", command=move_up)
up_btn.pack(side=tk.LEFT, padx=5)
down_btn = ttk.Button(btn_frame, text="下移", command=move_down)
down_btn.pack(side=tk.LEFT, padx=5)
del_btn = ttk.Button(btn_frame, text="删除", command=delete_selected)
del_btn.pack(side=tk.LEFT, padx=5)

# 行3：语言与模型选择区域
ttk.Label(main_frame, text="语言选项：").grid(row=3, column=0, sticky="w", padx=5, pady=5)
lang_menu = ttk.Combobox(main_frame, textvariable=lang_var,
                         values=["Auto", "en", "zh", "fr", "de", "es", "it", "ja", "ko", "ru"],
                         state="readonly", width=10)
lang_menu.grid(row=3, column=1, sticky="w", padx=5, pady=5)
lang_menu.set("Auto")
ttk.Label(main_frame, text="选择模型：").grid(row=3, column=2, sticky="w", padx=5, pady=5)
default_models = ["tiny", "base", "small", "medium", "large-v3-turbo", "large-v2", "large-v3"]
#  默认模型列表
# 这里可以根据需要添加更多模型名称
# 例如：default_models = ['tiny.en', 'tiny', 'base.en', 'base', 'small.en', 'small', 'medium.en', 'medium', 'large-v1', 'large-v2', 'large-v3', 'large', 'large-v3-turbo']

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

# 行5：输出文件名后缀
ttk.Label(main_frame, text="输出文件名后缀：").grid(row=5, column=0, sticky="w", padx=5, pady=5)
suffix_entry = ttk.Entry(main_frame, textvariable=suffix_var, width=20)
suffix_entry.grid(row=5, column=1, sticky="w", padx=5, pady=5)

# 行6：保存方式及输出文件夹
ttk.Label(main_frame, text="保存位置：").grid(row=6, column=0, sticky="w", padx=5, pady=5)
radio1 = ttk.Radiobutton(main_frame, text="跟随源文件路径保存", variable=output_mode_var, value=1,
                         command=update_output_folder_state)
radio1.grid(row=6, column=1, sticky="w", padx=(5,2), pady=5)
radio2 = ttk.Radiobutton(main_frame, text="统一存放到指定文件夹", variable=output_mode_var, value=2,
                         command=update_output_folder_state)
radio2.grid(row=6, column=2, sticky="w", padx=(2,5), pady=5)
ttk.Label(main_frame, text="输出文件夹：").grid(row=7, column=0, sticky="w", padx=5, pady=5)
output_folder_entry = ttk.Entry(main_frame, textvariable=output_folder_var, width=60, state="disabled")
output_folder_entry.grid(row=7, column=1, columnspan=2, sticky="w", padx=5, pady=5)
select_output_folder_button = ttk.Button(main_frame, text="选择文件夹", command=select_output_folder, state="disabled")
select_output_folder_button.grid(row=7, column=3, sticky="w", padx=5, pady=5)

# 行8：开始识别按钮
start_button = ttk.Button(main_frame, text="开始识别", command=start_recognition, width=15)
start_button.grid(row=8, column=0, columnspan=4, pady=10)

# 行9：日志区域
logging_text = scrolledtext.ScrolledText(main_frame, width=80, height=8, state=tk.DISABLED)
logging_text.grid(row=9, column=0, columnspan=4, sticky="nsew", padx=5, pady=5)
log_menu = tk.Menu(root, tearoff=0)
log_menu.add_command(label="全选", command=lambda: logging_text.tag_add("sel", "1.0", "end"))
logging_text.bind("<Button-3>", lambda e: (log_menu.tk_popup(e.x_root, e.y_root), log_menu.grab_release()))

# 让日志区域随窗口拉伸
main_frame.rowconfigure(9, weight=1)
main_frame.columnconfigure(3, weight=1)

root.mainloop()
