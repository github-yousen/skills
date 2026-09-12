# -*- coding: utf-8 -*-
"""
番茄小说作者后台 (fanqienovel.com) API 客户端
用法: 确保技能目录下存在 fanqienovel_auth.json（凭证文件），导入函数调用即可
依赖: 标准库 urllib，无需第三方包

凭证管理（与 leetcode-algo-trainer 同模式）:
1. 凭证存于本技能目录的 fanqienovel_auth.json（与脚本分离，过期只改这一个文件）
2. 通过浏览器登录 https://fanqienovel.com 后 F12->Network 抓取刷新
3. 可用 temp-scripts/fill_fanqienovel_creds.py 从 curl 集合自动生成

实测要点（2026-08 发布第4章验证）:
- publish_article 的 volume_name 必填，缺省报"缺少书籍卷相关参数"
- 章节状态: article_status 1=已发布 2=断更/隐藏(非审核中) 0=草稿
- 隐藏/断更识别: cant_modify_reason="断更作品恢复连载后可修改" + can_delete=2
- 审核中识别: cant_modify_reason="审核中暂不支持修改" + can_delete=2
- 已发布可修改: can_delete=1
- get_edit_article / get_latest_article 需 book_id + item_id 双参数
"""
import os
import urllib.request
import urllib.parse
import ssl
import json
import re
import time

_BASE = "https://fanqienovel.com"

# 可通过环境变量 FANQIENOVEL_DATA_DIR 覆盖凭证目录（默认本技能目录）
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR = os.environ.get('FANQIENOVEL_DATA_DIR',
                            os.path.dirname(_SCRIPT_DIR))  # scripts/ 的上一级 = 技能目录
AUTH_FILE = os.path.join(_SKILL_DIR, 'fanqienovel_auth.json')

# 公共参数
_AID = "2503"
_APP_NAME = "muye_novel"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"


def load_auth():
    """读取凭证文件，返回 dict（cookie / ms_token / a_bogus / secsdk_token）"""
    if not os.path.exists(AUTH_FILE):
        raise FileNotFoundError(
            f"未找到凭证文件 {AUTH_FILE}\n"
            "请先在浏览器登录 fanqienovel.com，F12->Network 复制请求凭证写入该文件，"
            "或运行 temp-scripts/fill_fanqienovel_creds.py 自动生成")
    with open(AUTH_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def _req(method, path, params=None, data=None, need_sig=True, need_secsdk=False, referer=None):
    """通用请求封装

    :param method: GET / POST
    :param path: 接口路径，如 /api/author/book/book_list/v0
    :param params: 查询参数 dict（不含 aid/app_name，自动追加）
    :param data: POST form body dict（不含 aid/app_name，自动追加）
    :param need_sig: 是否追加 msToken + a_bogus 签名参数（GET 必填）
    :param need_secsdk: 是否携带 x-secsdk-csrf-token 头（写操作必填）
    :param referer: Referer 页面地址
    """
    auth = load_auth()
    cookie = auth.get("cookie", "")
    if not cookie:
        raise RuntimeError(f"凭证文件 {AUTH_FILE} 中 cookie 为空，请更新")

    query = {"aid": _AID, "app_name": _APP_NAME}
    if params:
        query.update(params)
    url = _BASE + path + "?" + urllib.parse.urlencode(query)
    if need_sig:
        url += "&msToken=" + urllib.parse.quote(auth.get("ms_token", "")) \
               + "&a_bogus=" + urllib.parse.quote(auth.get("a_bogus", ""))

    headers = {
        "User-Agent": _UA,
        "Cookie": cookie,
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://fanqienovel.com",
        "Referer": referer or "https://fanqienovel.com/main/writer/book-manage",
    }
    body = None
    if data:
        payload = {"aid": _AID, "app_name": _APP_NAME}
        payload.update(data)
        body = urllib.parse.urlencode(payload).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"
    if need_secsdk:
        secsdk = auth.get("secsdk_token", "")
        if not secsdk:
            raise RuntimeError(f"写操作需要 x-secsdk-csrf-token，请在 {AUTH_FILE} 中更新 secsdk_token")
        headers["x-secsdk-csrf-token"] = secsdk

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


# ==================== 账号 / 状态 ====================

def check_user_status():
    """校验登录状态"""
    return _req("GET", "/api/author/verify/check_user_status/v0")


def get_account_info():
    """获取账号信息"""
    return _req("GET", "/api/author/account/info/v0/")


def get_server_time():
    """获取服务器时间"""
    return _req("GET", "/app/node/data/server/time", need_sig=False)


def get_level_config(is_pc="1"):
    """作家等级配置"""
    return _req("GET", "/app/node/config/author/level_config/v2/", params={"is_pc": is_pc}, need_sig=False)


def get_new_msg_count(source_type_list="1"):
    """新消息数"""
    return _req("GET", "/reading/msgapi/getnewmsgcount/v0/",
                params={"source_type_list": source_type_list}, need_sig=False)


# ==================== 书籍 ====================

def get_book_list(page_index=0, page_count=10, image_fmt="270x480"):
    """书籍列表（作者后台全部作品）"""
    return _req("GET", "/api/author/book/book_list/v0",
                params={"page_index": page_index, "page_count": page_count,
                        "image_fmt_list": image_fmt})


def get_book_detail(book_id, image_fmt="270x480"):
    """书籍详情"""
    return _req("GET", "/api/author/book/book_detail/v0/",
                params={"book_id": book_id, "image_fmt_list": image_fmt})


def get_homepage_book_list(page_index=0, page_count=10, image_fmt="396x220"):
    """首页书籍列表"""
    return _req("GET", "/api/author/homepage/book_list/v0/",
                params={"page_index": page_index, "page_count": page_count,
                        "image_fmt_list": image_fmt})


def get_volume_list(book_id):
    """卷列表"""
    return _req("GET", "/api/author/volume/volume_list/v1", params={"book_id": book_id})


def get_banned_info(book_id, type="1"):
    """封禁/违规信息"""
    return _req("GET", "/api/author/banned/info/v0/", params={"book_id": book_id, "type": type})


def create_book(**kwargs):
    """创建书籍（写操作，需 secsdk_token）"""
    return _req("POST", "/api/author/book/create/v0/", data=kwargs, need_sig=True, need_secsdk=True)


def delete_book(book_id):
    """删除书籍（写操作，需 secsdk_token）"""
    return _req("POST", "/api/author/book/delete/v0", data={"book_id": book_id},
                need_sig=True, need_secsdk=True)


def top_hide_book(book_id, action):
    """书籍隐藏/置顶（写操作，需 secsdk_token）

    :param action: 后端动作值（1=置顶/显示? 2=隐藏? 需实测确认，可尝试 1/2/0）
    """
    return _req("POST", "/api/author/book/top_hide/v0/", data={"book_id": book_id, "action": action},
                need_sig=True, need_secsdk=True)


def modify_book_info(book_id, **kwargs):
    """修改书籍信息（写操作，需 secsdk_token）

    🔴 实测结论（2026-08-11，安全书验证 + 逆向前端 main.js ModifyBook）：
    - 有效接口：POST **/app/book/modify_book/v0/**（改了才生效）
    - ❌ /api/author/book/modify_book/v0/ 返回 code=0 但**静默假成功**（不生效），勿用
    - 请求体字段：book_name / gender / category / thumb_uri / summary /
      gift_word / roles / is_self_pic / activity_id / special_judge / group_category_id
    - 🔴 简介字段名是 **summary**（不是 abstract；本函数兼容 abstract 别名自动转换）
    - 🔴 只传需要修改的字段即可，服务端支持部分更新
    - 🔴 **已签约作品不可修改分类**：传 category 会报 code=-2020"已签约作品不可修改分类"，
      因此签约书改简介/书名时请勿传 category。本函数提供 skip_category 开关自动排除。

    :param book_id: 书籍ID
    :param kwargs: 可修改字段（book_name / summary(或abstract) / gift_word / roles / thumb_uri / gender / category 等）
    :param skip_category: True 时强制剔除 category 字段（签约书默认应跳过）
    :return: 接口响应 dict（code=0 即成功）
    """
    skip_category = kwargs.pop("skip_category", True)
    data = {"book_id": book_id}
    # 兼容别名：abstract → summary（防止用户按直觉传 abstract）
    if "abstract" in kwargs and "summary" not in kwargs:
        kwargs["summary"] = kwargs.pop("abstract")
    # 签约书不可改分类：默认剔除 category
    if skip_category:
        kwargs.pop("category", None)
    data.update(kwargs)
    return _req("POST", "/app/book/modify_book/v0/", data=data,
                need_sig=True, need_secsdk=True)


def get_book_outline(book_id):
    """获取书籍大纲"""
    return _req("GET", "/api/author/book/get_book_outline/v0/", params={"book_id": book_id})


def update_book_outline(book_id, content):
    """更新书籍大纲（写操作）"""
    return _req("POST", "/api/author/book/update_book_outline/v0/",
                data={"book_id": book_id, "content": content},
                need_sig=True, need_secsdk=True)


def get_pre_sign_book_list(page_index=0, page_count=10):
    """可签约书籍列表"""
    return _req("GET", "/api/author/book/pre_sign_book_list/v0",
                params={"page_index": page_index, "page_count": page_count})


# ==================== 卷管理 ====================

def add_volume(book_id, volume_name):
    """新增卷（写操作）"""
    return _req("POST", "/api/author/volume/add_volume/v0",
                data={"book_id": book_id, "volume_name": volume_name},
                need_sig=True, need_secsdk=True)


def modify_volume(volume_id, volume_name, book_id=""):
    """修改卷名（写操作）"""
    return _req("POST", "/api/author/volume/modify/v0",
                data={"volume_id": volume_id, "volume_name": volume_name, "book_id": book_id},
                need_sig=True, need_secsdk=True)


def delete_volume(volume_id):
    """删除卷（写操作）"""
    return _req("POST", "/api/author/volume/delete_volume/v0/",
                data={"volume_id": volume_id}, need_sig=True, need_secsdk=True)


# ==================== 章节 ====================

def get_chapter_list(book_id, volume_id="", page_index=0, page_count=15, status="0",
                     must_have_correction_feedback="0", need_correction_feedback_num="1"):
    """章节列表

    :param book_id: 书籍ID
    :param volume_id: 卷ID（可选，空则查全部卷）
    :param status: 章节状态（0=全部）
    """
    return _req("GET", "/api/author/chapter/chapter_list/v1",
                params={"book_id": book_id, "volume_id": volume_id,
                        "page_index": page_index, "page_count": page_count, "status": status,
                        "must_have_correction_feedback": must_have_correction_feedback,
                        "need_correction_feedback_num": need_correction_feedback_num})


def get_draft_list(book_id, volume_id="", page_index=0, page_count=15):
    """章节草稿列表（未发布的存稿）"""
    return _req("GET", "/api/author/chapter/draft_list/v1",
                params={"book_id": book_id, "volume_id": volume_id,
                        "page_index": page_index, "page_count": page_count})


def search_chapter(book_id, keyword, page_index=0, page_count=10):
    """搜索章节"""
    return _req("GET", "/api/author/search/search_chapter/v0",
                params={"book_id": book_id, "keyword": keyword,
                        "page_index": page_index, "page_count": page_count})


def get_edit_article(item_id, book_id=""):
    """获取章节编辑内容（已有章节）

    :param item_id: 章节ID
    :param book_id: 书籍ID（实测必须，缺省报"书籍ID为空"）
    """
    params = {"item_id": item_id}
    if book_id:
        params["book_id"] = book_id
    return _req("GET", "/api/author/edit_article/v0/", params=params)


def new_article(book_id, volume_id=""):
    """新建章节（返回新 item_id，再调 publish_article 发布）"""
    return _req("POST", "/api/author/article/new_article/v0/",
                data={"book_id": book_id, "volume_id": volume_id},
                need_sig=True, need_secsdk=True)


def get_latest_article(item_id, book_id=""):
    """获取章节最新内容

    :param item_id: 章节ID
    :param book_id: 书籍ID（实测必须，缺省报"书籍ID为空"）
    """
    params = {"item_id": item_id}
    if book_id:
        params["book_id"] = book_id
    return _req("GET", "/api/author/article/get_latest_article/v0/", params=params)


def delete_article(item_id):
    """删除章节（写操作，需 secsdk_token）"""
    return _req("POST", "/api/author/delete_article/v1",
                data={"item_id": item_id}, need_sig=True, need_secsdk=True)


def cover_article(item_id):
    """章节屏蔽/覆盖（写操作，具体行为以实测为准）"""
    return _req("POST", "/api/author/article/cover_article/v0/",
                data={"item_id": item_id}, need_sig=True, need_secsdk=True)


def modify_article_timer(item_id, timer_status, timer_time=""):
    """章节定时发布设置（写操作）

    :param timer_status: 1=启用定时
    :param timer_time: 定时时间（格式待实测，如时间戳或 yyyy-mm-dd hh:mm）
    """
    return _req("POST", "/api/author/article/modify_timer/v0/",
                data={"item_id": item_id, "timer_status": timer_status, "timer_time": timer_time},
                need_sig=True, need_secsdk=True)


# ==================== 数据统计 ====================

def get_stats_book_list(page_index=0, page_count=10, image_fmt="270x480"):
    """数据统计页书籍列表"""
    return _req("GET", "/api/author/stats/book_list/v0/",
                params={"page_index": page_index, "page_count": page_count,
                        "image_fmt_list": image_fmt})


def get_book_common_stats(book_id, stats_type=""):
    """书籍通用统计"""
    return _req("GET", "/api/author/stats/book_common_v1/v0/",
                params={"book_id": book_id, "stats_type": stats_type})


def get_book_increase_stats(book_id, start_date, end_date, stats_types="24,27,26,25,28,29"):
    """趋势增长统计

    :param book_id: 书籍ID
    :param start_date: 起始秒级时间戳
    :param end_date: 结束秒级时间戳
    :param stats_types: 统计维度ID，逗号分隔
    """
    return _req("GET", "/api/author/stats/book_increase_v2/v0/",
                params={"book_id": book_id, "start_date": start_date,
                        "end_date": end_date, "stats_types": stats_types})


def get_chapter_stats(book_id, stats_type="3", latest_count=500, page_index=0, page_count=500):
    """章节维度统计（每章完读/追读/流失数据）

    :param stats_type: 决定返回的指标（实测关键参数，缺省数据为空）：
        - "3"     → 完读率 read_completion_rate + 流失率 loss_rate
        - "4"     → 追读率 follow_read_rate
        - "5,6,7" → 段评 comment_paragraph_cnt / 章评 comment_chapter_cnt / 催更 reminder_cnt
    :param latest_count: 最近章节数（如 500=全部）
    :param page_count: 每页数量（与 latest_count 保持一致取全量）
    """
    return _req("GET", "/api/author/stats/chapter_list_v1/v0/",
                params={"book_id": book_id, "stats_type": stats_type,
                        "latest_count": latest_count,
                        "page_index": page_index, "page_count": page_count})


def get_hot_words(gender="0", type="1"):
    """热门关键词列表"""
    return _req("GET", "/api/author/hot_word/word_list/v0",
                params={"gender": gender, "type": type, "set_read_time": "1"})


def get_read_source(book_id, start_date="", end_date=""):
    """流量来源构成（实测近7天可用，无日期参数则返回近7天）

    返回字段：
      read_count_total   总阅读次数
      read_count_library 书城来源
      read_count_search  搜索来源（新读者主力）
      read_count_shelf   书架回流（老读者）
      read_count_category 分类来源
      read_count_recent  继续阅读
    书架比正确算法 = 用本接口的 search（新量）与 shelf（回流）判断留存，
    不要用 shelf_cnt_daily 单日值（波动大不可靠）。
    """
    params = {"book_id": book_id}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    return _req("GET", "/api/author/stats/read_source/v0/", params=params)


# ==================== 写作 / 发布（写操作） ====================

def correct_text(text, item_id):
    """错别字/语病纠错（需 _SECSDK_TOKEN）"""
    return _req("POST", "/app/node/editor/correction/v0/",
                data={"text": text, "item_id": item_id}, need_sig=False, need_secsdk=True)


def pre_audit_article(item_id, content, pre_audit_type="1"):
    """发布前敏感词预审（需 _SECSDK_TOKEN）

    :param content: HTML 格式正文，如 <p>段落</p>
    """
    return _req("POST", "/app/book/pre_audit_article/v0/",
                data={"item_id": item_id, "content": content, "pre_audit_type": pre_audit_type},
                need_sig=False, need_secsdk=True)


def get_speak_popup(item_id, content):
    """获取章节弹窗信息（写作辅助，需 _SECSDK_TOKEN）"""
    return _req("POST", "/api/author/article/get_speak_popup/v0/",
                data={"item_id": item_id, "content": content},
                need_sig=True, need_secsdk=True)


def publish_article(book_id, item_id, volume_id, title, content,
                    volume_name="", publish_status="1", need_pay="0",
                    timer_status="0", timer_time="", use_ai="2", has_chapter_ad="false",
                    chapter_ad_types="", speak_type="0"):
    """发布/更新章节（核心写操作，需 _SECSDK_TOKEN）

    :param book_id: 书籍ID
    :param item_id: 章节ID（新章节需先创建；更新则用原ID）
    :param volume_id: 所属卷ID
    :param volume_name: 卷名称
    :param title: 章节标题
    :param content: HTML 格式正文
    :param publish_status: 1=发布
    :param timer_status: 0=立即发布, 1=定时发布
    :param timer_time: 定时发布时间（秒级时间戳字符串，如 "1786356000"）
    """
    return _req("POST", "/api/author/publish_article/v0/",
                data={"book_id": book_id, "item_id": item_id, "volume_id": volume_id,
                      "volume_name": volume_name, "title": title, "content": content,
                      "publish_status": publish_status, "need_pay": need_pay,
                      "timer_status": timer_status, "timer_time": timer_time, "timer_chapter_preview": "[]",
                      "speak_type": speak_type, "use_ai": use_ai, "has_chapter_ad": has_chapter_ad,
                      "chapter_ad_types": chapter_ad_types, "device_platform": "pc"},
                need_sig=True, need_secsdk=True)


def mark_book_problem_read():
    """书籍问题标记已读"""
    return _req("POST", "/app/home/message/book_problem_mark_info_read_mark/v0",
                data={}, need_sig=False)


# ==================== 内容转换 / 发布助手 ====================

def md_to_html(md_text):
    """Markdown 段落文本 -> 章节正文 HTML（<p> 段落，段内 <br> 换行）。

    注意：此函数不处理标题行，调用方需先自行剔除 `# 第X章 xxx` 标题行，
    否则标题会被当成正文首段，导致线上"标题重复"事故（实测踩坑）。
    """
    lines = [l.rstrip() for l in md_text.splitlines()]
    paras = []
    cur = []
    for l in lines:
        if not l.strip():
            if cur:
                paras.append(cur)
                cur = []
            continue
        cur.append(re.sub(r'^#{1,6}\s*', '', l))
    if cur:
        paras.append(cur)
    return "".join(f"<p>{'<br>'.join(p)}</p>" for p in paras)


def chapter_md_to_html(md_text):
    """整章 content.md -> (title, html)。

    约定格式：第一行 `# 第X章 标题` 为章节标题，其余为正文。
    返回 (标题, 正文HTML)，标题不会进入正文。
    """
    lines_all = md_text.strip().splitlines()
    first = lines_all[0]
    title = re.sub(r'^#\s*', '', first).strip()
    body_text = "\n".join(lines_all[1:]).strip()
    body_html = md_to_html(body_text)
    return title, body_html


def publish_chapter_from_md(book_id, volume_id, volume_name, md_text,
                            item_id=None, title=None, body_html=None):
    """从整章 Markdown 文本直接发布章节（创建->预审->发布 全流程）。

    :param book_id: 书籍ID
    :param volume_id: 卷ID
    :param volume_name: 卷名（必填，缺省报"缺少书籍卷相关参数"）
    :param md_text: content.md 全文（第一行须为 `# 第X章 标题`）
    :param item_id: 已有章节ID（更新/重发时传；None=新建）
    :param title: 手动指定标题（默认从 md 第一行提取）
    :param body_html: 手动指定正文HTML（默认由 md 转换，自动剔除标题行）
    :return: dict（title / item_id / audit / publish / ok）
    """
    if title is None or body_html is None:
        t, h = chapter_md_to_html(md_text)
        title = title or t
        body_html = body_html or h

    result = {"title": title, "item_id": item_id, "ok": False}

    # ① 创建或复用章节
    if not item_id:
        new_resp = new_article(book_id, volume_id)
        data = new_resp.get("data") or {}
        item_id = data.get("item_id") or data.get("id") or new_resp.get("item_id")
        if not item_id:
            result["new"] = new_resp
            result["error"] = f"创建章节失败: {new_resp.get('message')}"
            return result
        result["new"] = new_resp
        result["item_id"] = item_id

    # ② 预审
    result["audit"] = pre_audit_article(item_id, body_html)

    # ③ 发布
    result["publish"] = publish_article(book_id, item_id, volume_id, title, body_html,
                                        volume_name=volume_name)
    result["ok"] = str(result["publish"].get("code")) in ("0", "None", "none")
    if not result["ok"]:
        result["error"] = result["publish"].get("message")
    return result


# ==================== 收益查询（需 VM 加密接口） ====================
# 以下收益接口需要 X-Muye-Encrypt-Key 请求头 + 响应解密
# 加密函数由 scripts/fanqie_encrypt.js (Node.js) 提供
# 依赖：在技能目录执行 npm install crypto-js bignumber.js

import subprocess as _subprocess

_ENCRYPT_JS = os.path.join(_SCRIPT_DIR, "fanqie_encrypt.js")
_NODE_BIN = "node"


def _check_encrypt_dep():
    """检查加密模块依赖是否就绪"""
    if not os.path.exists(_ENCRYPT_JS):
        raise FileNotFoundError(
            f"加密模块不存在: {_ENCRYPT_JS}\n"
            "收益接口需要 VM 加密，请确保 scripts/fanqie_encrypt.js 和 references/vm_code.js 存在")
    node_modules = os.path.join(_SKILL_DIR, "node_modules")
    if not os.path.exists(node_modules):
        raise FileNotFoundError(
            f"Node.js 依赖未安装，请在技能目录执行:\n"
            f"  cd {_SKILL_DIR} && npm install crypto-js bignumber.js")


def _fetch_encrypted(path, params):
    """调用加密的收益接口（通过 Node.js 子进程完成加密/解密）

    内部调用 fanqie_encrypt.js 生成 X-Muye-Encrypt-Key，请求接口，解密响应。
    """
    _check_encrypt_dep()
    auth = load_auth()
    sec_ms = str(int(time.time() * 1000))

    # 构建查询参数
    query = {"aid": _AID, "app_name": _APP_NAME}
    query.update(params)
    query["sec_time"] = sec_ms

    # 调用 Node.js 脚本完成 加密→请求→解密 全流程
    js_script = f"""
const enc = require({_ENCRYPT_JS!r});
const https = require('https');
const url = require('url');

const o = enc.get_a();
const u = enc.get_A(o);

const params = {json.dumps(query)};
const msToken = {json.dumps(auth.get('ms_token', ''))};
const a_bogus = {json.dumps(auth.get('a_bogus', ''))};
const cookie = {json.dumps(auth.get('cookie', ''))};
const apiPath = {json.dumps(path)};
const bookPath = 'https://fanqienovel.com' + apiPath;

const qs = new URLSearchParams({{...params, msToken, a_bogus}}).toString();
const fullUrl = bookPath + '?' + qs;

const options = {{
    hostname: 'fanqienovel.com',
    path: '/' + fullUrl.split('/').slice(3).join('/'),
    method: 'GET',
    headers: {{
        'User-Agent': {_UA!r},
        'Cookie': cookie,
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://fanqienovel.com',
        'Referer': 'https://fanqienovel.com/main/writer/profit',
        'X-Muye-Encrypt-Key': u,
    }},
}};

const req = https.request(options, (res) => {{
    let raw = '';
    res.on('data', (c) => raw += c);
    res.on('end', () => {{
        const downgrade = res.headers['x-muye-encrypt-downgrade'];
        const respKey = res.headers['x-muye-encrypt-key'];
        if (downgrade && Number(downgrade) === 0 && respKey) {{
            try {{
                const decrypted = enc.get_res(respKey, o, raw);
                const result = typeof decrypted === 'string' ? JSON.parse(decrypted) : decrypted;
                process.stdout.write(JSON.stringify(result));
            }} catch(e) {{
                process.stdout.write(JSON.stringify({{code: -999, message: '解密失败: ' + e.message, raw: raw.substring(0, 200)}}));
            }}
        }} else {{
            try {{
                process.stdout.write(raw);
            }} catch(e) {{
                process.stdout.write(JSON.stringify({{code: -998, message: '非JSON响应', raw: raw.substring(0, 200)}}));
            }}
        }}
    }});
}});
req.on('error', (e) => {{
    process.stdout.write(JSON.stringify({{code: -997, message: '请求错误: ' + e.message}}));
}});
req.end();
"""

    try:
        result = _subprocess.run(
            [_NODE_BIN, "-e", js_script],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
            cwd=_SKILL_DIR,
        )
        if result.returncode != 0 and not result.stdout:
            raise RuntimeError(f"Node.js执行失败: {result.stderr[:500]}")
        return json.loads(result.stdout)
    except _subprocess.TimeoutExpired:
        return {"code": -996, "message": "请求超时"}
    except json.JSONDecodeError:
        return {"code": -995, "message": "响应解析失败", "raw": result.stdout[:200]}


def get_income_book_list():
    """收益页书籍列表（明文接口，不需加密）"""
    return _req("GET", "/api/author/income/book_list/v0/",
                params={"page_index": "0", "page_count": "200"})


def get_income_book_summary(book_id):
    """单本书收益汇总（加密接口）

    返回字段：novel_app_income(累计)、yesterday_income_novel_app(昨日)、
    novel_app_increase(增长率) 等
    """
    return _fetch_encrypted("/api/author/income/book_summary_v3/v0/",
                           {"book_id": book_id})


def get_income_book_daily(book_id, start_date="", end_date="", income_type="3"):
    """单本书每日收益明细（加密接口）

    :param start_date/end_date: 秒级时间戳，默认近30天
    :param income_type: 3=常规收益
    返回 income_daily_list，每条含 date/novel_app_read_fee/novel_app_total 等
    """
    now = int(time.time())
    if not start_date:
        start_date = str(now - 30 * 86400)
    if not end_date:
        end_date = str(now)
    return _fetch_encrypted("/api/author/income/book_daily_v3/v0/",
                           {"book_id": book_id, "income_type": income_type,
                            "start_date": start_date, "end_date": end_date})


def get_income_book_monthly(book_id, start_date="", end_date=""):
    """单本书月度收益（加密接口，长篇小说专用）

    :param start_date/end_date: 秒级时间戳，默认近半年
    返回 income_monthly_list，每条含 month/total/detail(分项明细)
    """
    now = int(time.time())
    if not start_date:
        start_date = str(now - 180 * 86400)
    if not end_date:
        end_date = str(now)
    return _fetch_encrypted("/api/author/income/book_monthly_v3/v0/",
                           {"book_id": book_id, "start_date": start_date, "end_date": end_date})


def get_income_gift_summary(book_id):
    """礼物收益汇总（加密接口）

    返回 gift_income(礼物总收入)、gift_count(礼物数量)
    """
    return _fetch_encrypted("/api/author/income/gift_summary_v1/v0/",
                           {"book_id": book_id})


def get_income_interaction_summary(book_id):
    """互动收益汇总（加密接口）

    返回 interaction_income(互动收入)、gift_count(礼物数)
    """
    return _fetch_encrypted("/api/author/income/interaction_summary/v0/",
                           {"book_id": book_id})


def get_income_completion_reward_list(book_id, page_index="0", page_count="20"):
    """完结奖励列表（明文接口）"""
    return _req("GET", "/api/author/income/completion_reward_list/v0/",
                params={"book_id": book_id, "page_index": page_index, "page_count": page_count})


def get_income_compensation_list(page_index="0", page_count="20"):
    """收益补偿列表（明文接口）"""
    return _req("GET", "/api/author/income_compensation/list/v0/",
                params={"page_index": page_index, "page_count": page_count})


# ==================== 评论 / 粉丝互动 ====================

def get_book_comment_list(book_id, days="", sort="", page_index=0, page_count=20,
                          user_filter="", scope_filter=""):
    """书评列表

    :param days: 时间范围筛选
    :param sort: 排序方式
    :param user_filter: 用户筛选
    :param scope_filter: 范围筛选
    """
    params = {"book_id": book_id, "page_index": page_index, "page_count": page_count}
    if days: params["days"] = days
    if sort: params["sort"] = sort
    if user_filter: params["user_filter"] = user_filter
    if scope_filter: params["scope_filter"] = scope_filter
    return _req("GET", "/api/author/comment/book_comment_list/v0/", params=params)


def get_chapter_comment_list(book_id, item_id, days="", sort="",
                              page_index=0, page_count=20):
    """章评列表

    :param item_id: 章节ID
    :param days: 时间范围筛选
    :param sort: 排序方式
    """
    params = {"book_id": book_id, "item_id": item_id,
              "page_index": page_index, "page_count": page_count}
    if days: params["days"] = days
    if sort: params["sort"] = sort
    return _req("GET", "/api/author/comment/chapter_comment_list/v0/", params=params)


def get_paragraph_comment_list(book_id, chapter_id, page_index=0, page_count=20):
    """段评列表

    :param chapter_id: 章节ID（item_id）
    """
    return _req("GET", "/api/author/comment/paragraph_comment_list/v0/",
                params={"book_id": book_id, "chapter_id": chapter_id,
                        "page_index": page_index, "page_count": page_count})


def get_reply_comment_list(comment_id, page_index=0, page_count=20):
    """评论的回复列表"""
    return _req("GET", "/api/author/comment/reply_comment_list/v0/",
                params={"comment_id": comment_id, "page_index": page_index, "page_count": page_count})


def reply_comment(comment_id, reply_content, to_reply_id=""):
    """回复评论（写操作）

    :param comment_id: 被回复的评论ID
    :param reply_content: 回复内容
    :param to_reply_id: 被回复的子回复ID（回复他人回复时传）
    """
    data = {"comment_id": comment_id, "reply_content": reply_content}
    if to_reply_id:
        data["to_reply_id"] = to_reply_id
    return _req("POST", "/api/author/comment/reply/v0/",
                data=data, need_sig=True, need_secsdk=True)


def delete_comment(comment_id, book_id=""):
    """删除评论（写操作）"""
    data = {"comment_id": comment_id}
    if book_id:
        data["book_id"] = book_id
    return _req("POST", "/api/author/comment/delete/v0/",
                data=data, need_sig=True, need_secsdk=True)


def digg_comment(comment_id, operator="1"):
    """点赞评论（写操作）

    :param operator: 1=点赞, 0=取消
    """
    return _req("POST", "/api/author/comment/digg/v0/",
                data={"comment_id": comment_id, "operator": operator},
                need_sig=True, need_secsdk=True)


def stick_comment(comment_id, stick_type, book_id=""):
    """置顶评论（写操作）

    :param stick_type: 1=置顶, 0=取消置顶
    """
    data = {"comment_id": comment_id, "stick_type": stick_type}
    if book_id:
        data["book_id"] = book_id
    return _req("POST", "/api/author/comment/stick_position/v0/",
                data=data, need_sig=True, need_secsdk=True)


def report_comment(comment_id, report_type, content="", book_id=""):
    """举报评论（写操作）

    :param report_type: 举报类型（见 get_comment_report_type_list）
    """
    data = {"comment_id": comment_id, "report_type": report_type, "content": content}
    if book_id:
        data["book_id"] = book_id
    return _req("POST", "/api/author/comment/report/v0/",
                data=data, need_sig=True, need_secsdk=True)


def get_comment_report_type_list():
    """举报类型列表"""
    return _req("GET", "/api/author/comment/report_type_list/v0/")


def get_author_speak_comment_list(book_id, page_index=0, page_count=20):
    """作者说评论列表（作者发布的"作者说"章节下的评论）"""
    return _req("GET", "/api/author/comment/author_speak_comment_list/v0/",
                params={"book_id": book_id, "page_index": page_index, "page_count": page_count})


def get_fan_list(book_id, page_index=0, page_count=20):
    """粉丝列表"""
    return _req("GET", "/api/author/comment/fan_list/v0/",
                params={"book_id": book_id, "page_index": page_index, "page_count": page_count})


def get_fan_mute_list(book_id, page_index=0, page_count=20):
    """禁言粉丝列表"""
    return _req("GET", "/api/author/comment/fan_mute_list/v0/",
                params={"book_id": book_id, "page_index": page_index, "page_count": page_count})


def mute_fan(fan_id, book_id, mute_type="1"):
    """禁言/解除禁言粉丝（写操作）

    :param mute_type: 1=禁言, 0=解除
    """
    return _req("POST", "/api/author/comment/mute/v0/",
                data={"fan_id": fan_id, "book_id": book_id, "mute_type": mute_type},
                need_sig=True, need_secsdk=True)


def get_fans_name(fan_ids):
    """获取粉丝昵称

    :param fan_ids: 粉丝ID列表（逗号分隔或列表）
    """
    if isinstance(fan_ids, list):
        fan_ids = ",".join(str(f) for f in fan_ids)
    return _req("GET", "/api/author/comment/get_fans_name/v0",
                params={"fan_ids": fan_ids})


# ==================== 签到 / 全勤 ====================

def get_attend_book_list():
    """签到书籍列表（需要签到的书）"""
    return _req("GET", "/api/author/attend/book_list/v0/")


def attend_book(book_id):
    """每日签到（写操作）

    每天更新章节后签到，影响全勤奖。
    """
    return _req("POST", "/api/author/attend/book_attend/v0",
                data={"book_id": book_id}, need_sig=True, need_secsdk=True)


def ask_for_leave(book_id, date, attend_activity_id=""):
    """请假（写操作）

    断更时主动请假，避免全勤奖清零。
    :param date: 请假日期（格式如 yyyy-mm-dd）
    :param attend_activity_id: 签到活动ID（可从 get_attend_activity 获取）
    """
    data = {"book_id": book_id, "date": date}
    if attend_activity_id:
        data["attend_activity_id"] = attend_activity_id
    return _req("POST", "/app/book/leave_attend/v0/",
                data=data, need_sig=True, need_secsdk=True)


def author_check_in():
    """作者每日签到（写操作，区别于书籍签到）"""
    return _req("POST", "/api/author/attend/author_check_in/v0",
                data={}, need_sig=True, need_secsdk=True)


def get_check_in_ticket_count():
    """签到券数量"""
    return _req("GET", "/api/author/attend/new_check_in_ticket_count/v0")


def get_check_in_ticket_list():
    """签到券列表"""
    return _req("GET", "/api/author/attend/check_in_ticket_list/v0")


def use_check_in_ticket(ticket_id, book_id):
    """使用签到券（写操作）

    可用于补签缺勤的日期。
    """
    return _req("POST", "/api/author/attend/use_check_in_ticket/v0",
                data={"ticket_id": ticket_id, "book_id": book_id},
                need_sig=True, need_secsdk=True)


# ==================== 通知 / 申诉 ====================

def get_notice_list(page_index=0, page_count=20, notice_type=""):
    """系统通知列表

    :param notice_type: 通知类型（空=全部）
    """
    params = {"page_index": page_index, "page_count": page_count}
    if notice_type:
        params["type"] = notice_type
    return _req("GET", "/api/author/notice/list/v0/", params=params)


def appeal_book_safe_reaudit(book_id, reason, content=""):
    """安全审核申诉（写操作）

    书被判定违规/隐藏后，提交申诉请求人工复核。
    :param reason: 申诉理由
    :param content: 补充说明
    """
    return _req("POST", "/api/author/appeal/book/safe_reaudit/v0/",
                data={"book_id": book_id, "reason": reason, "content": content},
                need_sig=True, need_secsdk=True)


# ==================== 定时发布 ====================

def modify_article_timer(item_id, timer_status, timer_time=""):
    """修改章节定时状态（写操作）

    已发布章节可修改/取消定时。
    :param timer_status: 1=启用定时, 0=取消定时
    :param timer_time: 定时时间（秒级时间戳字符串，取消时传空）
    """
    return _req("POST", "/api/author/article/modify_timer/v0/",
                data={"item_id": item_id, "timer_status": timer_status, "timer_time": timer_time},
                need_sig=True, need_secsdk=True)


# ==================== 便捷示例 ====================

if __name__ == "__main__":
    # 校验登录状态
    print(json.dumps(check_user_status(), ensure_ascii=False, indent=2)[:800])
