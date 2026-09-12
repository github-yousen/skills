# fanqienovel.com 操作手册

> 首次分析时间：2026-08-05T14:57:09.807390
> 目标网站：https://fanqienovel.com/main/writer/book-manage
> 文档用途：**下次直接看本文档操作，无需重新分析**

> ⚠️ 本文档由脚本自动生成骨架，`{...}` / TODO 处需结合源码人工补全。

---

## 一、基本信息

| 项目 | 内容 |
|------|------|
| 目标 URL | https://fanqienovel.com/main/writer/book-manage |
| 前端框架 | 未识别 |
| 打包工具 | 未识别 |
| 状态管理 | 未识别 |
| Source Map | 无/未还原 |
| 主 JS 文件 | `main.e63907e3.js` |

---

## 二、凭证说明

> 根据源码中出现的鉴权关键词推断，需结合实际确认。

- **检测到的鉴权关键词**：Authorization, Bearer, Cookie, Token, auth, csrf, csrf_token, getToken, interceptors.request, interceptors.response, localStorage.setItem, login, logout, refreshToken, sessionStorage.setItem, setToken, token, withCredentials
- **检测到的签名/加密关键词**：access_token, appkey, decrypt, encrypt, hmac, md5, mixin_key_array, sha256, sign, wbi, wts

**获取 Cookie**：浏览器登录 → F12 → Application → Cookies → 复制对应域名的值

---

## 三、API 接口清单

> 共提取 530 个接口（含 chunk / sourcemap 还原源码）。

### 认证 / 用户

| 方法 | 路径 | 来源JS |
|------|------|--------|
| GET? | `/api/user/author/login/callback` | main.e63907e3.js |
| GET? | `/api/author/homepage/book_list/v0/` | main.e63907e3.js |
| GET? | `/api/author/data/upload_pic_v2/v0/` | main.e63907e3.js |
| GET? | `/api/author/notice/list/v0/` | main.e63907e3.js |
| GET? | `/api/author/attend/book_list/v0/` | main.e63907e3.js |
| GET? | `/api/author/stats/author/v0/` | main.e63907e3.js |
| GET? | `/api/author/attend/book_attend/v0/` | main.e63907e3.js |
| GET? | `/api/author/attend/book_attend_activity/v0` | main.e63907e3.js |
| GET? | `/api/author/attend/ask_for_leave/v0/` | main.e63907e3.js |
| GET? | `/api/author/book/category_list/v0/` | main.e63907e3.js |
| GET? | `/api/author/book/group_category_list/v0/` | main.e63907e3.js |
| GET? | `/api/author/book/create/v0/` | main.e63907e3.js |
| GET? | `/api/author/book/delete/v0` | main.e63907e3.js |
| GET? | `/api/author/book/top_hide/v0/` | main.e63907e3.js |
| GET? | `/api/author/volume/volume_list/v1` | main.e63907e3.js |
| GET? | `/api/author/chapter/chapter_list/v1` | main.e63907e3.js |
| GET? | `/api/author/delete_article/v1` | main.e63907e3.js |
| GET? | `/api/author/chapter/draft_list/v1` | main.e63907e3.js |
| GET? | `/api/author/search/search_chapter/v0` | main.e63907e3.js |
| GET? | `/api/author/short_article/new/v0/` | main.e63907e3.js |
| GET? | `/api/author/short_article/publish/v0/` | main.e63907e3.js |
| GET? | `/api/author/short_article/edit/v1/` | main.e63907e3.js |
| GET? | `/api/author/short_article/cover/v0/` | main.e63907e3.js |
| GET? | `/api/author/short_article/get_category/v0/` | main.e63907e3.js |
| GET? | `/api/author/short_article/get_category_list/v0/` | main.e63907e3.js |
| GET? | `/api/author/short_article/get_category_list/v1/` | main.e63907e3.js |
| GET? | `/api/author/short_article/apply_list/v0/` | main.e63907e3.js |
| GET? | `/api/author/short_article/apply_user_info/v0/` | main.e63907e3.js |
| GET? | `/api/author/short_article/apply/v0` | main.e63907e3.js |
| GET? | `/api/author/short_article/apply_modify/v0/` | main.e63907e3.js |
| GET? | `/api/author/sa_activity/activity_list/v0/` | main.e63907e3.js |
| GET? | `/api/author/short_article/appeal/v0/` | main.e63907e3.js |
| GET? | `/api/author/short_article/check_pre/v0` | main.e63907e3.js |
| GET? | `/api/author/short_article/publish_wtt/v0/` | main.e63907e3.js |
| GET? | `/api/author/short_article/card_list/v0/` | main.e63907e3.js |
| GET? | `/api/author/short_article/wtt_list/v0/` | main.e63907e3.js |
| GET? | `/api/author/short_article/wtt_draft_list/v0/` | main.e63907e3.js |
| GET? | `/api/author/short_article/delete_wtt/v0/` | main.e63907e3.js |
| GET? | `/api/author/book/get_book_outline/v0/` | main.e63907e3.js |
| GET? | `/api/author/book/update_book_outline/v0/` | main.e63907e3.js |
| GET? | `/api/author/article/publish_speak/v0` | main.e63907e3.js |
| GET? | `/api/author/article/delete_speak/v0` | main.e63907e3.js |
| GET? | `/api/author/article/get_speak/v0` | main.e63907e3.js |
| GET? | `/api/author/comment/author_speak_comment_list/v0` | main.e63907e3.js |
| GET? | `/api/author/article/get_speak_popup/v0/` | main.e63907e3.js |
| GET? | `/api/author/article/traffic_book_list/v0/` | main.e63907e3.js |
| GET? | `/api/author/article/check_traffic_book/v0/` | main.e63907e3.js |
| GET? | `/api/author/article/check_trafficed_book/v0/` | main.e63907e3.js |
| GET? | `/api/author/edit_article/v0/` | main.e63907e3.js |
| GET? | `/api/author/article/new_article/v0/` | main.e63907e3.js |
| GET? | `/api/author/publish_article/v0/` | main.e63907e3.js |
| GET? | `/api/author/volume/add_volume/v0` | main.e63907e3.js |
| GET? | `/api/author/volume/modify/v0` | main.e63907e3.js |
| GET? | `/api/author/volume/delete_volume/v0/` | main.e63907e3.js |
| GET? | `/api/author/inset/qualification/v0` | main.e63907e3.js |
| GET? | `/api/author/inset/set_answer_status/v0/` | main.e63907e3.js |
| GET? | `/api/author/inset/upload_pic/v0/` | main.e63907e3.js |
| GET? | `/api/author/inset/emoticon_search/v0/` | main.e63907e3.js |
| GET? | `/api/author/correction_feedback/add_ignore_record/v0/` | main.e63907e3.js |
| GET? | `/api/author/article/cover_article/v0/` | main.e63907e3.js |
| GET? | `/api/author/article/get_latest_article/v0/` | main.e63907e3.js |
| GET? | `/api/author/article/save_doc_history/v0/` | main.e63907e3.js |
| GET? | `/api/author/article/get_doc_history/v0/` | main.e63907e3.js |
| GET? | `/api/author/article/get_doc_snapshot/v0/` | main.e63907e3.js |
| GET? | `/api/author/article/get_access_key/v0/` | main.e63907e3.js |
| GET? | `/api/author/spot_fire/book_list/v0/` | main.e63907e3.js |
| GET? | `/api/author/spot_fire/stat_list/v0/` | main.e63907e3.js |
| GET? | `/api/author/invite/info/v0/` | main.e63907e3.js |
| GET? | `/api/author/invite/list/v0/` | main.e63907e3.js |
| GET? | `/api/author/book/modify_book/v0/` | main.e63907e3.js |
| GET? | `/api/author/book/book_detail/v0/` | main.e63907e3.js |
| GET? | `/api/author/book/creation_apply/v0/` | main.e63907e3.js |
| GET? | `/api/author/banned/info/v0/` | main.e63907e3.js |
| GET? | `/api/author/audit/detect_input/v0/` | main.e63907e3.js |
| GET? | `/api/author/verify/check_user_status/v0` | main.e63907e3.js |
| GET? | `/api/author/activity/activity_list/v0/` | main.e63907e3.js |
| GET? | `/api/author/book/book_list/v0` | main.e63907e3.js |
| GET? | `/api/author/article/modify_timer/v0/` | main.e63907e3.js |
| GET? | `/api/author/article/handle_timer_preview/v0/` | main.e63907e3.js |
| GET? | `/api/author/benefits/history_book/v0` | main.e63907e3.js |
| ... | 其余 266 个见 analysis_report.json | |

### 内容 / 列表

| 方法 | 路径 | 来源JS |
|------|------|--------|
| GET? | `/api/node/activity/list` | main.e63907e3.js |
| GET? | `/api/config/list/` | main.e63907e3.js |
| GET? | `/api/rank/category/list` | main.e63907e3.js |
| GET? | `/api/node/ai/style/list` | main.e63907e3.js |
| GET? | `/api/origin/activity/novel/book_attend_list/v0/` | main.e63907e3.js |
| GET? | `/app/book/book_list/v0/` | main.e63907e3.js |
| GET? | `/app/book/chapter_list/v0/` | main.e63907e3.js |
| GET? | `/app/book/draft_list/v0/` | main.e63907e3.js |
| GET? | `/app/book/volume_list/v0/` | main.e63907e3.js |
| GET? | `/app/book/book_detail/v0/` | main.e63907e3.js |
| GET? | `/app/book/category_list/v0/` | main.e63907e3.js |
| GET? | `/app/book/attend_list/v0/` | main.e63907e3.js |
| GET? | `/app/book/group_category_list/v0/` | main.e63907e3.js |
| GET? | `/app/book/recommend_info/v0/` | main.e63907e3.js |
| GET? | `/app/book/operate_recommend/v0/` | main.e63907e3.js |
| GET? | `/app/book/referral_traffic/new_book_list/v0/` | main.e63907e3.js |
| GET? | `/app/book/short_article/draft_list/v0/` | main.e63907e3.js |
| GET? | `/app/book/short_article/list/v0/` | main.e63907e3.js |
| GET? | `/app/book/book_list/v1/` | main.e63907e3.js |
| GET? | `/app/book/correction_feedback/add_ignore_record/v0/` | main.e63907e3.js |
| GET? | `/app/book/correction_feedback/list/v0/` | main.e63907e3.js |
| GET? | `/app/book/multiple_name/infos/v0/` | main.e63907e3.js |
| GET? | `/app/book/multiple_name/book_list/v0/` | main.e63907e3.js |
| GET? | `/app/book/traffic_book_list/v0/` | main.e63907e3.js |
| GET? | `/app/book/short_article/get_category_list/v0/` | main.e63907e3.js |
| GET? | `/app/book/pre_sign_book_list/v0/` | main.e63907e3.js |
| GET? | `/app/book/contract/bank_info/v0/` | main.e63907e3.js |
| GET? | `/app/book/contract/contract_detail/v0/` | main.e63907e3.js |
| GET? | `/app/book/short_article/douyin_hot_list/v0/` | main.e63907e3.js |
| GET? | `/app/book/chapter_adjust/book_list/v0/` | main.e63907e3.js |
| GET? | `/app/book/chapter_adjust/chapter_list/v0/` | main.e63907e3.js |
| GET? | `/app/book/reputation_name/list/v0/` | main.e63907e3.js |
| GET? | `/app/book/ai/chat_record_list/v0/` | main.e63907e3.js |
| GET? | `/app/book/search_chapter/v0/` | main.e63907e3.js |
| GET? | `/app/book/banned/info/v0/` | main.e63907e3.js |
| GET? | `/app/book/video/list/v1/` | main.e63907e3.js |
| GET? | `/app/book/check_in_ticket_list/v0/` | main.e63907e3.js |
| GET? | `/app/book/ai/consult_first_recommend_questions/v0/` | main.e63907e3.js |
| GET? | `/app/book/album/list/v1/` | main.e63907e3.js |
| GET? | `/app/book/album/search_video_list/v1/` | main.e63907e3.js |
| GET? | `/app/book/album/get_video_list/v1/` | main.e63907e3.js |
| GET? | `/app/book/ai/diagnose/book_list/v0/` | main.e63907e3.js |
| GET? | `/app/book/album/search_video_list_v2/v1/` | main.e63907e3.js |
| GET? | `/app/book/pre_audit_article_feedback/v0/` | main.e63907e3.js |
| GET? | `/app/book/short_article/get_category_list/v1/` | main.e63907e3.js |
| GET? | `/app/book/operate_recommend/v1/` | main.e63907e3.js |
| GET? | `/app/book/recommend_info/v1/` | main.e63907e3.js |
| GET? | `/app/node/config/list` | main.e63907e3.js |
| GET? | `/app/node/rank/category/list` | main.e63907e3.js |
| GET? | `/app/node/ai/style/list` | main.e63907e3.js |
| GET? | `/app/home/message/book_problem_mark_info_read_mark/v0` | main.e63907e3.js |
| GET? | `/v1/list_test` | 9558.6e1b4aa7.js |

### 业务接口

| 方法 | 路径 | 来源JS |
|------|------|--------|
| GET? | `/api/node/editor/typo_backflow` | main.e63907e3.js |
| GET? | `/api/image/crop` | main.e63907e3.js |
| GET? | `/api/node/income/gift/summary/` | main.e63907e3.js |
| GET? | `/api/node/data/antidirt/v0/` | main.e63907e3.js |
| GET? | `/api/node/story/generation_chapter/v0/` | main.e63907e3.js |
| GET? | `/api/node/story/chapter_backflow/v0/` | main.e63907e3.js |
| GET? | `/api/origin/activity/novel/libra_propeties/v0` | main.e63907e3.js |
| GET? | `/api/origin/activity/novel/book_attend_activity/v0/` | main.e63907e3.js |
| GET? | `/api/node` | main.e63907e3.js |
| GET? | `/api/origin` | main.e63907e3.js |
| GET? | `/pgc/serial/novel/contract/download_contract/` | main.e63907e3.js |
| GET? | `/app/book/article/v0/` | main.e63907e3.js |
| GET? | `/app/book/publish_article/v0/` | main.e63907e3.js |
| GET? | `/app/book/edit_article/v0/` | main.e63907e3.js |
| GET? | `/app/book/delete_article/v0/` | main.e63907e3.js |
| GET? | `/app/book/creation_apply/v0/` | main.e63907e3.js |
| GET? | `/app/book/upload_pic/v0/` | main.e63907e3.js |
| GET? | `/app/book/modify_book/v0/` | main.e63907e3.js |
| GET? | `/app/book/create/v0/` | main.e63907e3.js |
| GET? | `/app/book/modify_volume/v0/` | main.e63907e3.js |
| GET? | `/app/book/add_volume/v0/` | main.e63907e3.js |
| GET? | `/app/book/delete/v0/` | main.e63907e3.js |
| GET? | `/app/book/delete_speak/v0/` | main.e63907e3.js |
| GET? | `/app/book/publish_speak/v0/` | main.e63907e3.js |
| GET? | `/app/book/get_speak/v0/` | main.e63907e3.js |
| GET? | `/app/book/book_attend/v0/` | main.e63907e3.js |
| GET? | `/app/book/leave_attend/v0/` | main.e63907e3.js |
| GET? | `/app/book/edit_article/v1/` | main.e63907e3.js |
| GET? | `/app/book/delete_volume/v0/` | main.e63907e3.js |
| GET? | `/app/book/modify_article_timer/v0/` | main.e63907e3.js |
| GET? | `/app/book/sign_apply/v0/` | main.e63907e3.js |
| GET? | `/app/book/get_poster/v0/` | main.e63907e3.js |
| GET? | `/app/book/send_highlight/v0/` | main.e63907e3.js |
| GET? | `/app/book/top_hide/v0/` | main.e63907e3.js |
| GET? | `/app/book/update_book_outline/v0/` | main.e63907e3.js |
| GET? | `/app/book/get_book_outline/v0/` | main.e63907e3.js |
| GET? | `/app/book/referral_traffic/publish/v0/` | main.e63907e3.js |
| GET? | `/app/book/referral_traffic/latest/v0/` | main.e63907e3.js |
| GET? | `/app/book/cover_article/v0/` | main.e63907e3.js |
| GET? | `/app/book/get_doc_snapshot/v0/` | main.e63907e3.js |
| GET? | `/app/book/get_doc_history/v0/` | main.e63907e3.js |
| GET? | `/app/book/save_doc_history/v0/` | main.e63907e3.js |
| GET? | `/app/book/get_latest_article/v0/` | main.e63907e3.js |
| GET? | `/app/book/new_article/v0/` | main.e63907e3.js |
| GET? | `/app/book/short_article/publish/v0/` | main.e63907e3.js |
| GET? | `/app/book/short_article/delete/v0/` | main.e63907e3.js |
| GET? | `/app/book/short_article/new/v0/` | main.e63907e3.js |
| GET? | `/app/book/short_article/edit/v0/` | main.e63907e3.js |
| GET? | `/app/book/short_article/cover/v0/` | main.e63907e3.js |
| GET? | `/app/book/short_article/get_category/v0/` | main.e63907e3.js |
| GET? | `/app/book/short_article/get_cover/v0/` | main.e63907e3.js |
| GET? | `/app/book/set_advert/v0/` | main.e63907e3.js |
| GET? | `/app/book/get_advert_msg/v0/` | main.e63907e3.js |
| GET? | `/app/book/appeal/safe_reaudit/v0/` | main.e63907e3.js |
| GET? | `/app/book/multiple_name/check_name/v0/` | main.e63907e3.js |
| GET? | `/app/book/multiple_name/confirm/v0/` | main.e63907e3.js |
| GET? | `/app/book/multiple_name/publish/v0/` | main.e63907e3.js |
| GET? | `/app/book/multiple_name/pause/v0/` | main.e63907e3.js |
| GET? | `/app/book/check_traffic_book/v0/` | main.e63907e3.js |
| GET? | `/app/book/check_trafficed_book/v0` | main.e63907e3.js |
| GET? | `/app/book/get_speak_popup/v0/` | main.e63907e3.js |
| GET? | `/app/book/contract/contract_history/v0/` | main.e63907e3.js |
| GET? | `/app/book/contract/person_audit/v0/` | main.e63907e3.js |
| GET? | `/app/book/contract/contract_modify/v0/` | main.e63907e3.js |
| GET? | `/app/book/contract/ea_apply/v0/` | main.e63907e3.js |
| GET? | `/app/book/contract/bank_name/v0/` | main.e63907e3.js |
| GET? | `/app/book/contract/contract_apply/v0/` | main.e63907e3.js |
| GET? | `/app/book/book_attend_activity/v0/` | main.e63907e3.js |
| GET? | `/app/book/contract/esign_call_back/v0/` | main.e63907e3.js |
| GET? | `/app/book/contract/contract_download/v0/` | main.e63907e3.js |
| GET? | `/app/book/short_article/apply/v0/` | main.e63907e3.js |
| GET? | `/app/book/chapter_adjust/apply/v0/` | main.e63907e3.js |
| GET? | `/app/book/chapter_adjust/adjust/v0/` | main.e63907e3.js |
| GET? | `/app/book/reputation_name/delete/v0/` | main.e63907e3.js |
| GET? | `/app/book/reputation_name/publish/v0/` | main.e63907e3.js |
| GET? | `/app/book/ai/generate_naming/v0/` | main.e63907e3.js |
| GET? | `/app/book/ai/qualification/v0/` | main.e63907e3.js |
| GET? | `/app/book/ai/set_agreement/v0/` | main.e63907e3.js |
| GET? | `/app/book/ai/generate_rewrite/v0/` | main.e63907e3.js |
| GET? | `/app/book/ai/get_rewrite/v0/` | main.e63907e3.js |
| ... | 其余 51 个见 analysis_report.json | |

### 上报 / 监控

| 方法 | 路径 | 来源JS |
|------|------|--------|
| GET? | `/api/web-cmp/v1/report/` | .js |

---

## 四、页面功能地图

| 路径 | 名称/说明 |
|------|-----------|
| `/name-experiment` |  |
| `/multi-cover` |  |
| `/home` |  |
| `/book-manage?type=1` |  |
| `/book-manage` |  |
| `/short-manage` |  |
| `/data` |  |
| `/short-data` |  |
| `/profit?enter_from=` |  |
| `/short-income` |  |
| `/interactive` |  |
| `/comment-manage?type=0` |  |
| `/reward-manage` |  |
| `/speak-manage` |  |
| `/fans-manage?type=1` |  |
| `/inspiration?type=0` |  |
| `/preheating` |  |
| `/reputation` |  |
| `/welfare?type=6` |  |
| `/level` |  |
| `/` |  |
| `/create` |  |
| `/short-draft` |  |
| `/short-sign` |  |
| `/short-recommend` |  |
| `/short-recommend-draft` |  |
| `/book-info/:bookId` |  |
| `/chapter-manage/:bookData` |  |
| `/:bid/publish/:iid?` |  |
| `/publish-short/:iid?` |  |
| `/message` |  |
| `/welfare` |  |
| `/sign/:bid` |  |
| `/profit` |  |
| `/compensate` |  |
| `/comment-manage` |  |
| `/comment-manage/paragraph/:bookId/:data?` |  |
| `/comment-manage/chapter/:bookId/:itemId?` |  |
| `/comment-speak/comment/:bookId/:itemId?` |  |
| `/user-info` |  |
| `/interactive/topic` |  |
| `/add-topic/:id?` |  |
| `/author` |  |
| `/login` |  |
| `/fans-manage` |  |
| `/notice` |  |
| `/preview/:chapterData` |  |
| `/preview-short/:chapterData` |  |
| `/inspiration` |  |
| `/inspiration/rank` |  |
| `/publish-playlet/:bookId/:itemId?` |  |
| `/playlet-chapter/:bid?` |  |
| `/playlet-sign/:bid?` |  |
| `/playlet-edit/:bid?` |  |
| `/playlet-info/:bid?` |  |
| `/playlet-manage` |  |
| `/playlet-auth` |  |
| `/playlet-data` |  |
| `/chapter-problem-detail/:bookId?` |  |

---

## 五、域名体系

| 域名 | 用途 |
|------|------|
| `lf-serial-static.fanqienovel.com` | 静态资源/CDN |
| `lf1-cdn-tos.bytegoofy.com` | 静态资源/CDN |
| `privacy.zijieapi.com` | API 接口 |
| `ipolyfill-origin.bytedance.com` | 其它 |
| `lf-c-flwb.bytetos.com` | 其它 |
| `lf-security.bytegoofy.com` | 其它 |
| `fanqienovel.com` | 主站 |

---

## 六、附录

### 6.1 JS 文件清单

| 文件名 | 大小(B) | 接口数 |
|--------|---------|--------|
| `main.e63907e3.js` | 1831502 | 666 |
| `sdk-glue.js` | 100290 | 0 |
| `runtime.js` | 3143 | 0 |
| `.js` | 57898 | 1 |
| `secsdk-lastest.umd.js` | 190562 | 0 |
| `polyfill.min.js` | 1679 | 0 |
| `builder-runtime.37a35524.js` | 14977 | 0 |
| `lib-arco.6aa248e7.js` | 1120027 | 0 |
| `lib-react.1b920edd.js` | 212986 | 0 |
| `debugger.3b8accef.js` | 39263 | 1 |
| `lib-axios.67db564b.js` | 23835 | 0 |
| `lib-router.ca08f7a9.js` | 67716 | 0 |
| `9558.6e1b4aa7.js` | 2005951 | 43 |

---

*文档由 web-reverse-engineer 技能自动生成，接口有变化请重新分析更新。*