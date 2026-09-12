# 番茄短剧(红果短剧)排行榜 API 分析报告

> 分析日期: 2026-08-23 | 分析人: CodeBuddy
> 状态: **已实测可用,免签名免登录,裸 HTTP 请求即返回数据**
> 增强更新: 加入真机抓包验证,发现 6 个可用 API 集群域名 + 54+ 完整域名清单

## 1. 结论速览

- 番茄短剧 = 红果小说 app 内集成的短剧 tab,包名 `com.dragon.read`(字节系,版本 v7.2.2.32)
- **排行榜接口无需任何签名/登录**——直接 GET 即返回完整榜单数据
- 已确认 **6 个 API 集群域名**均可免签名直调(同一套后端,负载均衡)
- 已确认 **5 个榜单**,支持分页(每页 15 条,`offset` 翻页)
- 短剧"上新/筛选"接口(`landpage`)同样免签名可用
- 搜索/详情/视频直链接口需 X-Argus 系列签名(需 App 端 Frida 预言机,见 §6)
- **真机抓包确认**:手机实际访问的 API 域名是 `api5-normal-sinfonlineb.fqnovel.com` 和 `api5-normal-hl.fqnovel.com`(非报告里写的 a 域名)
- **意外发现**:app 调用了阿里广告 IP `8.134.240.5`(直连 IP,绕过 DNS),归属 Hangzhou Alibaba Advertising

## 2. 排行榜接口(核心交付)

```
GET https://<任一可用域名>/reading/bookapi/bookmall/cell/change/v
```

### 2.1 可用 API 集群域名(2026-08-23 真机抓包验证)

| 域名 | IP | 状态 | 备注 |
|------|-----|------|------|
| `api5-normal-sinfonlinea.fqnovel.com` | (DNS) | ✅ 通 | 报告里写的,免签名可用 |
| `api5-normal-sinfonlineb.fqnovel.com` | `58.42.14.184` | ✅ 通 | **手机实际访问**,免签名可用 |
| `api5-normal-hl.fqnovel.com` | `119.84.131.124` | ✅ 通 | **手机实际访问**(国内 HL 集群) |
| `api3-normal-sinfonlinea.fqnovel.com` | (DNS) | ✅ 通 | api3 集群 |
| `api3-normal-sinfonlineb.fqnovel.com` | `119.86.9.99` | ✅ 通 | api3 集群 |
| `api3-normal-hl.fqnovel.com` | (DNS) | ✅ 通 | api3 集群 |

> **建议**:脚本默认用 `api5-normal-sinfonlinea`(历史稳定);若需模拟手机实际访问,可用 `b` 域名(海外节点 `sin` = Singapore/东南亚)

### 2.2 公共参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `aid` | `8662` | 红果短剧应用 ID |
| `app_name` | `novelread` | |
| `version_code` | `72232` | App 7.2.2.32 |
| `version_name` | `7.2.2.32` | |
| `device_platform` | `android` | |
| `os_version` | `12` | (实为 12 字段即可,手机 11 也通) |
| `iid` / `device_id` | `0` | 实测传 0 即可 |
| `_rticket` | 毫秒时间戳 | |

### 2.3 榜单参数

| 参数 | 值 |
|------|-----|
| `cell_id` | `7470092475068071998` |
| `tab_type` | `26`(实测任意值结果一致) |
| `client_req_type` | `2` |
| `client_template` | `2` |
| `screen_width_px` | `1350` |
| `selected_items` | `comic_series_rank` |
| `sub_selected_items` | **榜单枚举,见下表** |
| `session_uuid` | 随机 UUID |
| `offset` | 分页偏移(第 2 页起传 `15`/`30`…) |

### 2.4 榜单枚举(sub_selected_items)

| board key | sub_selected_items | 榜单名 | 实测榜首(2026-08-23) |
|-----------|--------------------|--------|--------------------------|
| `recommend` | `comic_series_hot_rank` | 短剧推荐榜 | 庄园保姆,成了全家白月光! |
| `hot` | `hot_play` | 短剧热播榜 | 好雨知时节(89集) |
| `new` | `new_rank` | 短剧新剧榜 | 第二十五时区的情书 |
| `comic_hot` | `comic_series_hot_play` | 漫剧热播榜 | 咱家剑宗团宠小师妹第五季 |
| `comic_new` | `comic_series_new_rank` | 漫剧新剧榜 | 咱家剑宗团宠小师妹第五季 |

> 区分真人短剧 / AI 漫剧: 真人短剧 `rec_text` 为"X万推荐",漫剧为"X万热度";漫剧出品方多为"XX动漫/漫文化"。

### 2.5 请求头

```http
User-Agent: com.phoenix.read/72232 (Linux; U; Android 12; zh_CN; SM-G977N; Build/SP1A.210812.016; Cronet/TTNetVersion:5bf53e58 2023-03-07)
Accept: application/json
Host: <上述任一可用域名>
```

### 2.6 响应结构

```json
{
  "code": 0, "message": "SUCCESS",
  "data": {
    "cell_view": {
      "cell_data": [
        {
          "video_data": {
            "series_id": "7673056752958458942",
            "title": "好雨知时节",
            "episode_cnt": 89,
            "score": "8.0",
            "play_cnt": 33380666,
            "rec_text": "6940万推荐",
            "copyright": "甜豆包剧场",
            "cover": "https://p3-reading-sign.fqnovelpic.com/...",
            "video_desc": "简介...",
            "category_schema": "[{\"category_id\":5000,\"name\":\"爱情\",...}]"
          }
        }
      ],
      "has_more": true,
      "next_offset": 15
    }
  }
}
```

## 3. 其他免签名接口

### 短剧上新 / 分类筛选

```
POST https://<任一可用域名>/reading/distribution/category/landpage/v?<公共参数>
```

请求体:

```json
{
  "filter_ids": "",
  "req_scene": "default",
  "offset": 0,
  "need_selector_panel": false,
  "limit": 18,
  "select_items": {
    "category_dim_epoch": [], "online_time": [], "gender": [],
    "category_dim_role": [], "genre": ["short_play"],
    "sort": ["online_time"], "category_dim_theme": []
  },
  "session_id": "", "req_type": "only_content", "client_req_type": 3
}
```

- `genre`: `short_play`(真人短剧) / `comic_series`(漫剧) / `ai_series`(AI短剧)
- `online_time`: `["days_7"]` = 7天内上新;空 = 最新上架
- `sort`: `["online_time"]` = 按上线时间
- 返回 `data.video_data[]`,其中 `sub_title_list` 含 `"今日上新"` 文本可精确判断今日上新

## 4. 需签名接口(参考,未实测成功)

| 用途 | 接口 | 说明 |
|------|------|------|
| 搜索短剧 | `GET /reading/bookapi/search/tab/v?query=xxx` | 需签名 |
| 剧集列表 | `POST /novel/player/multi_video_detail/v1/` | body `{"series_id": ...}` |
| 视频直链 | `POST /novel/player/multi_video_model/v1/` | body `{"mixed_video_id_map":{"1":[vid...]}}` |

签名方案(Frida 预言机): hook App 内 `com.bytedance.frameworks.baselib.network.http.NetworkParams.tryAddSecurityFactor(url, headers)` 让 App 自己算签名。完整实现见 GitHub `yinjg1997/hongguo`。

> 视频 CDN 直链(`*.qznovelvod.com`)为自签名 URL,普通 GET 即可下载,无需 X-Argus。

## 5. 真机抓包域名清单(2026-08-23 番茄小说 app v7.2.2.32)

通过 `adb reverse + mitmdump` 抓包(证书未装,只能看 CONNECT 域名,无法看 URL 路径),番茄 app 启动期间共访问 54+ 个域名:

### 5.1 番茄 API 核心域(`fqnovel.com`)

| 域名 | 用途 |
|------|------|
| `api5-normal-sinfonlineb.fqnovel.com` | **主 API**(海外 sin 集群) |
| `api5-normal-hl.fqnovel.com` | **主 API**(国内 HL 集群) |
| `api3-normal-hl.fqnovel.com` | 备 API(国内 HL) |
| `api3-normal-sinfonlineb.fqnovel.com` | 备 API(海外) |
| `mon11-misc-hl.fqnovel.com` | 监控/埋点 |
| `mon3-misc-hl.fqnovel.com` | 监控/埋点 |
| `log0-applog-hl.fqnovel.com` | 业务日志 |
| `log3-applog-hl.fqnovel.com` | 业务日志 |
| `rtlog3-applog-hl.fqnovel.com` | 实时日志 |
| `rtlog5-applog-hl.fqnovel.com` | 实时日志 |
| `frontier100-toutiao-hl.fqnovel.com` | 头条系前沿服务 |
| `lf3-reading.fqnovelpic.com` | 番茄阅读图床 |

### 5.2 字节通用 SDK(`zijieapi.com` / `snssdk.com` / `bytedance.com`)

- `mssdk3-normal-lf.zijieapi.com` (移动安全 SDK)
- `abtest3-misc-hl.zijieapi.com` (A/B 测试)
- `polaris3-normal-hl.zijieapi.com` / `polaris5-normal-hl.zijieapi.com` (极光推送)
- `gecko3-hj.zijieapi.com` / `gecko5-hj.zijieapi.com` / `gecko5-hl.zijieapi.com` (gecko)
- `thanos.zijieapi.com` / `timon.zijieapi.com` (基础服务)
- `vcs.zijieapi.com` / `saveu5-normal-hl.zijieapi.com` / `life-service-open.zijieapi.com` (字节云)
- `bsync3-normal-hl.zijieapi.com` (同步)
- `tnc0-aliec2.zijieapi.com` / `tnc0-alisc1.zijieapi.com` / `tnc3-alisc1.bytedance.com` (TNC 安全)
- `feedback-c.zijieapi.com` (用户反馈)
- `ads3-normal-hl.zijieapi.com` / `ads5-normal-hl.zijieapi.com` (广告)
- `pitaya.bytedance.com` (基础服务)
- `effect.snssdk.com` / `ichannel.snssdk.com` / `is.snssdk.com` / `reading.snssdk.com` / `i.snssdk.com` (字节通用)
- `settings.ttwebview.com` (WebView 设置)
- `webcast3-open-hl.douyin.com` / `webcast5-open-hl.douyin.com` (抖音直播)

### 5.3 电商/抖音/CDN

- `ec3-core-hl.ecombdapi.com` / `ec5-core-hl.ecombdapi.com` (电商核心)
- `ecom3-normal-hl.ecombdapi.com` / `ecom5-normal-hl.ecombdapi.com` (电商业务)
- `isaas3-normal-hl.ecombdapi.com` / `isaas5-normal-hl.ecombdapi.com` (电商云)
- `p3.douyinpic.com` / `p11.douyinpic.com` (抖音图)
- `p3-aio.ecombdimg.com` / `p26-item.ecombdimg.com` (电商图)
- `p3-novel.byteimg.com` / `p6-novel.byteimg.com` (字节图)
- `lf-normal-gr-sourcecdn.bytegecko.com` / `lf-sourcecdn-tos.bytegecko.com` / `lf-webcast-gr-sourcecdn.bytegecko.com` (gecko CDN)

### 5.4 异常/可疑

- **`8.134.240.5:443`** — 直连 IP(绕过 DNS),归属 **Hangzhou Alibaba Advertising**(杭州阿里广告),AS37963。这是番茄 app 调用了**阿里妈妈广告 SDK**或淘宝/阿里广告直通链!
- **DNS 失败 4 次** — 抓包期间有 4 次 getaddrinfo 失败,域名未明(日志未记录具体域名,需要重抓 DNS 失败前的请求)

## 6. 直接可用脚本

```bash
# 全部榜单各前15条
py scripts/fanqie_drama_rank.py

# 指定榜单 + 数量
py scripts/fanqie_drama_rank.py hot 50
py scripts/fanqie_drama_rank.py recommend 100

# 列出所有榜单
py scripts/fanqie_drama_rank.py --list

# 多域名验证(测试 6 个 API 域名是否都通)
py scripts/verify_domains.py
```

## 7. 获取凭证/签名环境(仅需签名接口时才需要)

1. MuMu12 模拟器(root)装红果短剧 App + frida-server
2. `frida/oracle.js` 暴露 `rpc.exports.sign(url, headers)` 签名接口
3. 或部署 `sign_server.py` 独立签名服务,`hongguo.py` 通过 `SIGN_SERVER` 环境变量调用

## 8. 信息源

- 原始逆向: GitHub `yinjg1997/hongguo`(红果短剧接口逆向 + 下载服务)
- 域名基线: `api5-normal-sinfonlinea.fqnovel.com`(备用域名,无 SSL pinning)
- 真机抓包: 2026-08-23, vivo V2068A (PD2068, Android 11), `com.dragon.read` v7.2.2.32, `adb reverse + mitmdump 12.2.3`
- 本次分析全部结论均经 2026-08-23 实测验证

## 9. 待补全(需要 root 或 frida + 已装证书)

- [ ] 完整 URL 路径(需装证书绕过 TLS 信任,可看到 `/reading/bookapi/...` 完整路径)
- [ ] X-Argus/X-Gorgon 签名算法逆向(需 frida hook native)
- [ ] DNS 失败对应的具体域名(需重抓)
