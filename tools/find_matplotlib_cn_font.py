from matplotlib.font_manager import fontManager
import matplotlib.pyplot as plt

import matplotlib as mpl
print(mpl.matplotlib_fname())  # 打印配置文件位置
print(mpl.get_cachedir())  # 打印缓存目录，字体通常在附近的 fonts 子目录
# 打印所有可用字体
fonts = [
    f.name
    for f in fontManager.ttflist
    if "Hei" in f.name or "Song" in f.name or "Kai" in f.name
]

all_fonts = [f.name for f in fontManager.ttflist]
print("可用中文字体:", fonts)
print("所有字体:", all_fonts)

# 或者查看所有字体
# print([f.name for f in fontManager.ttflist])
