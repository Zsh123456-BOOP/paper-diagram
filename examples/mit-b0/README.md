# MiT-B0 对比案例

三张 PNG 是用户提供的截图，顺序固定为：

1. `01-with-paper-diagram.png`：使用本项目的前身 cell-local。
2. `02-without-paper-diagram.png`：未使用 cell-local，使用通用 Presentations / PPTX 工具。
3. `03-reference.png`：用户提供的原始参考图。

两份公开 PPTX 对应用户提供的文件：

| 公开文件 | 用户提供的文件名 | 方法 |
| --- | --- | --- |
| [with-paper-diagram.pptx](with-paper-diagram.pptx) | MiT-B0_recreated.pptx | 使用本项目 skill 的前身 |
| [without-paper-diagram.pptx](without-paper-diagram.pptx) | MiT-B0-faithful-editable.pptx | 通用 PPTX 工具 |

公开副本已移除文档作者等元数据及演讲备注文字；幻灯片 XML 与嵌入媒体保持不变。PNG 保留用户提供的截图，不是对清理后 PPTX 的统一环境重新渲染。[manifest.json](manifest.json) 记录公开 PPTX 的 SHA-256 和对象数量。

对象统计读取 `ppt/slides/slide1.xml`：原生形状为 `p:sp`，文本对象为包含非空 `a:t` 的形状，分组为 `p:grpSp`，图片为 `p:pic`。文本是原生形状的子集，不能把表中各项直接相加当成总对象数。

这是一个用户授权公开的案例；不是对原论文模型的实验验证。不同运行的模型、提示词与字体环境未统一控制，当前发布版本也未重新运行此案例。因此只用于观察复刻结果和可编辑结构，不据此宣称性能提升百分比、普遍优于某模型或严格 1:1。代码许可见仓库 LICENSE；示例图与模型内容不用于主张对任何第三方素材的所有权。
