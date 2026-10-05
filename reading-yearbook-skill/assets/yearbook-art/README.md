# 纸本艺术素材

- `hero-book.png`：本次通过imagegen生成的原创透明插画，红蜡笔书页、蓝色眼镜与花枝；不含真实书封或数据。网页和Canvas共享一次内嵌的图片。
- `reading.png`、`rhythm.png`：本机Gabriola排印的固定装饰字样，完整保留花体边界。未分发系统字体文件。再生成时运行`scripts/create_display_lettering.py`，需要本机字体及支持RAQM的Pillow；日常构建不需要Pillow。

这是当前认可原型的视觉版本，不是所有书目的唯一风格。按材料与认可方向制作新插画后，用`--art-assets`覆盖hero/reading/rhythm，透明素材继续与真实文字、真实书封分离。图表代码的PolyForm许可另见`assets/lieflat-LICENSE.txt`。
