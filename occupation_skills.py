"""ISCO-08 skill levels; not national degree requirements or worker attainment.

Source: ISCO-08 Volume 1, Part I (skill model) and Part III (major/sub-major groups).
https://ilostat.ilo.org/methods/concepts-and-definitions/classification-occupation/
"""
SKILL_SYSTEM = {
    "name": "ISCO-08 职业技能等级",
    "source_url": "https://ilostat.ilo.org/methods/concepts-and-definitions/classification-occupation/",
    "levels": [
        ["技能等级 1（基础任务）", "Skill level 1", 0],
        ["技能等级 2（操作与服务任务）", "Skill level 2", 1],
        ["技能等级 3（复杂技术任务）", "Skill level 3", 2],
        ["技能等级 4（复杂专业任务）", "Skill level 4", 3],
    ],
    "note": "按 ISCO-08 任务复杂度和技能定义映射；不是本国招聘学历要求，也不是就业者实际学历。技能可通过教育、培训或经验获得。",
}


def skill_fields(code):
    prefix, major = code[:2], code[0]
    if major == "1":
        level = 3 if prefix == "14" else 4
    elif major == "0":
        level = {"01": 4, "02": 2, "03": 1}.get(prefix)
    else:
        level = {"2": 4, "3": 3, "4": 2, "5": 2, "6": 2, "7": 2, "8": 2, "9": 1}.get(major)
    return {"skill_level": level, "skill_idx": level - 1 if level else None,
            "skill": SKILL_SYSTEM["levels"][level - 1][0] if level else "未映射",
            "skill_source": "isco08_skill_model"}
