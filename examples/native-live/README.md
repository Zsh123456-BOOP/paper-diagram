# 原生实时绘制小图

本例验证实时对象创建，不是参考图复刻基准。`make_demo.py` 创建一个示意 Attention 模块，包含输入叠层、Q/K/V、圆角模块、独立矩阵单元、折线箭头与三次曲线。

从仓库根目录运行，提供本机已有的字体文件：

```sh
python -m pip install -e .
python examples/native-live/make_demo.py --output-dir /your/new-scene --font /your/font.ttf
python skills/paper-diagram/scripts/run.py live /your/new-scene/scene.json --output-dir /your/new-live-run --interval 0.3
```

导入 `PaperDiagramLive.bas` 后，在 PowerPoint 正常编辑窗口运行 `PaperDiagramDraw`。每次运行都会另建新演示文稿。此小图有 74 个创建/分组步骤，配置的步骤间隔共约 22 秒，实际总时长还取决于 PowerPoint 执行与刷新速度。

已在 Mac PowerPoint 16.112.3 观察到从空白到局部再到完整图的刷新，并检查实际保存的 PPTX：50 个原生形状，含 19 个文本对象，16 个分组，17 段三次曲线，8 个箭头，0 个图片对象。输入叠层及其标签可以整体移动。VBA 由同一绘图计划生成，未使用隐藏完成图或位图动画。

Windows 未在本次实机测试。实时模式支持范围和限制见[实时绘图说明](../../skills/paper-diagram/references/live-powerpoint.md)。视频捕获与剪辑尚未集成到工具。
