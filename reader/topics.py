"""Local keyword rules for grouping reading cards by subject."""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable


TECH = "科技与开发"
ENGINEERING = "工程与硬件"
RESEARCH = "研究与写作"
LEARNING = "课程与学习"
CAREER = "工作与职业"
KNOWLEDGE = "知识管理"
CULTURE = "文化与生活"
BUSINESS = "商业与产品"
UNCLASSIFIED = "待分类"
TOPICS = (TECH, ENGINEERING, RESEARCH, LEARNING, CAREER, KNOWLEDGE, CULTURE, BUSINESS, UNCLASSIFIED)

VOCABULARY = {
    TECH: {
        "软件开发": "软件开发|programming|软件工程|Python|JavaScript|Git|代码审查|code review",
        "人工智能": "人工智能|artificial intelligence|大语言模型|LLM|机器学习|machine learning|深度学习|deep learning|Agent",
        "数据分析": "数据分析|data analysis|数据可视化|data visualization|SQL",
        "系统与网络": "操作系统|operating systems|计算机网络|Docker|Linux|Kubernetes|database|数据库",
    },
    ENGINEERING: {
        "电子与电路": "硬件|hardware|芯片|semiconductor|电路|electronics|circuit|PCB",
        "嵌入式": "嵌入式|嵌入式系统|Arduino|microcontroller|embedded systems|数据采集|robotics|机器人",
        "工程设计": "工程设计|engineering design|机械设计|仿真|electronics simulation|3D打印",
    },
    RESEARCH: {
        "文献阅读": "文献|研究论文|论文阅读|literature review|paper reading|科研|research methods",
        "写作与编辑": "写作|编辑|writing|editing|写作反馈|文章结构",
        "研究方法": "实验设计|experiment design|reproducibility|统计方法|研究方法|科研选题",
    },
    LEARNING: {
        "课程": "课程|course|syllabus|讲义|lecture notes|教材|textbook|workshop|训练营",
        "学习路线": "学习路线|study roadmap|learning path|自学路线|入门指南",
        "学习方法": "学习方法|学习习惯|spaced repetition|间隔重复|active recall|复习|练习题",
    },
    CAREER: {
        "求职与面试": "求职|面试|简历|resume|career|job search|interview",
        "职业技能": "职业技能|workplace|团队协作|teamwork|沟通|远程办公|工作流程",
    },
    KNOWLEDGE: {
        "归档与检索": "归档|知识管理|知识库|笔记系统|personal knowledge management|Obsidian|read it later|bookmark",
        "阅读与笔记": "阅读台|阅读清单|阅读队列|读书笔记|笔记方法|自动标签|reading queue",
        "效率工具": "时间管理|效率工具|task management|任务看板|自动化工作流",
    },
    CULTURE: {
        "艺术与设计": "艺术|美术|插画|摄影|photography|visual design|博物馆|museum",
        "文化与历史": "文化|历史|culture|history|文学|literature|电影|cinema",
        "生活与兴趣": "园艺|gardening|烹饪|cooking|食谱|recipe|徒步|hiking|手工|旅行",
    },
    BUSINESS: {
        "产品设计": "产品设计|product design|用户研究|user research|界面设计|usability",
        "商业与行业": "行业|创业|商业|business|市场营销|marketing|品牌|创业公司|startup",
    },
}


def normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def aliases(pattern: str) -> Callable[[str], bool]:
    branches = []
    needles = set()
    for alias in pattern.split("|"):
        alias = normalized(alias)
        needles.update((alias, alias.replace(" ", "")))
        if re.fullmatch(r"[a-z0-9].*", alias):
            start = r"(?<![a-z0-9])"
        else:
            start = ""
        end = r"(?![a-z0-9])" if re.search(r"[a-z0-9]$", alias) else ""
        branches.append(start + re.escape(alias).replace(r"\ ", r"[ \t]*") + end)
    compiled = re.compile("|".join(branches))

    def matches(value: str) -> bool:
        return any(needle in value for needle in needles) and compiled.search(value) is not None

    return matches


RULES = {
    topic: {tag: aliases(pattern) for tag, pattern in tags.items()}
    for topic, tags in VOCABULARY.items()
}
TAG_VALUE = re.compile(r'''"(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[^,，]+''')
REFERENCE_HEADING = re.compile(r"(?m)^#{1,6}\s+(?:研究迁移|参考文献|相关归档|关联笔记|参考链接|来源链接|References\b|Related\s+(?:work|links)\b)", re.I)
BOILERPLATE = re.compile(r"(?m)^\s*(?:>\s*)?(?:来源网址|原始链接|来源地址|原帖链接|抓取状态|状态|日期|原始来源)\s*[:：].*$")


def frontmatter_tags(front: str) -> list[str]:
    """Read the simple inline, scalar and block tag fields Obsidian uses."""
    match = re.search(r"(?mi)^tags\s*:[ \t]*(.*)$", front)
    if not match:
        return []
    inline = match.group(1).strip()
    if not inline or inline.startswith("#"):
        values = []
        for line in front[match.end():].lstrip("\n\r").splitlines():
            entry = re.match(r"^[ \t]*-\s+(.+)$", line)
            if not entry:
                break
            values.append(entry.group(1))
    elif inline.startswith("["):
        end = inline.rfind("]")
        values = TAG_VALUE.findall(inline[1:end]) if end > 0 else []
    else:
        values = TAG_VALUE.findall(inline)
    return [value.strip().strip("\"'").lstrip("#") for value in values]


def clean_excerpt(body: str) -> str:
    excerpt = REFERENCE_HEADING.split(body[:4500], maxsplit=1)[0]
    excerpt = re.sub(r"```[\s\S]*?(?:```|\Z)|<!--[\s\S]*?(?:-->|\Z)", " ", excerpt)
    excerpt = re.sub(r"!?\[[^\]\n]*\]\([^\n)]*\)|!?\[\[[^\]\n]*\]\]|https?://\S+", " ", excerpt)
    return normalized(BOILERPLATE.sub(" ", excerpt))


def classify(title: str, tags: list[str], body: str, _path: str) -> dict:
    headline = normalized(title)
    metadata = "\n".join(normalized(tag) for tag in tags)
    excerpt = clean_excerpt(body)
    scores = {}
    heading_matches = {}
    tag_hits = []
    for topic, rules in RULES.items():
        hits = []
        weak_hits = 0
        for label, match in rules.items():
            weight = 6 * match(headline) + 4 * match(metadata)
            weak_hits += match(excerpt)
            if weight:
                hits.append((weight, label))
                tag_hits.append((weight, label))
        scores[topic] = max((weight for weight, _ in hits), default=0) + min(2, weak_hits)
        heading_matches[topic] = [label for _, label in hits]

    ranked = sorted(scores, key=scores.get, reverse=True)
    topic = ranked[0]
    if scores[topic] < 4 or scores[topic] == scores[ranked[1]]:
        topic = UNCLASSIFIED

    evidence = "标题和已有标签缺少明确的主题线索"
    if topic != UNCLASSIFIED:
        evidence = "标题或归档标签：" + "、".join(heading_matches[topic][:3])

    tag_hits.sort(reverse=True)
    display_tags = []
    seen = set()
    for value in (*tags, *(label for _, label in tag_hits)):
        value = value.strip()
        key = normalized(value)
        if 0 < len(value) <= 40 and key not in seen:
            display_tags.append(value)
            seen.add(key)
        if len(display_tags) == 5:
            break
    return {"topic": topic, "tags": display_tags, "topicEvidence": evidence}


def validate_manual_tags(value: object) -> list[str]:
    if not isinstance(value, list) or len(value) > 12:
        raise ValueError("每篇最多保存 12 个标签")
    tags = []
    seen = set()
    for candidate in value:
        if not isinstance(candidate, str):
            raise ValueError("标签格式无效")
        tag = unicodedata.normalize("NFKC", candidate).strip().lstrip("#").strip()
        if not 1 <= len(tag) <= 40 or any(c in ",，" or unicodedata.category(c) in {"Cc", "Cs"} for c in tag):
            raise ValueError("标签须为 1 至 40 个字符，不能包含逗号或换行")
        key = tag.casefold()
        if key not in seen:
            tags.append(tag)
            seen.add(key)
    return tags
