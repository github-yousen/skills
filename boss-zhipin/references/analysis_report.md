# www.zhipin.com 操作手册

> 首次分析时间：2026-07-23
> 目标网站：https://www.zhipin.com
> 文档用途：**下次直接看本文档操作，无需重新分析**

---

## 一、基本信息

| 项目 | 内容 |
|------|------|
| 目标 URL | https://www.zhipin.com |
| 前端框架 | 未识别（非主流SSR框架） |
| 主 JS 文件 | `main.js` (791KB) + `index.js` (538KB) |
| 接口总数 | 88 个 API 端点 |
| Source Map | 无 |
| 鉴权体系 | GatewayToken + Session + CSRF 三层 |

### JS 文件清单

| 文件名 | 大小 | 接口数 | 说明 |
|--------|------|--------|------|
| `main.js` | 791KB | 138 | 主业务逻辑（搜索/聊天/投递） |
| `index.js` | 538KB | 0 | polyfill/安全脚本 |
| `patas.2.3.0.min.js` | 115KB | 4 | APM 监控 |
| `warlockdata.min.2.2.15.js` | 70KB | 1 | 数据采集 |
| `browser-check-v2.js` | 1KB | 0 | 浏览器检测 |
| `jquery-1.12.2.min.js` | 97KB | 0 | jQuery 1.12 |

### 域名体系

| 域名 | 用途 |
|------|------|
| `www.zhipin.com` | 主站 + API 网关 |
| `img.bosszhipin.com` | 图片 CDN |
| `static.zhipin.com` | 静态资源 CDN（JS/CSS） |
| `api.map.baidu.com` | 百度地图 API（定位/区域） |

---

## 二、凭证说明

### 鉴权流程图

```
浏览器登录 → 获取 Cookie
  ├── __zp_stoken__  (网关 Token)
  ├── __zp_sseed__   (网关种子)
  ├── __zp_sname__   (网关脚本名)
  ├── __zp_sts__     (网关时间戳)
  └── bst            (Boss Session Token)

请求时自动携带:
  ├── Cookie: 上述所有
  ├── Header: token = _PAGE.token.split("|")[0]
  └── Header: traceId (链路追踪)
```

### Token 白名单机制

以下路径不走 `bst` Cookie 校验（源码发现）：
- `/wapi/zppassport/set/zpToken`
- `/wapi/zppassport/get/zpToken`
- `/wapi/zppassport/user/unbind`
- `/wapi/zppassport/user/changeMobile`
- `/wapi/zppassport/user/changePassword`
- `/safe-validate` 后缀的接口

---

## 三、API 接口清单（按模块）

### 职位搜索模块

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/wapi/zprelation/interaction/geekGetJob` | 搜索职位（核心） |
| GET | `/web/geek/job` | 搜索页面（SSR） |
| GET | `/web/geek/recommend` | 推荐职位 |
| GET | `/wapi/zpitem/web/item/detail/info` | 职位详情 |
| GET | `/wapi/zpitem/web/competitive/use` | 竞争分析 |
| GET | `/wapi/zprelation/geekTag/job/interest` | 兴趣标签 |
| GET | `/wapi/zpitem/web/geekBomb/interest` | 兴趣匹配 |
| GET | `/wapi/zpitem/web/geekVip/subscribe` | VIP订阅 |

### 城市/地区模块

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/wapi/zpCommon/data/listForCityAreaGps` | 城市区域GPS列表 |
| GET | `/wapi/zpCommon/data/getCityShowPosition` | 按cityCode获取展示位 |
| GET | `/wapi/zpgeek/overseasjob/workenv/query` | 海外职位环境 |

### 公司/品牌模块

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/wapi/zpgeek/brand/suggest` | 品牌搜索建议 |
| POST | `/wapi/zpCompany/leaderboard/getLabels` | 公司榜单标签 |
| GET | `/wapi/zpboss/h5/liveRecruit/audience/queryLivingGif` | 直播招聘 |

### 简历模块

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/web/geek/resume` | 简历主页 |
| GET | `/geek/resume/preview` | 简历预览 |
| GET | `/web/geek/resumeAnalyze` | 简历分析 |
| GET | `/web/geek/resumeSync` | 简历同步 |
| GET | `/wapi/zprelation/resume/geekDeliverList` | 投递列表 |
| POST | `/wapi/zpupload/uploadSingle` | 单文件上传 |
| POST | `/wapi/zpupload/resume/uploadFile.json` | 简历文件上传 |
| POST | `/wapi/zpgeek/resume/attachment/parser/upload.json` | 简历解析上传 |

### 聊天/沟通模块

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/web/geek/chat` | 聊天页面 |
| GET | `/wapi/zpchat/geek/getBossData` | 获取Boss信息 |
| GET | `/wapi/zpchat/config/get` | 聊天配置 |
| GET | `/wapi/zpchat/notify/setting/get` | 通知设置 |
| GET | `/wapi/zpchat/notify/setting/update` | 更新通知 |
| GET | `/wapi/zpchat/greeting/custom/save` | 保存问候语 |
| GET | `/wapi/zpchat/greeting/getTipTemplate` | 问候语模板 |
| GET | `/wapi/zpchat/greeting/updateGreeting` | 更新问候语 |
| GET | `/wapi/zpchat/wechat/getScanMixInfo` | 微信扫码信息 |

### 面试模块

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/wapi/zpinterview/geek/interview/sendResume` | 发送简历给面试 |

### 登录/认证模块

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/wapi/zppassport/captcha/randkey` | 验证码随机key |
| GET | `/wapi/zppassport/send/smsCodeV3` | 发送短信验证码 |
| GET | `/wapi/zppassport/login/phoneV3` | 手机验证码登录 |
| GET | `/wapi/zppassport/login/accountV3` | 账号密码登录 |
| GET | `/wapi/zppassport/qrcode/getMpCode` | 获取小程序码 |
| GET | `/wapi/zppassport/qrcode/dispatcher` | 二维码分发 |
| GET | `/wapi/zppassport/qrcode/loginConfirm` | 扫码确认登录 |
| GET | `/wapi/zppassport/wxmp/isLogin` | 微信是否已登录 |
| GET | `/web/zppassport/logout` | 退出登录 |
| GET | `/wapi/zppassport/set/zpToken` | Token 白名单 |
| GET | `/wapi/zppassport/get/zpToken` | Token 白名单 |

### 用户设置模块

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/wapi/zppassport/user/unbind` | 解绑账号 |
| GET | `/wapi/zppassport/user/changeMobile` | 修改手机号 |
| GET | `/wapi/zppassport/user/changePassword` | 修改密码 |
| GET | `/wapi/zpuser/wap/getSecurityGuideV1` | 安全引导 |
| GET | `/wapi/zpuser/wap/weChat/exist` | 微信绑定检查 |
| GET | `/wapi/zpuser/wap/weChat/update` | 更新微信绑定 |

### 付费/订单模块

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/wapi/zpp/user/rechargeBean` | 充值 |
| GET | `/wapi/zpp/user/bzbOrderInfo` | 订单信息 |
| GET | `/wapi/zpp/user/bzbDiscountList` | 折扣列表 |
| GET | `/wapi/zpp/user/payOrderSync` | 支付同步 |
| GET | `/wapi/zpp/user/bzbOrder` | 创建订单 |
| GET | `/wapi/zpblock/order/preorder` | 预下单 |
| GET | `/wapi/zpblock/order/bzbquery` | 查询订单 |

### 通用数据

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/common/data/positionSkill` | 职位技能映射 |

### 上报/监控模块

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/wapi/zpgeek/collection/popup/window` | 弹窗上报 |
| GET | `/api/v1/report/web` | Web上报 |
| GET | `/api/rest/coverage/data/report/fe` | 覆盖率上报 |
| GET | `/dap/api/json` | 数据采集 |

### 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/web/geek/guide` | 新手指引 |
| GET | `/wapi/zprelation/userBlack/delete` | 移除黑名单 |
| GET | `/wapi/zpuser/faqFeedback/createFeedbackV2` | 反馈 |
| GET | `/wapi/zpitem/geek/vip/info` | VIP信息 |

---

## 四、可直接调用的操作

### ① 搜索职位

```
POST /wapi/zprelation/interaction/geekGetJob?tag=4&isActive=true
Content-Type: application/x-www-form-urlencoded

query=产品经理&city=101010100&page=1&pageSize=15&experience=104
```

### ② 获取城市列表

```
GET /wapi/zpCommon/data/listForCityAreaGps
```

### ③ 查看职位详情

```
GET /wapi/zpitem/web/item/detail/info?itemId=xxx
```

### ④ 获取推荐职位

```
GET /web/geek/recommend
```

### ⑤ 搜索公司品牌

```
GET /wapi/zpgeek/brand/suggest?query=腾讯
```

### ⑥ 获取投递记录

```
GET /wapi/zprelation/resume/geekDeliverList
```

---

## 五、关键数据结构

### 搜索响应（geekGetJob）

```json
{
  "code": 0,
  "message": "success",
  "zpData": {
    "jobList": [
      {
        "jobName": "产品经理",
        "salaryDesc": "15K-25K",
        "brandName": "XX公司",
        "cityName": "北京",
        "areaDistrict": "海淀区",
        "bossName": "张先生",
        "bossTitle": "CEO",
        "skills": ["产品设计", "用户研究"],
        "publishTime": "刚刚活跃",
        "labels": ["急聘", "名企"]
      }
    ],
    "totalCount": 1200
  }
}
```

### 城市列表响应

```json
{
  "code": 0,
  "zpData": {
    "cityList": [
      {"code": "101010100", "name": "北京", "letter": "B"}
    ],
    "hotCityList": [
      {"code": "101010100", "name": "北京"}
    ]
  }
}
```

---

## 六、PM 需求设计要点

（详见 `boss_pm_prd.py` 运行的完整 PRD 输出）

| 优先级 | 功能 | 已有API | 状态 |
|--------|------|---------|------|
| P0 | 城市/区域筛选 | ✅ | 已验证 |
| P0 | 发布时间筛选 | 🔴 | 需后端确认 |
| P0 | 薪资/经验/学历筛选 | ✅ | JS参数已有 |
| P0 | 关键词搜索 | ✅ | 需登录态 |
| P1 | 搜索联想补全 | 🔴 | 需新建接口 |
| P1 | 公司/行业筛选 | ✅ | 已可用 |
| P2 | 排序/增强信息 | ✅ | 已可用 |

---

*文档由 web-reverse-engineer 技能自动生成，接口有变化请重新分析更新。*
