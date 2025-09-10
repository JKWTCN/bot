import matplotlib.pyplot as plt
import matplotlib as mpl

# 设置字体回退链：如果第一个字体缺少字符，会尝试下一个
plt.rcParams["font.sans-serif"] = [
    "Unifont",
    "Noto Sans CJK SC",  # 思源黑体，支持繁简中文
    "SimHei",  # 黑体
    "Microsoft YaHei",  # 微软雅黑
    "KaiTi",  # 楷体
    "FangSong",  # 仿宋
    "Arial Unicode MS",  # Arial Unicode，支持多种字符
    "DejaVu Sans",  # 较全面的Unicode字体
]

# 解决负号显示问题
plt.rcParams["axes.unicode_minus"] = False

# 测试显示
plt.figure(figsize=(10, 6))
plt.text(0.1, 0.8, "中文测试 Chinese Test", fontsize=20)
plt.text(0.1, 0.6, "数学符号: ∑ ∫ ∏ √ ∞ ≠ ≈", fontsize=20)
plt.text(0.1, 0.4, "特殊字符: 😀 ❤️ ★ ♪", fontsize=20)
plt.text(0.1, 0.2, "日语: こんにちは 韓国語: 안녕하세요", fontsize=16)
plt.title("字体回退测试")
plt.axis("off")
plt.tight_layout()
plt.show()
