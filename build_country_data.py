#!/usr/bin/env python3
"""Rebuild the six-country map offline from reviewed, checksum-pinned inputs."""
import argparse
import json
from pathlib import Path
import openpyxl
from ai_exposure import apply_ai_exposure
from employment_data import (ROOT, DATA, read_observations, year_rows, total_value,
                             sex_fields, gender_summary, survey_changes, model_changes, verify_snapshot)
from occupation_skills import SKILL_SYSTEM, skill_fields

# ─── ISCO-08 Occupation Names (Chinese + English) ───────────────────────

ISCO_L1_NAMES = {
    '1': ('管理人员', 'Managers'),
    '2': ('专业人员', 'Professionals'),
    '3': ('技术员和助理专业人员', 'Technicians & Associate Professionals'),
    '4': ('文职支持人员', 'Clerical Support Workers'),
    '5': ('服务和销售人员', 'Service & Sales Workers'),
    '6': ('农林渔业技术工人', 'Skilled Agricultural/Forestry/Fishery Workers'),
    '7': ('手工艺及相关行业工人', 'Craft & Related Trades Workers'),
    '8': ('工厂操作员和装配工', 'Plant/Machine Operators & Assemblers'),
    '9': ('基层职业', 'Elementary Occupations'),
    '0': ('军人', 'Armed Forces Occupations'),
}

ISCO_L2_NAMES = {
    '01': ('军官', 'Commissioned Armed Forces Officers'),
    '02': ('军士', 'Non-commissioned Armed Forces Officers'),
    '03': ('其他军人', 'Armed Forces Occupations, Other Ranks'),
    '11': ('首席执行官/高级官员/立法者', 'Chief Executives/Senior Officials/Legislators'),
    '12': ('行政和商务经理', 'Administrative & Commercial Managers'),
    '13': ('生产和专业服务经理', 'Production & Specialized Services Managers'),
    '14': ('酒店/零售及其他服务经理', 'Hospitality/Retail/Other Services Managers'),
    '21': ('科学和工程专业人员', 'Science & Engineering Professionals'),
    '22': ('卫生专业人员', 'Health Professionals'),
    '23': ('教学专业人员', 'Teaching Professionals'),
    '24': ('商业和行政专业人员', 'Business & Administration Professionals'),
    '25': ('信息通信技术专业人员', 'ICT Professionals'),
    '26': ('法律/社会/文化专业人员', 'Legal/Social/Cultural Professionals'),
    '31': ('科学和工程助理专业人员', 'Science & Engineering Associate Professionals'),
    '32': ('卫生助理专业人员', 'Health Associate Professionals'),
    '33': ('商业和行政助理专业人员', 'Business & Administration Associate Professionals'),
    '34': ('法律/社会/文化助理专业人员', 'Legal/Social/Cultural Associate Professionals'),
    '35': ('信息通信技术技术员', 'ICT Technicians'),
    '41': ('一般文职人员', 'General & Keyboard Clerks'),
    '42': ('客户服务人员', 'Customer Services Clerks'),
    '43': ('数字记录和材料记录人员', 'Numerical & Material Recording Clerks'),
    '44': ('其他文职支持人员', 'Other Clerical Support Workers'),
    '51': ('个人服务人员', 'Personal Service Workers'),
    '52': ('销售人员', 'Sales Workers'),
    '53': ('个人护理人员', 'Personal Care Workers'),
    '54': ('保安服务人员', 'Protective Services Workers'),
    '61': ('面向市场的农业技术工人', 'Market-oriented Skilled Agricultural Workers'),
    '62': ('面向市场的林渔猎技术工人', 'Market-oriented Skilled Forestry/Fishery/Hunting Workers'),
    '63': ('自给型农林渔业劳动者', 'Subsistence Farmers/Fishers/Hunters/Gatherers'),
    '71': ('建筑和相关行业工人', 'Building & Related Trades Workers'),
    '72': ('金属/机械及相关行业工人', 'Metal/Machinery & Related Trades Workers'),
    '73': ('手工艺和印刷工人', 'Handicraft & Printing Workers'),
    '74': ('电气和电子行业工人', 'Electrical & Electronic Trades Workers'),
    '75': ('食品加工/木工/服装及相关工人', 'Food Processing/Woodworking/Garment Workers'),
    '81': ('固定设备和机器操作员', 'Stationary Plant & Machine Operators'),
    '82': ('装配工', 'Assemblers'),
    '83': ('驾驶员和移动设备操作员', 'Drivers & Mobile Plant Operators'),
    '91': ('清洁工和帮佣', 'Cleaners & Helpers'),
    '92': ('农林渔业劳工', 'Agricultural/Forestry/Fishery Labourers'),
    '93': ('采矿/建筑/制造/运输劳工', 'Mining/Construction/Manufacturing/Transport Labourers'),
    '94': ('食品加工助理', 'Food Preparation Assistants'),
    '95': ('街头和相关销售服务人员', 'Street & Related Sales & Service Workers'),
    '96': ('垃圾收集和其他基层工人', 'Refuse Workers & Other Elementary Workers'),
}

# India NCO-2015 3-digit names (≈ ISCO-08 minor groups)
ISCO_L3_NAMES = {
    '111': ('立法者和高级官员', 'Legislators & Senior Officials'), '112': ('总经理和执行董事', 'Managing Directors & Chief Executives'),
    '121': ('商务服务和行政经理', 'Business Services & Administration Managers'), '122': ('销售/市场/开发经理', 'Sales/Marketing/Development Managers'),
    '131': ('农林渔业生产经理', 'Production Managers in Agriculture/Forestry/Fisheries'), '132': ('制造/采矿/建筑/物流经理', 'Manufacturing/Mining/Construction/Distribution Managers'),
    '133': ('信息通信技术服务经理', 'ICT Service Managers'), '134': ('专业服务经理', 'Professional Services Managers'),
    '141': ('酒店和餐饮经理', 'Hotel & Restaurant Managers'), '142': ('零售和批发贸易经理', 'Retail & Wholesale Trade Managers'),
    '143': ('其他服务经理', 'Other Services Managers'),
    '211': ('物理和地球科学专业人员', 'Physical & Earth Science Professionals'), '212': ('数学/精算/统计专业人员', 'Mathematicians/Actuaries/Statisticians'),
    '213': ('生命科学专业人员', 'Life Science Professionals'), '214': ('工程专业人员（不含电气电子）', 'Engineering Professionals (excl. Electrotechnology)'),
    '215': ('电气工程专业人员', 'Electrotechnology Engineers'), '216': ('建筑师/规划师/测量师/设计师', 'Architects/Planners/Surveyors/Designers'),
    '221': ('医生', 'Medical Doctors'), '222': ('护理和助产专业人员', 'Nursing & Midwifery Professionals'),
    '223': ('传统医学和替代医学专业人员', 'Traditional & Complementary Medicine Professionals'), '224': ('急救医师和护理人员', 'Paramedical Practitioners'),
    '225': ('兽医', 'Veterinarians'), '226': ('其他卫生专业人员', 'Other Health Professionals'),
    '231': ('大学和高等教育教师', 'University & Higher Education Teachers'), '232': ('职业教育教师', 'Vocational Education Teachers'),
    '233': ('中学教师', 'Secondary Education Teachers'), '234': ('小学和学前教师', 'Primary School & Early Childhood Teachers'),
    '235': ('其他教学专业人员', 'Other Teaching Professionals'),
    '241': ('财务专业人员', 'Finance Professionals'), '242': ('行政专业人员', 'Administration Professionals'),
    '243': ('销售/市场/公关专业人员', 'Sales/Marketing/Public Relations Professionals'),
    '251': ('软件和应用开发人员/分析师', 'Software & Applications Developers & Analysts'), '252': ('数据库和网络专业人员', 'Database & Network Professionals'),
    '261': ('法律专业人员', 'Legal Professionals'), '262': ('图书馆和档案专业人员', 'Librarians & Related Information Professionals'),
    '263': ('社会和宗教专业人员', 'Social & Religious Professionals'), '264': ('作者/记者/语言学家', 'Authors/Journalists/Linguists'),
    '265': ('创意和表演艺术家', 'Creative & Performing Artists'),
    '311': ('物理和工程科学技术员', 'Physical & Engineering Science Technicians'), '312': ('采矿/制造/建筑监督员', 'Mining/Manufacturing/Construction Supervisors'),
    '313': ('过程控制技术员', 'Process Control Technicians'), '314': ('生命科学技术员和相关助理', 'Life Science Technicians & Related Associates'),
    '315': ('船舶和航空控制及技术员', 'Ship & Aircraft Controllers & Technicians'),
    '321': ('医学和药学技术员', 'Medical & Pharmaceutical Technicians'), '322': ('护理和助产助理专业人员', 'Nursing & Midwifery Associate Professionals'),
    '323': ('传统医学和替代医学助理', 'Traditional & Complementary Medicine Associate Professionals'), '324': ('兽医技术员和助理', 'Veterinary Technicians & Assistants'),
    '325': ('其他卫生助理专业人员', 'Other Health Associate Professionals'),
    '331': ('金融和数学助理专业人员', 'Financial & Mathematical Associate Professionals'), '332': ('销售和采购代理/经纪人', 'Sales & Purchasing Agents & Brokers'),
    '333': ('商业服务代理', 'Business Services Agents'), '334': ('行政和专业秘书', 'Administrative & Specialized Secretaries'),
    '335': ('政府监管助理专业人员', 'Government Regulatory Associate Professionals'),
    '341': ('法律/社会助理专业人员', 'Legal/Social Associate Professionals'), '342': ('体育和健身工作者', 'Sports & Fitness Workers'),
    '343': ('艺术/文化/烹饪助理专业人员', 'Artistic/Cultural/Culinary Associate Professionals'),
    '351': ('信息通信技术运营技术员', 'ICT Operations Technicians'), '352': ('通信技术员', 'Telecommunications Technicians'),
    '411': ('一般办事员', 'General Office Clerks'), '412': ('秘书（一般）', 'Secretaries (General)'),
    '413': ('键盘操作员', 'Keyboard Operators'),
    '421': ('出纳员和相关人员', 'Tellers/Money Collectors & Related Clerks'), '422': ('客户信息工作者', 'Client Information Workers'),
    '431': ('数字记录和会计人员', 'Numerical Clerks'), '432': ('材料记录和运输人员', 'Material Recording & Transport Clerks'),
    '441': ('其他文职支持人员', 'Other Clerical Support Workers'),
    '511': ('旅行服务员/乘务员/导游', 'Travel Attendants/Conductors/Guides'), '512': ('厨师', 'Cooks'),
    '513': ('服务员和酒吧侍应', 'Waiters & Bartenders'), '514': ('理发师/美容师及相关人员', 'Hairdressers/Beauticians & Related Workers'),
    '515': ('建筑和家务管理人员', 'Building & Housekeeping Supervisors'), '516': ('其他个人服务人员', 'Other Personal Services Workers'),
    '521': ('街头和市场销售人员', 'Street & Market Salespersons'), '522': ('商店销售人员', 'Shop Salespersons'),
    '523': ('收银员和售票员', 'Cashiers & Ticket Clerks'), '524': ('其他销售人员', 'Other Sales Workers'),
    '531': ('儿童看护人员', 'Child Care Workers'), '532': ('个人护理人员（卫生机构）', 'Personal Care Workers in Health Services'),
    '541': ('保安人员', 'Protective Services Workers'),
    '611': ('市场园艺师和作物种植者', 'Market Gardeners & Crop Growers'), '612': ('畜牧工人', 'Animal Producers'),
    '613': ('混合作物和畜牧农民', 'Mixed Crop & Animal Producers'),
    '621': ('林业和相关工人', 'Forestry & Related Workers'), '622': ('渔业工人/猎人/捕猎者', 'Fishery Workers/Hunters/Trappers'),
    '631': ('自给型作物种植者', 'Subsistence Crop Farmers'), '632': ('自给型畜牧者', 'Subsistence Livestock Farmers'),
    '633': ('自给型混合种植和畜牧者', 'Subsistence Mixed Crop & Livestock Farmers'), '634': ('自给型渔民/猎人/采集者', 'Subsistence Fishers/Hunters/Gatherers'),
    '711': ('建筑结构及相关工人', 'Building Frame & Related Trades Workers'), '712': ('建筑装修和相关工人', 'Building Finishers & Related Trades Workers'),
    '713': ('油漆工/建筑物清洁工及相关', 'Painters/Building Structure Cleaners & Related'),
    '721': ('钣金工/结构金属工及相关', 'Sheet & Structural Metal Workers & Related'), '722': ('铁匠/锻工和相关工具制造工', 'Blacksmiths/Toolmakers & Related'),
    '723': ('机械装配工和修理工', 'Machinery Mechanics & Repairers'),
    '731': ('手工艺工人', 'Handicraft Workers'), '732': ('印刷行业工人', 'Printing Trades Workers'),
    '741': ('电气设备安装和修理工', 'Electrical Equipment Installers & Repairers'), '742': ('电子和通信安装/修理工', 'Electronics & Telecommunications Installers'),
    '751': ('食品加工及相关行业工人', 'Food Processing & Related Trades Workers'), '752': ('木材加工工人/家具制造工', 'Wood Treaters/Cabinet-makers'),
    '753': ('服装及相关行业工人', 'Garment & Related Trades Workers'), '754': ('其他手工艺和相关行业工人', 'Other Craft & Related Workers'),
    '811': ('采矿和矿物加工设备操作员', 'Mining & Mineral Processing Plant Operators'), '812': ('金属加工和精加工设备操作员', 'Metal Processing & Finishing Plant Operators'),
    '813': ('化工和照相制品设备操作员', 'Chemical & Photographic Products Plant Operators'), '814': ('橡胶/塑料/纸张产品机器操作员', 'Rubber/Plastic/Paper Products Machine Operators'),
    '815': ('纺织/皮革/毛皮产品机器操作员', 'Textile/Fur/Leather Products Machine Operators'), '816': ('食品和相关产品机器操作员', 'Food & Related Products Machine Operators'),
    '817': ('木材加工和造纸机器操作员', 'Wood Processing & Papermaking Plant Operators'), '818': ('其他固定设备和机器操作员', 'Other Stationary Plant & Machine Operators'),
    '821': ('装配工', 'Assemblers'),
    '831': ('火车司机和相关人员', 'Locomotive Engine Drivers & Related'), '832': ('汽车/货车/摩托车驾驶员', 'Car/Van/Motorcycle Drivers'),
    '833': ('重型卡车和客车驾驶员', 'Heavy Truck & Bus Drivers'), '834': ('移动设备操作员', 'Mobile Plant Operators'),
    '835': ('船舶甲板船员及相关人员', 'Ships Deck Crews & Related'),
    '911': ('家庭/酒店/办公室清洁工和帮手', 'Domestic/Hotel/Office Cleaners & Helpers'), '912': ('车辆/窗户/洗衣及其他手工清洁工', 'Vehicle/Window/Laundry & Other Hand Cleaning Workers'),
    '921': ('农林渔业劳工', 'Agricultural/Forestry/Fishery Labourers'),
    '931': ('采矿和建筑劳工', 'Mining & Construction Labourers'), '932': ('制造业劳工', 'Manufacturing Labourers'),
    '933': ('运输和仓储劳工', 'Transport & Storage Labourers'),
    '941': ('食品加工助理', 'Food Preparation Assistants'),
    '951': ('街头和相关服务工人', 'Street & Related Service Workers'), '952': ('街头小贩（不含食品）', 'Street Vendors (excl. Food)'),
    '961': ('垃圾收集工人', 'Refuse Workers'), '962': ('其他基层工人', 'Other Elementary Workers'),
}


COUNTRIES = {
    "IND": {"cn": "印度", "en": "India", "year": "2024", "survey": "MOSPI PLFS / ILOSTAT", "trend": ("2022", "2024")},
    "NGA": {"cn": "尼日利亚", "en": "Nigeria", "year": "2023", "survey": "NBS NLFS / ILOSTAT", "model": True},
    "IDN": {"cn": "印度尼西亚", "en": "Indonesia", "year": "2023", "survey": "BPS Sakernas / ILOSTAT", "model": True},
    "RUS": {"cn": "俄罗斯", "en": "Russia", "year": "2025", "survey": "Rosstat LFS / ILOSTAT", "trend": ("2020", "2025")},
    "PAK": {"cn": "巴基斯坦", "en": "Pakistan", "year": "2025", "survey": "PBS LFS / ILOSTAT"},
    "KEN": {"cn": "肯尼亚", "en": "Kenya", "year": "2022", "survey": "KNBS CHS / ILOSTAT", "trend": ("2021", "2022")},
}
TREND_NOTES = {
    "IND": "2022–2024 年 ILOSTAT 两位职业组的份额变化；三位职业沿用上级组参考值。2025 年 PLFS 改变抽样设计和统计周期，本次不跨该调整拼接趋势。",
    "NGA": "2020–2025 年 ILO 建模的一位职业大类份额变化；同一大类内各方块共用参考值，不是两位职业的调查变化。",
    "IDN": "本地快照仅有 2023 年 ISCO-08 两位调查。颜色采用 2020–2025 年 ILO 建模的一位职业大类参考变化，不是两位职业的调查变化。",
    "RUS": "2020–2025 年同名 Rosstat LFS 两位职业组的份额变化，分母为来源公布的全部就业人数。仍需注意各期调查范围。",
    "PAK": "原 2020–2025 趋势混用了 HIES 与 LFS，且 2020 年带统计断点标记，已暂停。2024–25 调查还发布不同 ICLS 定义，须核实一致口径后恢复。",
    "KEN": "2021–2022 年两位职业组的份额变化，以包括未分类就业的官方总量为分母。两期职业覆盖不完整；U 标记或缺失端点不计算趋势。",
}
EMPLOYMENT_NOTES = {
    "IND": "三位职业面积来自 PLFS 2023–24 表 25 第 10 列（城乡合计 person）× ILOSTAT 2024 就业总量。两来源的就业定义和总体未完成一致性核验，因此人数只作规模换算；原始百分比才是该表公布值。不可当作官方三位职业人数。",
    "NGA": "沿用 2023 年快照；2024 年快照约 23.3% 就业归为未分类。保留源表 B（统计断点）和 U（低可靠性）标记。",
    "IDN": "沿用本地已保存的 2023 年 ISCO-08 调查快照；这不表示 BPS 此后没有发布新版调查。",
    "RUS": "沿用本地已保存的 2025 年两位职业调查快照；人数保留原调查覆盖口径。",
    "PAK": "沿用本地已保存的 2025 年两位职业快照；未分类就业保留在覆盖率分母，不当成某个已分类职业。",
    "KEN": "图中只展示有职业人数的分类；来源总量中的约 254 万人未归入图示职业，不能把图示人数当作全国全部就业。",
}


def india_distribution(path=DATA / "India_PLFS_Table25.xlsx"):
    """Published person percentages, never the male distribution or sample counts."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb["Sheet1"]
        if ws.cell(3, 8).value != "rural + urban" or ws.cell(4, 10).value != "person":
            raise ValueError("PLFS Table 25 column layout changed")
        result = {}
        for row in ws.iter_rows(min_row=6, values_only=True):
            code = str(row[0]).strip()
            if not (code.isdigit() and len(code) == 3):
                continue
            value = row[9]
            if not isinstance(value, (int, float)) or not 0 <= value <= 100:
                raise ValueError(f"Invalid person percentage: {code}")
            if code in result:
                raise ValueError(f"Duplicate PLFS occupation: {code}")
            result[code] = value
        if not 99.5 <= sum(result.values()) <= 100.5:
            raise ValueError("PLFS person percentages do not sum to approximately 100")
        return result
    finally:
        wb.close()


def occupation(code, jobs, year, observations, trends, india=False):
    major, parent = code[0], code[:2]
    names = ISCO_L3_NAMES if india else ISCO_L2_NAMES
    title, english = names.get(code, (f"职业代码 {code}", f"Occupation {code}"))
    trend = trends.get(parent) or trends.get(major) or {}
    row = observations.get((year, "SEX_T", parent), {})
    record = {
        "title": title, "title_en": english, "code": code,
        "category": f"{major}-{ISCO_L1_NAMES[major][0]}", "jobs": jobs,
        "jobs_year": year, "jobs_method": "scaled_plfs_person_share" if india else "survey_l2",
        "jobs_status": [] if india else list(filter(None, [row.get("status")])),
        "share_change": trend.get("change"),
        "share_change_desc": f"{trend['year_from']}–{trend['year_to']}" if trend else "",
        "share_change_method": trend.get("method", "unavailable"),
        "share_change_reference_code": trend.get("reference_code"),
        **sex_fields(observations, year, parent, inherited=india),
        **skill_fields(code),
    }
    return record


def build_country(cc, manifest):
    config = COUNTRIES[cc]
    year = config["year"]
    observations = read_observations(cc)
    published_total = total_value(observations, year)
    levels = year_rows(observations, year)
    if config.get("model"):
        trends = model_changes(cc)
    elif config.get("trend"):
        trends = survey_changes(observations, *config["trend"])
    else:
        trends = {}
    if cc == "IND":
        percentages = india_distribution()
        rows = [dict(occupation(code, round(published_total * pct / 100), year, observations, trends, True),
                     published_person_share=pct)
                for code, pct in percentages.items() if pct > 0]
    else:
        rows = [occupation(code, round(row["value"]), year, observations, trends)
                for code, row in sorted(levels.items()) if code.isdigit() and row["value"] is not None and row["value"] > 0]
    total = sum(r["jobs"] for r in rows)
    listed = sum(r["value"] for code, r in levels.items() if code.isdigit() and r["value"] is not None)
    coverage = min(100, listed / published_total * 100)
    unclassified = levels.get("X", {}).get("value")
    sex_codes = {r["code"][:2] for r in rows}
    source_url = f"https://sdmx.ilo.org/rest/data/ILO,DF_EMP_TEMP_SEX_OC2_NB/{cc}.A..SEX_T+SEX_M+SEX_F.?format=csv&startPeriod=2015"
    source_files = [i for i in manifest["files"] if Path(i["path"]).name.startswith(cc) or (cc == "IND" and i["path"].endswith(".xlsx"))]
    links = [{"label": "ILOSTAT 原始 CSV（含男女、总量及质量标记）", "url": source_url},
             {"label": "数据口径与更新记录", "url": "data-methodology.html"},
             {"label": "ILOSTAT 职业数据入口", "url": f"https://rshiny.ilo.org/dataexplorer56/?lang=en&id=EMP_TEMP_SEX_OC2_NB_A&ref_area={cc}"}]
    if cc == "IND":
        links.insert(0, {"label": "MOSPI PLFS 2023–24 原表（表 25）", "url": "https://www.mospi.gov.in/sites/default/files/publication_reports/AnnualReport_PLFS2023-24L2.pdf"})
    if config.get("model"):
        links.append({"label": "ILO 大类建模趋势原始数据", "url": source_files[-1]["source_url"]})
    # Major-group share changes are sums of component share differences, not an
    # employment-weighted average of those differences. Model L1 values appear once.
    major_changes = []
    if config.get("model"):
        major_changes = [{"category": f"{code}-{ISCO_L1_NAMES[code][0]}", **t} for code, t in sorted(trends.items())]
    elif trends:
        start, end = config["trend"]
        a, b = year_rows(observations, start), year_rows(observations, end)
        for major in ISCO_L1_NAMES:
            codes = {code for code in a.keys() | b.keys() if code.isdigit() and code.startswith(major)}
            if not codes or not codes.issubset(trends):
                continue
            change = 100 * (sum(b[c]["value"] for c in codes) / total_value(observations, end)
                            - sum(a[c]["value"] for c in codes) / total_value(observations, start))
            major_changes.append({"category": f"{major}-{ISCO_L1_NAMES[major][0]}", "change": round(change, 2)})
    return {
        "name_cn": config["cn"], "name_en": config["en"], "title": config["cn"] + "职业地图",
        "description": f"{config['cn']} · {year} 年参考数据 · <b>{len(rows)} 个职业组</b>。方块面积表示图示就业规模，颜色表示所选指标。",
        "source": config["survey"], "source_links": links, "data_year": year,
        "total_jobs": total, "occ_count": len(rows), "occupations": rows,
        "skill_system": SKILL_SYSTEM,
        "employment_summary": {
            "source_total_jobs": round(published_total), "source_classified_jobs": round(listed),
            "source_classification_coverage_pct": coverage,
            "source_unclassified_jobs": round(unclassified) if unclassified is not None else None,
            "source_unrepresented_jobs": max(0, round(published_total - listed)),
            "map_jobs": total, "map_is_scaled_estimate": cc == "IND",
            "quality_flags": sorted({r["status"] for r in levels.values() if r["status"]}),
            "notes": EMPLOYMENT_NOTES[cc],
        },
        "gender_summary": gender_summary(observations, year, sex_codes),
        "trend_note": TREND_NOTES[cc], "major_share_changes": major_changes,
        "source_files": source_files,
    }


def build_data():
    manifest = verify_snapshot()
    result = {"schema_version": 2, "data_reviewed_on": manifest["reviewed_on"],
              "source_refresh_status": manifest["online_check"],
              "countries": {cc: build_country(cc, manifest) for cc in COUNTRIES}}
    return apply_ai_exposure(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "site/data.json")
    parser.add_argument("--check", action="store_true", help="Fail if committed data differs from a clean rebuild")
    args = parser.parse_args()
    result = build_data()
    if args.check:
        if result != json.loads(args.output.read_text(encoding="utf-8")):
            raise SystemExit("site/data.json differs from a clean rebuild")
        print("Country data matches the reviewed inputs and build logic")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8")
        temporary.replace(args.output)
        for cc, country in result["countries"].items():
            print(cc, country["occ_count"], country["total_jobs"])


if __name__ == "__main__":
    main()
