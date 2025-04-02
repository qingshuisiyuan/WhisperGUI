# WhisperGUI
python实现的Whisper视频、语音文件识别字幕并生成
![image](https://github.com/user-attachments/assets/9c25a027-8af7-44c3-936f-fc84743b7e58)
#使用说明
在不导入本地模型的情况下，可以直接选择官方的在线模型，程序会自动下载并加载。  
可以导入本地自定义模型，但必须是pt格式（直接把模型文件改为pt扩展名）并且与openai官方模型名字一致（自行下载的模型改为：tiny.pt, base.pt, small.pt, medium.pt, large-v3-turbo.pt, large-v2.pt, large-v3.pt等与openai官方模型一致的名字就可以导入并加载。）  
releases页面提供了离线的openai官方模型base.pt, small.pt, medium.pt, large-v3-turbo.pt, large-v3.pt六种模型，其中large-v3效果最好。  
如果你选择导出为TXT格式，你将会得到一段没有任何标点符号的连续文本，这个问题暂时无法解决。  
仅测试了CPU环境（用没有独立N显卡的笔记本开发的）。
