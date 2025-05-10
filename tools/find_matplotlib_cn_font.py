from matplotlib.font_manager import fontManager
import matplotlib.pyplot as plt

# 打印所有可用字体
fonts = [
    f.name
    for f in fontManager.ttflist
    if "Hei" in f.name or "Song" in f.name or "Kai" in f.name
]
print("可用中文字体:", fonts)

# 或者查看所有字体
# print([f.name for f in fontManager.ttflist])
