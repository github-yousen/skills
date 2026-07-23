"""
Boss直聘 API 客户端
基于逆向分析 www.zhipin.com 源码生成
用法:
    from api_client import search_jobs, get_cities
    # 先填入 Cookie
    # api_client._COOKIES = "你的Cookie字符串"
    jobs = search_jobs(keyword="产品经理")
"""
import urllib.request, urllib.parse, json, ssl, time, gzip, zlib

# ============================================================
# 配置区 — 用户在这里填入 Cookie
# ============================================================
_BASE_URL = "https://www.zhipin.com"
_COOKIES = ""  # TODO: 填入浏览器登录后的 Cookie

# ============================================================
# 内部: 通用请求
# ============================================================
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def _req(method, path, params=None, data=None, content_type=None):
    """通用 HTTP 请求：自动处理压缩、鉴权头、重试"""
    url = _BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://www.zhipin.com/web/geek/job",
        "Origin": "https://www.zhipin.com",
    }
    if _COOKIES:
        headers["Cookie"] = _COOKIES
    if content_type:
        headers["Content-Type"] = content_type

    body = None
    if data:
        if content_type == "application/json":
            body = json.dumps(data).encode("utf-8")
        else:
            body = urllib.parse.urlencode(data).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
                raw = resp.read()
                ce = resp.headers.get("Content-Encoding", "")
                if "gzip" in ce:
                    raw = gzip.decompress(raw)
                elif "deflate" in ce:
                    raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                ct = resp.headers.get("Content-Type", "")
                if "json" in ct or path.startswith("/wapi/"):
                    return json.loads(raw.decode("utf-8", errors="ignore"))
                return raw.decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as e:
            if attempt == 2:
                return {"error": f"HTTP {e.code}"}
            time.sleep(1)
        except Exception as e:
            if attempt == 2:
                return {"error": str(e)}
            time.sleep(1)

# ============================================================
# 城市/地区
# ============================================================

def get_cities():
    """获取全量城市区域数据 → 城市选择器"""
    return _req("GET", "/wapi/zpCommon/data/listForCityAreaGps")

def get_city_hot_areas(city_code):
    """获取城市热门区域 → 区域选择"""
    return _req("GET", "/wapi/zpCommon/data/getCityShowPosition",
                params={"cityCode": city_code})

# ============================================================
# 职位搜索
# ============================================================

def search_jobs(keyword="", city_code="", page=1, page_size=15,
                salary=None, experience=None, degree=None,
                job_type=None, publish_days=None, sort_type=None):
    """
    职位搜索 - 核心接口

    参数:
      keyword     - 搜索关键词
      city_code   - 城市编码（空=全国）
      page        - 页码
      page_size   - 每页条数
      salary      - 薪资编码，如 "1006"=20-30K
      experience  - 经验编码，如 "104"=3-5年
      degree      - 学历编码，如 "203"=本科
      job_type    - 类型: fulltime/parttime/intern
      publish_days- 发布天数: 1/3/7/15
      sort_type   - 排序: 0=综合 1=最新
    """
    data = {
        "query": keyword,
        "city": city_code,
        "page": page,
        "pageSize": page_size,
    }
    if salary:      data["salary"] = salary
    if experience:  data["experience"] = experience
    if degree:      data["degree"] = degree
    if job_type:    data["jobType"] = job_type
    if publish_days: data["publishDays"] = publish_days
    if sort_type:   data["sortType"] = sort_type

    return _req("POST", "/wapi/zprelation/interaction/geekGetJob",
                params={"tag": "4", "isActive": "true"},
                data=data)

def get_job_detail(item_id):
    """获取职位详情"""
    return _req("GET", "/wapi/zpitem/web/item/detail/info",
                params={"itemId": item_id})

def get_recommend_jobs():
    """获取个性化推荐职位"""
    return _req("GET", "/web/geek/recommend")

def get_job_competitive(item_id):
    """获取职位竞争分析"""
    return _req("GET", "/wapi/zpitem/web/competitive/use",
                params={"itemId": item_id})

# ============================================================
# 公司/品牌
# ============================================================

def search_brand(query):
    """品牌搜索建议"""
    return _req("GET", "/wapi/zpgeek/brand/suggest",
                params={"query": query})

def get_company_leaderboard():
    """公司榜单标签"""
    return _req("POST", "/wapi/zpCompany/leaderboard/getLabels")

# ============================================================
# 简历相关
# ============================================================

def get_deliver_list():
    """获取投递列表"""
    return _req("GET", "/wapi/zprelation/resume/geekDeliverList")

def get_resume():
    """获取简历信息"""
    return _req("GET", "/web/geek/resume")

def upload_resume(file_path):
    """上传简历文件"""
    # 需要构造 multipart/form-data，此处占位
    raise NotImplementedError("上传需用 requests 库处理 multipart")

# ============================================================
# 聊天/沟通
# ============================================================

def get_boss_data(encrypt_boss_id):
    """获取 Boss 信息"""
    return _req("GET", "/wapi/zpchat/geek/getBossData",
                params={"encryptBossId": encrypt_boss_id})

def get_chat_config():
    """获取聊天配置"""
    return _req("GET", "/wapi/zpchat/config/get")

def get_notify_settings():
    """获取通知设置"""
    return _req("GET", "/wapi/zpchat/notify/setting/get")

def update_notify_settings(**settings):
    """更新通知设置"""
    return _req("GET", "/wapi/zpchat/notify/setting/update", data=settings)

# ============================================================
# 兴趣/标签
# ============================================================

def get_job_interest_tags():
    """获取职位兴趣标签"""
    return _req("GET", "/wapi/zprelation/geekTag/job/interest")

def get_position_skills():
    """获取职位技能映射"""
    return _req("GET", "/common/data/positionSkill")
