# 六国职业地图

交互式职业就业分布地图，覆盖印度、印度尼西亚、巴基斯坦、尼日利亚、肯尼亚和俄罗斯。方块面积表示就业人数；颜色可切换就业趋势、学历要求、生成式 AI 暴露度和性别比例。

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

原始就业文件在 `ilostat_data/`，来源链接见各国页面及 `build_country_data.py`。本次 GenAI 更新沿用现有就业人数、趋势、学历和性别字段。学历字段是职业要求的映射，并非个人实际学历调查结果。

## 运行与更新

```bash
# 从已保存的权威职业分数刷新 AI 指标；Python 标准库即可，离线运行
python ai_exposure.py

# 校验权威工作簿后重新提取参考数据（仅更换来源时需要）
python scripts/import_ilo_genai.py /path/to/Final_Scores_ISCO08_Gmyrek_et_al_2025.xlsx

# 完整重建国家数据（需要 openpyxl 与 ilostat_data/ 中的输入）
python build_country_data.py

# 本地预览
python -m http.server 8000 --directory site

# 验证数据与缺失值处理
python -m unittest discover -s tests -v
```

完整国家重建同样调用 `ai_exposure.py` 中的统一函数，不会恢复旧预设分数。工作簿 URL、固定提交版本、SHA-256、字段名和转换方式保存在 `data/ilo_genai_2025/occupations.json`。

## 主要文件

| 文件 | 用途 |
| --- | --- |
| `ai_exposure.py` | 职业映射、等权汇总、就业加权、缺失值与覆盖率处理 |
| `scripts/import_ilo_genai.py` | 校验并导入原始工作簿，避免按任务重复计权 |
| `data/ilo_genai_2025/occupations.json` | 427 条原始职业参考分数和来源元数据 |
| `build_country_data.py` | 构建六国就业数据并附加 GenAI 指标 |
| `site/data.json` | 页面实际读取的数据与参考分数明细 |
| `site/index.html` | 职业地图、指标说明与原始分数明细弹窗 |
| `site/ai-exposure-methodology.html` | 可访问的数据来源和方法说明 |

GitHub Actions 从 `master` 的 `site/` 部署 GitHub Pages。功能分支修改需合入后才进入线上站点。

## 历史美国项目文件

原版美国 BLS 项目的 `score.py`、`scores.json`、`build_site_data.py` 等保留用于历史溯源；它们**不参与当前六国 AI 指标**。历史说明见 [legacy-us-readme.md](docs/legacy-us-readme.md)。不要运行旧 `build_site_data.py` 覆盖六国页面数据。
