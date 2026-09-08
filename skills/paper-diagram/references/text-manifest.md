# 可编辑文字清单（离线）

图片中的文字可以作为轮廓保留，也可以经过 Agent 或人工审核后恢复为 SVG `<text>`。后者能够修改文字内容，但 OCR、字体替代与公式识别仍可能造成误差。

## 坐标和示例

所有坐标、字号均为**按 EXIF 方向转正后的原图显示像素**，左上角为 `(0, 0)`。宽高也使用转正后的尺寸。SVG 必须保持相同画布：`viewBox="0 0 image_width image_height"`，不得裁剪或拉伸后直接复用清单。

```json
{
  "schema_version": "1.0",
  "image_width": 1189,
  "image_height": 404,
  "text_elements": [
    {
      "id": "graph-one-label",
      "content": "Graph #1",
      "bbox": [199, 29, 64, 21],
      "x": 200,
      "y": 45,
      "font_family": "Times New Roman",
      "font_size": 17,
      "font_weight": "normal",
      "font_style": "normal",
      "fill": "#000000",
      "background": "#f1f1f1",
      "reviewed": true
    }
  ]
}
```

示例坐标仅用于解释格式，不能替代对实际图片的审核。

- `bbox` 为 `[left, top, width, height]`，表示需要去除原文字的区域。右、下边界不包含在区域内；小数坐标向外取整。
- `x` 是文本起始位置；`y` 是**首行基线**，不是文字框顶边。
- `font_size` 是实际像素字号。首版不支持 `text_width` / `textLength`，避免导入其他软件后宽度失效。
- `background` 必须显式提供不透明 `#RGB` 或 `#RRGGBB`；不能自动从邻近像素猜测。
- `reviewed` 必须为布尔值 `true`。未经审核的清单在去字与回填时均会被拒绝。
- `id` 必须以英文字母或 `_` 开头，后续可使用字母、数字、`_`、`.`、`-`，并且在清单和 SVG 内唯一。
- 多行 `content` 使用 `\n`；每行生成独立 `<text>`。可选 `line_height` 默认 `1.2`，表示行距为字号的倍数。尽量使用每行一项，以便精确控制每行的擦除框和基线。
- 对上下标和复杂公式，建议保留路径，或将基符号和上下标分成独立文字项，分别标注字号与基线。首版不自动进行 LaTeX 排版。

## 审核必须检查的实际内容

在原图上逐项核对：内容、框、基线、颜色、字体、字号。框必须完整覆盖目标文字及其抗锯齿边缘，并且**只包含这段文字和干净的纯色背景，不得跨过连线、箭头、图标、边框或其他文字**。背景不纯或存在遮挡时，不应将该项标记为已审核；保留原区域的轮廓，或者先单独修复并验证图形。

程序仅检查字段与几何边界是否合法，**不会证明背景确实是纯色、不会检查文本实际渲染宽度，也不会判断你对 `reviewed:true` 的确认是否正确**。填充一旦覆盖线条，后续矢量化无法恢复它。

操作流程：

1. 可选：用本地已安装的 Tesseract 生成 OCR 草稿。
2. Agent 检查每一项，修正内容与实际字体参数，明确背景色，只对符合条件的项设置 `reviewed:true`；移除无法安全擦除的项。
3. 调用 `prepare_text_image(original, manifest, cleaned_png)`，生成去字 PNG，保留原图。
4. 检查去字结果没有损伤图形，再对它运行本地矢量化。
5. 调用 `restore_text(vector_svg, manifest, editable_svg)`，回填文字，保留已有路径。
6. 在实际编辑器和渲染结果中验证文字位置、字体可用性、上下标与换行。字体须在用户电脑安装，否则编辑器可能替换字体。

## 可复用 Python API

```python
from cell_local.text import generate_ocr_draft, prepare_text_image, restore_text

generate_ocr_draft("figure.png", "text-draft.json", lang="eng")
# 此时停止自动处理。经 Agent/人工逐项审核另存为 text-reviewed.json 后：
prepare_text_image("figure.png", "text-reviewed.json", "cleaned.png")
# 调用本地图片转 SVG，再：
restore_text("geometry.svg", "text-reviewed.json", "editable.svg")
```

OCR 为可选功能，使用本机 `tesseract` CLI，不安装或下载语言模型，不请求任何网络服务。草稿中的 `background:null`、`reviewed:false` 是有意设计；OCR 给出的字号与基线是近似值，不能原样批量批准。源图片和源 SVG 不会被这两个 API 原地覆盖。清单、SVG 尺寸、ID、坐标、空内容、非法数值或审核状态不合法时，操作报错且不生成结果文件。
