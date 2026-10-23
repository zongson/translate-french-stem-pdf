# translate-french-stem-pdf

**把法语理工讲义制作成「左中文、右法语原版」的对照 PDF，保留公式、图表、版式与练习留白。**

A Codex skill for French STEM lecture notes: Chinese translation on the left, original French PDF on the right, at the original scale. Translation is performed by the agent; Python scripts handle extraction, layout, rendering and verification.

![原创示例：中文在左、法语原文在右](https://github.com/zongson/translate-french-stem-pdf/raw/bfee2565924fbf1b476f8bfd3ca696486eba831e/docs/demo/preview.svg)

[查看对照 PDF](docs/demo/dual.pdf) · [查看原创法语示例](docs/demo/source.pdf) · [技能入口](SKILL.md) · [清单格式](references/manifest-schema.md)

## 适用范围与具体用途

面向需要结合原文学习专业内容的中文读者，也适合整理课程资料和教师备课。输入以**法语、带可提取文字层的理工科 PDF** 为主，输出以保持原稿结构的中法对照讲义为主。

| 材料 / 场景 | 可以完成的工作 | 需要注意的条件 |
|---|---|---|
| 大学物理、力学、流体力学讲义 | 翻译定义、推导中的文字、图注、题目，保留原始方程与示意图 | 文字与公式重叠时需要精确遮罩 |
| 量子化学、原子结构等讲义 | 统一波函数、轨道、屏蔽等术语，保留上下标、希腊字母、能级图 | 优先保留源公式，避免从损坏文字层重建 |
| 数学与一般工程类课程 PDF | 翻译定理说明、条件、证明中的自然语言、表格文字 | 密集矩阵、复杂公式和多栏版面需要局部调整 |
| 习题单、课堂讲义和复习资料 | 翻译题干、表头与注释，保留题号、空白线和待填项目 | 默认不解题、不补答案 |
| 一次处理多份讲义 | 每份源文件分别生成对照 PDF，重复标签可复用译文 | 每份文件保留独立清单，避免混淆坐标和术语 |
| 含图片标签或少量扫描页的 PDF | 在可靠识别标签后用局部覆盖完成翻译 | 脚本不自带 OCR；扫描页需要另行识别和更充分的目视检查 |

不适合直接套用的场景：没有 PDF 交付要求的普通段落翻译、小说式自由重排、要求完全可编辑的 Word/PPT、需要自动解题的作业，以及希望对任意扫描件实现无人检查的一键翻译。其他源语言需要修改翻译规范和识别逻辑，不属于当前默认能力。

## 最终成果是什么样的

- **同页对照**：左侧中文，右侧直接嵌入法语源页；顺序、页数与源文件一致。
- **尺寸与比例**：每页宽度是对应源页的两倍，高度不变。A4 纵向源页对应约 A3 横向对照页，两侧保持源比例。
- **完整翻译文字**：正文、标题、页眉、表头、图注、图内法语说明均在翻译范围内；作者、专名、网址与纯数学记号可按语境保留。
- **保护教学内容**：保留公式、变量、单位、数值、图形、框线、题号、答题留白；疑似源稿错误另作提示，不擅自改题。
- **可搜索中文**：中文字体和使用到的数学字体嵌入 PDF；输出包含可检索中文，而非只有一张译文图片。
- **便于继续修订**：翻译清单记录译文及定位信息，后续可以只调整某个文本块或某一页。

上方的流体静力学示例由本仓库自行编写，包含标题、解释文字、带下标的公式、示意图标签和练习留白。示例展示的是排版产物，不是自动求解结果。仓库不包含实际课程讲义原件或旧案例全文。

## 已有案例与验证结果

工作流整理自量子化学、流体静力学、运动学、连续介质、向量分析等翻译实践。当前版本曾使用以下三份已有翻译清单重建检查，共 **28 页**：

| 案例 | 页数 | 可搜索中文字符数 | 当次 PDF 构建耗时 | 检查范围 |
|---|---:|---:|---:|---|
| 原子的量子模型 | 10 | 3,602 | 2.877 秒 | 全文程序检查，全部 10 页法语侧像素对比 |
| 流体静力学 | 7 | 1,029 | 0.792 秒 | 全文轻量检查，首尾法语侧像素对比 |
| 运动学 | 11 | 1,631 | 1.114 秒 | 全文轻量检查，首尾法语侧像素对比 |

三份案例的当次程序检查均无错误，另查看了代表页和复杂区域。耗时来自单次本地运行、已完成译文的重建过程，**不包含翻译、OCR、人工阅读与修改时间**，也不是跨设备性能承诺或译文准确率评分。实际案例文件不随仓库发布。

仓库另提供可复现的原创演示检查：验证可搜索中文、标题字号层级、法语侧一致性、重复应用译文不叠加，以及预览缓存复用。自动检查不能判断所有术语是否准确、图片标签是否漏译或每个区域是否美观，仍需重点页目视复核。

## 安装为全局 Codex skill

保留目录名和技能名 **`translate-french-stem-pdf`**。将本仓库克隆到 `$CODEX_HOME/skills/translate-french-stem-pdf`；没有设置 `CODEX_HOME` 时，使用 `~/.codex/skills/translate-french-stem-pdf`。

Windows PowerShell，首次安装：

```powershell
$skillsRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
git clone https://github.com/zongson/translate-french-stem-pdf.git (Join-Path $skillsRoot 'translate-french-stem-pdf')
python -m pip install -r (Join-Path $skillsRoot 'translate-french-stem-pdf/requirements.txt')
```

macOS / Linux，首次安装：

```bash
git clone https://github.com/zongson/translate-french-stem-pdf.git "${CODEX_HOME:-$HOME/.codex}/skills/translate-french-stem-pdf"
python3 -m pip install -r "${CODEX_HOME:-$HOME/.codex}/skills/translate-french-stem-pdf/requirements.txt"
```

已有同名本地技能时，先备份并确认其内容，再决定替换；如果已经是此仓库的 Git 克隆，可在保存本地改动后拉取更新。安装后在支持本地技能的 Codex 环境中新开会话，确认技能列表可见。

运行环境为 Python **3.10+**、PyMuPDF、Pillow；本地已在 Python 3.13、PyMuPDF 1.28.2、Pillow 11.1.0 上验证。Windows 建议命令带 `-X utf8`。其他系统的字体配置可能需要调整，未声称完成全部平台验证。

## 日常使用

向 Codex 提供 PDF 路径或附件，并明确调用：

```text
$translate-french-stem-pdf 翻译这份法语理工讲义，生成左中文、右法语原版的对照 PDF。
保留原有公式、图表和习题空白，不附解答。
```

也可以指定术语偏好或要求严查：

```text
$translate-french-stem-pdf 翻译这些流体力学讲义，masse volumique 统一译为“密度”。
请重点检查公式旁的说明文字；扫描页采用完整检查。
```

该 skill 是代理工作流与本地 PDF 工具的组合。**脚本本身不调用翻译 API，也不会自动生成译文**；语义翻译、术语选择和复杂区域定位由代理完成。使用 Codex 时相应模型服务的可用性与用量规则仍由宿主决定。

## 脚本工作流

以下命令在仓库根目录执行；其他位置调用时使用脚本绝对路径。`work/` 用于中间清单和预览，最终文件名可自行指定。

```bash
# 1. 提取文本块、生成紧凑翻译队列和源页预览
python -X utf8 scripts/prepare_manifest.py INPUT.pdf work/translations.json --render-dir work/source

# 2. 由代理阅读原稿和队列，准备 work/updates.json，再批量应用译文
python -X utf8 scripts/apply_translations.py work/translations.json work/updates.json

# 3. 构建对照 PDF
python -X utf8 scripts/build_dual_pdf.py INPUT.pdf work/translations.json OUTPUT_中文法语_dual.pdf

# 4. 全文件轻量检查，渲染代表页与总览
python -X utf8 scripts/verify_dual_pdf.py INPUT.pdf work/translations.json OUTPUT_中文法语_dual.pdf --render-dir work/final
```

译文更新示例，页号从 1 开始，块号以提取队列为准；`1:3` 仅作格式示例：

```json
{
  "source_translations": {"Définitions": "定义"},
  "blocks": {
    "1:3": "波函数描述系统的量子态。",
    "1:4": {"action": "preserve", "reason": "独立公式，保留原始绘制内容"}
  }
}
```

复杂页面可使用独立的 `mask_rects` 和 `text_rect`，在保护公式的同时安排中文；`preserved_regions` 恢复原始公式片段，`rotation` 处理旋转标签，富文本支持上下标。详细规则见 [manifest-schema.md](references/manifest-schema.md) 和 [translation-standards.md](references/translation-standards.md)。

修复某几页后，指定代表页预览即可；构建仍会生成整份 PDF，缓存减少的是重复预览渲染：

```bash
python -X utf8 scripts/verify_dual_pdf.py INPUT.pdf work/translations.json OUTPUT_中文法语_dual.pdf --render-dir work/final --pages 2,5-6
```

对扫描件、复杂公式重排、低质量来源或明确要求严查的任务，使用 `--full` 并逐页查看：

```bash
python -X utf8 scripts/verify_dual_pdf.py INPUT.pdf work/translations.json OUTPUT_中文法语_dual.pdf --render-dir work/final --full
```

构建生成同名 `.build.json`，记录源文件 / 清单 / 成品哈希、实际字号和放置位置；检查生成 `.qa.json`，记录缺字、字体嵌入、中文检索与法语侧对比等结果。它们用于本地修订，通常不必随成品一起交付。

## 快速复现示例

```bash
python -m pip install -r requirements.txt
python -X utf8 examples/build_demo.py
```

在 `examples/output/` 中生成原创 `source.pdf`、中法对照 `dual.pdf` 和 `preview.png`，同时执行最小回归检查。演示译文已写在脚本中，因此此步骤不需要翻译服务。目录中的个人讲义不会被读取。

## 速度、排版与准确性的取舍

| 目标 | 当前策略 |
|---|---|
| 减少翻译往返 | 紧凑队列按语义批量翻译，精确重复短语可复用译文 |
| 减少重复运行 | 更新按稳定标识替换，预览按页内容缓存；只修复已发现的问题 |
| 保持阅读层次 | 从源字号开始排版，保留标题大小；先改善排字框，再有限缩字 |
| 保护数学符号 | 优先保留源公式；必须重排时嵌入数学字体并检查缺字 |
| 避免过度检查 | 默认一次全文轻量检查 + 总览及代表页目视查看，复杂任务再启用完整模式 |

默认中文字体使用 PyMuPDF 自带的 Droid Sans Fallback。数学字体会尝试系统 Cambria / DejaVu Sans / Arial Unicode；找不到适合字体时，可以在清单的 `fonts.cjk`、`fonts.math` 指定本机路径。仓库不附第三方字体文件，依赖与字体遵循各自许可。

## 仓库结构

```text
SKILL.md                         技能入口、交付要求与默认流程
agents/openai.yaml               技能名称、界面提示和调用元数据
scripts/prepare_manifest.py      提取清单、队列和源页预览
scripts/apply_translations.py    批量应用译文与局部排版更新
scripts/build_dual_pdf.py        构建原比例中法对照 PDF
scripts/verify_dual_pdf.py       程序检查和预览缓存
scripts/dual_common.py           字体、清单与预览共用逻辑
references/                     清单规范及翻译排版标准
examples/build_demo.py           原创示例生成与可运行检查
docs/demo/                      已生成的原创 PDF 与效果图
```
