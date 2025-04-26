# WhisperGUI-V1.3
python实现的Whisper的GUI页，支持视频、语音文件识别字幕并生成 
![image](https://github.com/user-attachments/assets/f7b13ac6-ddcc-4531-8279-1459fd1451f4) 
## 使用说明
您必须额外安装ffmpeg，并添加到系统环境变量中！https://ffmpeg.org/download.html 
支持GPU运算和纯CPU运算，如果你安装了CUDA12.8版本，则自动启用GPU运算，如没有安装，则使用CPU模式。 
您需要额外安装的CUDA版本：Cuda compilation tools, release 12.8, V12.8.93 
Build cuda_12.8.r12.8/compiler.35583870_0 
因为压缩包内置torch版本cu128，所以你的CUDA版本理论上也需要是12.8，才可能运行稳定。 

在不导入本地模型的情况下，可以直接官方的在线模型，程序会自动下载并加载。 
可以选择导入本地自定义模型，但必须是pt格式（直接把模型文件改为pt扩展名）并且与openai官方模型名称一致（自行下载的模型名称改为：tiny.pt,base.pt,small.pt,medium.pt,large-v3-turbo.pt,large-v2.pt,large-v3.pt等与openai官方模型的名称一致就可以导入并加载。） 
上个版本的发布页面提供了离线的openai官方模型base.pt、small.pt、medium.pt、large-v3-turbo.pt、large-v3.pt六种模型，其中large-v3效果最好。 

1.3版本的发布页面提供打包好环境的压缩包，解压后无需python环境可直接运行。如果您需要离线模型，请下载之前发布的版本，带有离线模型包。 

如果你选择导出为TXT格式，你将会得到一段没有任何标点符号的连续文本，这个问题暂时无法解决。 





# WhisperGUI-V1.2
python实现的Whisper视频、语音文件识别字幕并生成
![image](https://github.com/user-attachments/assets/9c25a027-8af7-44c3-936f-fc84743b7e58)
#使用说明
在不导入本地模型的情况下，可以直接选择官方的在线模型，程序会自动下载并加载。  
可以导入本地自定义模型，但必须是pt格式（直接把模型文件改为pt扩展名）并且与openai官方模型名字一致（自行下载的模型改为：tiny.pt, base.pt, small.pt, medium.pt, large-v3-turbo.pt, large-v2.pt, large-v3.pt等与openai官方模型一致的名字就可以导入并加载。）  
releases页面提供了离线的openai官方模型base.pt, small.pt, medium.pt, large-v3-turbo.pt, large-v3.pt六种模型，其中large-v3效果最好。  
如果你选择导出为TXT格式，你将会得到一段没有任何标点符号的连续文本，这个问题暂时无法解决。  
仅测试了CPU环境（用没有独立N显卡的笔记本开发的）。
