"""界面语言指令：显式声明 UI 语言，正文跟随界面语言，引文保持原字形。

背景：后端此前不知道用户界面语言，系统提示规则 6「使用用户的语言回答」
让模型按上下文主体字形作答——阅读器模式下页面经文与检索片段都是繁体，
简体用户会收到繁体回答（fojin.app 实测）。前端现经 ChatRequest.ui_lang
把界面语言传进来，本文件钉住注入位置与文字边界：

  1. 不传 ui_lang 时系统提示词逐字节不变（旧前端 / eval 钉死路径兼容）；
  2. 指令追加在系统提示词**最末尾**（离生成最近的指令服从率最高）；
  3. 指令要求引文原文与【《经名》第N卷】经名保持原始字形，不得转写。
"""

from app.schemas.chat import ChatRequest
from app.services.prompt_builder import (
    CITATION_DISCIPLINE_SUFFIX,
    THINKING_STYLE_SUFFIX,
    _build_llm_messages,
)


def _system_of(msgs: list[dict]) -> str:
    assert msgs[0]["role"] == "system"
    return msgs[0]["content"]


def test_no_ui_lang_keeps_prompt_byte_identical():
    before = _system_of(_build_llm_messages([], "【系统自动检索】……", "「般若」和智慧有什么不同？"))
    after = _system_of(_build_llm_messages([], "【系统自动检索】……", "「般若」和智慧有什么不同？", ui_lang=None))
    assert before == after


def test_zh_gets_simplified_directive_at_the_end():
    system = _system_of(_build_llm_messages([], "【系统自动检索】……", "什么是空性？", ui_lang="zh"))
    assert "界面语言" in system
    assert "简体中文" in system
    # 追加在所有既有后缀之后 —— 与 CITATION/THINKING 的注入顺序不冲突
    assert system.endswith(CITATION_DISCIPLINE_SUFFIX + THINKING_STYLE_SUFFIX + (
        "\n\n## 界面语言\n"
        "用户当前界面语言为简体中文。回答正文、白话翻译、术语解释和文末的[追问]建议，"
        "一律使用简体中文书写；"
        "但逐字引用经文原文时保持其原始字形（通常为繁体），不得转写、翻译引文本身；"
        "【《经名》第N卷】引用中的经名保持[出处]行的原始写法（通常为繁体）。"
    ))


def test_zh_hant_gets_traditional_directive():
    system = _system_of(_build_llm_messages([], "", "什麼是空性？", ui_lang="zh-Hant"))
    assert "繁體中文" in system


def test_en_gets_english_directive():
    system = _system_of(_build_llm_messages([], "", "What is emptiness?", ui_lang="en"))
    assert "英语（English）" in system


def test_reader_path_appends_language_directive():
    """阅读器模式正是本修复的动机场景：页面原文是繁体，UI 是简体。"""
    system = _system_of(_build_llm_messages(
        [], "", "這段什麼意思？",
        reading_context={"title": "般若波羅蜜多心經", "juan_num": 1,
                         "selected_text": None, "page_content": "觀自在菩薩……"},
        ui_lang="zh",
    ))
    assert "简体中文" in system
    assert system.endswith("（通常为繁体）。")


def test_master_path_appends_language_directive():
    system = _system_of(_build_llm_messages(
        [], "【系统自动检索】……", "如何修行？", master_id="huineng", ui_lang="zh",
    ))
    assert "简体中文" in system


def test_unknown_code_is_ignored():
    before = _system_of(_build_llm_messages([], "", "什么是空性？"))
    after = _system_of(_build_llm_messages([], "", "什么是空性？", ui_lang="fr"))
    assert before == after


def test_chat_request_accepts_ui_lang():
    r = ChatRequest(message="hi", ui_lang="zh-Hant")
    assert r.ui_lang == "zh-Hant"
    # 缺省 None —— 旧前端请求不带这个字段也合法
    assert ChatRequest(message="hi").ui_lang is None
