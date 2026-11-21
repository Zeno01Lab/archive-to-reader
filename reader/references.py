"""Separate a card's reading purpose from its subject and reading status."""
from __future__ import annotations

import re

from topics import normalized


USES = ("daily", "roadmap", "resources", "materials")
HEADING = re.compile(r"^#\s+(.+)$", re.M)
READING_ANALYSIS = re.compile(
    r"面试|面经|招生|博士申请|招聘|求职|人物经历|科研经历|博士[:：]|phd(?:建议|经验)|"
    r"学习法|学习习惯|学习与成长|讲座[:：]|论文精读|精读[:：]|"
    r"教材对照|资源核查|公开资料核查|研究方向交流手册|"
    r"学习心态分析|biographical-learning-review",
)

TYPE_RULES = (
    ("roadmap", re.compile(r"^(?:学习路线资料卡|学习方案(?:与资料归档)?|课程定点补课索引|自学路线)$")),
    ("resources", re.compile(r"^(?:(?:课程|学习|阅读)资源(?:调研(?:总结)?|归档|清单)|资源仓库调研)$")),
    ("materials", re.compile(r"^(?:课程资料整理|课程讲义|课程资料|学习资料|讲义|教材|课件|课程大纲|学习笔记资料卡|作业学习指导)$")),
)
TITLE_RULES = (
    ("roadmap", re.compile(
        r"(?:学习|自学|入门|补课|阅读)(?:个人经验)?(?:路线图?|路径)|"
        r"影子课程.{0,14}自学计划|学习.{0,6}备考方案|"
        r"(?:如何学习|怎么学).{0,30}知识地图|"
        r"\b(?:study|learning)\s+(?:roadmap|path)\b"
    )),
    ("resources", re.compile(
        r"(?:学习|课程|自学|入门|阅读|书籍|公开课程)(?:相关)?资源"
        r"(?!(?:与|和|及)[^:：|｜]*(?:实验|经验|建议|观点))|"
        r"(?:资源|资料|论文|书籍)(?:清单|地图|目录|导航|合集|分类)|"
        r"推荐的.{1,28}资源|书籍推荐|书单(?:线索|推荐|合集|索引)|补课清单|可认证网课|"
        r"\b(?:reading list|study resources|course resources|resource directory)\b"
    )),
    ("materials", re.compile(
        r"(?:学习|教学|自学|课程|参考)资料(?:归档|整理|查阅|汇总|入口)?|"
        r"课程(?:网站|主页|大纲|讲稿)|"
        r"仿真教材|学习笔记(?:[》」]|$)|"
        r"讲义|课件|习题集|习题解答|教程(?:[:：、，｜|]|\s|$)|"
        r"\b(?:lecture notes|course syllabus|course materials|problem sets)\b"
    )),
)


def classify_use(title: str, kind: str, body: str) -> tuple[str, str]:
    """Require an explicit title, type, or top-level heading for reference use."""
    headline = normalized(title)
    kind_key = normalized(kind).strip()
    if READING_ANALYSIS.search(headline) or READING_ANALYSIS.search(kind_key):
        return "daily", ""
    for use, pattern in TYPE_RULES:
        if pattern.fullmatch(kind_key):
            return use, f"归档类型：{kind}"

    heading = HEADING.search(body[:1600])
    texts = [(headline, "标题")]
    if heading:
        texts.append((normalized(heading.group(1)), "资料标题"))
    for value, source in texts:
        for use, pattern in TITLE_RULES:
            match = pattern.search(value)
            if match:
                return use, f"{source}包含「{match.group(0)}」"
    return "daily", ""


def reference_search(body: str) -> str:
    """Return searchable text while retaining link labels and removing URLs."""
    excerpt = body[:7000]
    excerpt = re.split(r"(?m)^#{1,6}\s+(?:研究迁移|变更记录|更新日志)\b", excerpt, maxsplit=1)[0]
    excerpt = re.sub(r"(?s)<!--.*?(?:-->|\Z)", " ", excerpt)
    excerpt = re.sub(r"!?\[\[([^\]\n]+)\]\]", lambda match: match[1].split("|", 1)[-1], excerpt)
    excerpt = re.sub(r"!?\[([^\]\n]*)\]\([^\n]*?\)", r"\1", excerpt)
    excerpt = re.sub(r"https?://\S+|<[^>\n]*>", " ", excerpt, flags=re.I)
    return " ".join(excerpt.split())[:4500]
