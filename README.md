# 六国职业地图

交互式职业就业分布地图，覆盖印度、印度尼西亚、巴基斯坦、尼日利亚、肯尼亚和俄罗斯。方块面积表示就业人数；颜色可切换就业趋势、ISCO-08 职业技能等级、生成式 AI 暴露度和性别比例。

**2026-09 全面审查：** 修正印度取列与性别重复累计、趋势分母和统计断点；补齐来源哈希、覆盖率和发布校验。[完整审查记录](docs/review-2026-09.md) · [页面数据说明](site/data-methodology.html)。核查日期不代表就业数据已更新：官方实时接口当前返回 403。

## GenAI 指标：ILO 研究基准与本项目派生值

**2026-09 更新：已移除无来源的 0–10 预设评分表。** 当前使用 [Gmyrek 等（2025），ILO Working Paper 140](https://www.ilo.org/sites/default/files/2025-05/WP140_web.pdf) 及 [第一作者公开数据](https://github.com/pgmyrek/2025_GenAI_scores_ISCO08)。论文的技术基准是 **2025 年初**，不是 2026 年。

- 原始量表为 **0–1**；提取 427 个四位职业的公布均分、标准差和原始暴露梯度。
- 地图职业组参考均分 = 对应四位职业原始均分的**等权平均**。
- 国家参考均分 = 地图职业组参考均分按本国现有就业人数加权；仅纳入可匹配就业。
- 大多数国家只有两位职业就业数据，印度为三位。**组内没有本国四位就业权重**；没有另行假设国家 AI 采用率或修正系数。
- 页面展示组内细分分数范围、加权构成参考范围、匹配就业覆盖，并可点击职业组或使用下拉框审阅其原始四位分数及分档。
- 无匹配的数据用 null，保留就业面积、显示灰色，从均分分母剔除。当前印尼军人类别 01/02/03 未匹配，涉及 539,970 人。
- 页面数字分段只是颜色展示，不等于 ILO 暴露梯度；不再把自定义阈值转换为“高暴露就业人数”。

**这是可复核的研究参考，不是官方六国实测影响或失业预测。** 国家差异来自现有就业结构；国家调查年份、职业粒度、任务内容与采用条件均可能影响比较。完整说明见 [页面方法说明](site/ai-exposure-methodology.html) 和 [数据溯源](data/ilo_genai_2025/README.md)。

## 就业数据

| 国家 | 当前人数参考年 | 主要来源 | 地图职业粒度 |
| --- | --- | --- | --- |
| 印度 | 2024 | MOSPI PLFS / ILOSTAT | NCO-2015 三位 |
| 印尼 | 2023 | BPS Sakernas / ILOSTAT | ISCO-08 两位 |
| 巴基斯坦 | 2025 | PBS LFS / ILOSTAT | ISCO-08 两位 |
| 尼日利亚 | 2023 | NBS NLFS / ILOSTAT | ISCO-08 两位 |
| 肯尼亚 | 2022 | KNBS CHS / ILOSTAT | ISCO-08 两位 |
| 俄罗斯 | 2025 | Rosstat LFS / ILOSTAT | ISCO-08 两位 |

原始就业文件在 `ilostat_data/`，版本和 SHA-256 见 `data/employment_sources.json`。印度三位面积为 PLFS 全体就业百分比 × ILOSTAT 2024 总量的换算值，二者总体一致性尚未验证；三位性别只展示上级两位组的参考比例。其余国家保留调查职业人数。各国页面分别显示来源总量、图示规模、职业分类覆盖和 B/U 质量标记。

技能等级采用 ISCO-08 的四级定义，不是招聘学历要求或个人实际学历。巴基斯坦原趋势跨调查且存在统计断点，暂不计算；印度趋势截到 2024。印尼和尼日利亚仅展示明确标注的一位大类建模趋势参考。

## 运行与更新

```bash
# 安装锁定依赖（Python 3.10+；CI 使用 3.12）
uv sync --frozen

# 从已保存的权威职业分数刷新 AI 指标；Python 标准库即可，离线运行
python ai_exposure.py

# 校验权威工作簿后重新提取参考数据（仅更换来源时需要）
python scripts/import_ilo_genai.py /path/to/Final_Scores_ISCO08_Gmyrek_et_al_2025.xlsx

# 完整重建国家数据（需要 openpyxl 与 ilostat_data/ 中的输入）
uv run --frozen python build_country_data.py

# 本地预览
python -m http.server 8000 --directory site

# 验证数据与缺失值处理
uv run --frozen python -m unittest discover -s tests -v
uv run --frozen python build_country_data.py --check

# 检查在线就业数据是否变化（只输出检查结果，不替换已审核输入）
python scripts/check_source_updates.py --output /tmp/ilostat-update-check.json
```

完整重建先核对所有活跃输入的 SHA-256，输入变动必须先复核并更新来源清单。构建脚本可从任意工作目录执行，导入模块不会改写文件；`--check` 只校验，不写入。

完整国家重建同样调用 `ai_exposure.py` 中的统一函数，不会恢复旧预设分数。工作簿 URL、固定提交版本、SHA-256、字段名和转换方式保存在 `data/ilo_genai_2025/occupations.json`。

## 主要文件

| 文件 | 用途 |
| --- | --- |
| `ai_exposure.py` | 职业映射、等权汇总、就业加权、缺失值与覆盖率处理 |
| `scripts/import_ilo_genai.py` | 校验并导入原始工作簿，避免按任务重复计权 |
| `data/ilo_genai_2025/occupations.json` | 427 条原始职业参考分数和来源元数据 |
| `build_country_data.py` | 构建六国就业数据并附加 GenAI 指标 |
| `employment_data.py` | CSV 维度校验、源表总量分母、性别去重和趋势可比性 |
| `occupation_skills.py` | 官方 ISCO-08 技能等级映射 |
| `data/employment_sources.json` | 就业输入哈希、来源和更新核实状态 |
| `scripts/check_source_updates.py` | 只读线上变化检查 |
| `site/data.json` | 页面实际读取的数据与参考分数明细 |
| `site/index.html` | 职业地图、指标说明与原始分数明细弹窗 |
| `site/ai-exposure-methodology.html` | 可访问的数据来源和方法说明 |

GitHub Actions 校验源文件、16 项数据测试、重建一致性和 JS 语法后，从 `master` 的 `site/` 部署 GitHub Pages。功能分支修改需合入后才进入线上站点。

## 历史美国项目文件

原版美国 BLS 项目的 `score.py`、`scores.json`、`build_site_data.py` 等保留用于历史溯源；它们**不参与当前六国 AI 指标**。历史说明见 [legacy-us-readme.md](docs/legacy-us-readme.md)。旧 `build_site_data.py` 默认写入 `legacy-output/us-data.json`，并拒绝覆盖六国 `site/data.json`。
