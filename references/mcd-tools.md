# 麦当劳 MCP 工具速查

## 文档状态说明

本文档记录的是**已在真实环境实测**的工具契约（2026-10-24，真实 Token + 真实账号）。

- **已实测**：标 ✅ 的部分，字段名、必填项、返回结构、金额单位均已用真实调用验证。
- **未实测**：标 ⚠️ 的部分，尚未验证，遇到时先最小参数试调，看报错反推。

测试环境：账号收藏 3 家门店（杭州富阳），有 4 张券，时间 2026-10-24 10:27（早餐时段）。

不要凭空构造参数。参数校验很严格，缺必填项会直接返回 `Parameter validation failed` 并附完整 schema，照报错改比猜快。

## 服务接入信息（✅ 实测）

| 项 | 值 |
|---|---|
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP |
| 鉴权头 | `Authorization: Bearer <MCP_TOKEN>` |
| Token 申请 | https://open.mcd.cn/mcp （手机号登录 → 控制台 → 激活） |
| 限流 | 每 Token 600 次/分钟，超限返回 `429` |
| 服务范围 | 中国大陆地区（不含港澳台） |

错误码：

| code | 含义 | 处理 |
|---|---|---|
| 401 | Token 无效或已过期（实测文案：`当前鉴权码不存在或已失效!`） | 检查 `Authorization` 头与 Token；引导用户重新申请 |
| 403 | **完全没带** `Authorization` 头（实测 `{"code":"0001","msg":"系统错误"}`） | 补上请求头；配置里占位符 `${MCD_MCP_TOKEN}` 未替换时会命中此项 |
| 429 | 触发限流 | 降低频率，串行化调用，等待后重试 |
| 600012 | 促销规则不支持该商品（券与商品不匹配） | 换券或换商品，不要重试同一组合 |
| 600050 | 门店收藏为空的业务提示（非 HTTP 错误） | 改用 `searchType=2` 地址搜索，勿当作"附近无门店" |

注意：麦当劳 MCP 的业务错误走 `{"success":false,"code":<6位>,"message":"..."}` 的形式，HTTP 状态码可能是 200。**必须检查响应体里的 `success` 字段**，只看 HTTP 状态会漏掉业务失败。

排障时用 `403` / `401` 的差异快速区分"没传 Token"与"Token 不对"，比逐个翻配置快。

## 一、时间与账号（✅ 全部实测）

### `now-time-info`

无入参。返回 `data.{datetime, date, dayOfWeek, formatted, timestamp, timezone, offset, utc}`。

实测返回 `{"date":"2026-10-24","dayOfWeek":"SATURDAY","formatted":"2026-10-24 10:27:17","timezone":"GMT+08:00"}`。

用途：判断早餐/正餐档、券有效期、可预约日期。**每轮任务开始必调**。

### `query-my-account`

无入参。返回 `data.{availablePoint, accumulativePoint, usedPoint, expiredPoint, frozenPoint, currentMouthExpirePoint, nextMouthExpirePoint, accountId, currency}`。

**所有积分字段都是字符串类型**（如 `"123.4"`），不是数字，参与计算前需转换。这一点容易踩：直接做算术会抛类型错误，或得到字符串拼接的结果。

### `query-my-coupons`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `page` | string | 否 | 默认第 1 页，最多 5 页 |
| `pageSize` | string | 否 | 默认 200，最大 200 |

注意：**入参是字符串类型**（`"1"` 而非 `1`）。

返回的是**已渲染的 Markdown 文本**，不是纯 JSON 数组，字段为券名、用券价格、有效期、标签（到店专用/外送专用）。实测账户有 4 张券。

**这个接口不返回 `couponId` 和 `couponCode`**，要拿到可用于算价的券 ID，必须走 `query-store-coupons`。

## 二、门店与选址（✅ 实测）

### `query-nearby-stores`（到店场景）

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `beType` | integer | **是** | `1` 到店自取，`5` 得来速 |
| `searchType` | integer | **是** | `1` 搜收藏门店，`2` 按位置搜索 |
| `city` | string | searchType=2 时必填 | 城市名，如 `"杭州"` |
| `keyword` | string | searchType=2 时必填 | 位置关键词，如 `"富阳"` |

返回 `data[]`：

| 字段 | 说明 |
|---|---|
| `storeCode` | 门店编码，后续所有工具的主键 |
| `storeName` | 门店全名 |
| `address` | 地址 |
| `distance` | **单位是米**。搜索场景实测 6189 = 6.19 km |
| `beCode` | **beType=1 时不返回此字段**；beType=5 时必传后续工具 |
| `reservation` | 是否支持预约 |
| `reservationTimeOptions[]` | `{date, today, reservationOptionText}`，today=true 表示当天 |
| `businessStatus` | 营业中标志，**仅 searchType=2 返回** |
| `businessStartTime` / `businessEndTime` | 营业时段，**仅 searchType=2 返回** |

**重要实测差异**：
- `searchType=1`（收藏）返回的 `distance` **恒为 0**，且没有 `businessStatus`、营业时间字段。不能拿它判断远近。
- `searchType=2`（搜索）才有真实距离和营业状态，是判断"最近"的正确入口。
- 收藏为空时走 `searchType=1` 会触发 `600050`。

### `delivery-query-addresses`（外送第一步）

无入参。返回 `data.addresses[].{addressId, contactName, phone, fullAddress}`。

手机号由接口自行脱敏（形如 `用户号段****尾号`），可直接展示，但仍属个人信息，不写入任何文件。

### `delivery-query-stores`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `addressId` | string | **是** | 来自 `delivery-query-addresses` |
| `beType` | integer | **是** | `2` 麦乐送，`6` 企业团餐 |

**漏传 `beType` 会直接校验失败**，实测报 `root: must have required property 'beType'`。

返回 `data[].{storeCode, beCode, storeName, reservation, reservationTimeOptions, businessStatus, businessStartTime, businessEndTime}`。

**关键**：外送场景的 `beCode` 有值，格式为 `storeCode + "02"`。实测：

| storeCode | 外送 beCode |
|---|---|
| 3330450 | 333045002 |
| 3330197 | 333019702 |
| 3330306 | 333030602 |

但**到店自取（beType=1）的同一家店没有 beCode**。所以"切换就餐方式必须重新取 beCode"不是理论提醒，是实测确认的硬规则。不要用拼接规则自己造 beCode，从返回里读。

## 三、菜单与餐品（✅ 实测）

### `query-meals`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `storeCode` | string | **是** | 门店编码，不能为空 |
| `orderType` | integer | **是** | `1` 到店（含自取+得来速），`2` 外送（含麦乐送+团餐） |
| `beType` | integer | **是** | `1` 到店取餐，`2` 麦乐送到家，`5` 得来速，`6` 企业团餐 |
| `beCode` | string | 条件必填 | beType=1 **不传**；beType=5/2/6 **必传** |
| `reservationDate` | string | 否 | 预约场景必传，格式 `yyyy-MM-dd HH:mm` |

返回结构（两层，要交叉看）：

```
data.categories[]          分类列表
  └ name                   分类名（如"麦满分系列"、"饮品"）
  └ meals[]                该分类下餐品
      └ code               餐品编码
      └ tags[]             标签（"人气产品"、"早餐卡专享价"、"第二份半价"）
data.meals{code}           餐品详情映射表，key 就是上面的 code
  └ name                   餐品名
  └ currentPrice           现价（元，字符串）
  └ originalPrice          原价（划线价，元，字符串）
  └ discountType           优惠类型，null 表示不享受优惠
  └ canWithOrder           是否可随单购
  └ withOrder{cardId,cardType}  随单购卡信息
data.frequent{code}        常点餐品
```

**餐品编码只能从 `data.categories[].meals[].code` 或 `data.meals` 的 key 取**，不要从用户口语化品名猜。

**时段差异是真实的**：10:27 与 10:35 两次查询同一座城市的不同门店，菜单完全不同。10:27 查到的是早餐档（麦满分、粥王、脆香油条、厚松饼堡），10:35 查到的是正餐档（巨无霸、麦辣鸡腿堡、安格斯厚牛堡、板烧鸡腿堡）。**同一个早餐品在两份菜单里完全不存在，正餐品在早餐菜单里也不存在。**

所以"这家店卖不卖"必须以当前时刻的返回为准，且早餐/正餐是两套独立菜单。上午十点半前后问同一个商品，答案可能完全相反。

同一餐品在不同门店的编码可能相同但价格不同。实测 `507411` 麦咖啡美式：3330421 店原价 19 现价 11.9；3330197 店同样 19 / 11.9；但 `5024` 猪柳麦满分在两家店分别是 14.5 和 14。**价格必须以目标门店的返回为准。**

### `query-meal-detail`

⚠️ 未实测。用于查套餐组成与可替换项，入参应从 `query-meals` 的返回取编码。

### `list-nutrition-foods`

⚠️ 未实测。营养成分查询，非主链路。

## 四、价格与优惠（✅ 实测，最关键）

### `query-store-coupons`（门店维度）

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `storeCode` | string | **是** | 必须全数字 |
| `orderType` | integer | **是** | `1` 到店，`2` 外送 |
| `beType` | integer | **是** | 同 query-meals |
| `beCode` | string | 条件必填 | beType=1 不传，其余必传 |
| `reservationDate` | string | 否 | 预约场景 |

返回 `data[]`：

| 字段 | 说明 |
|---|---|
| `title` | 券名 |
| `couponId` | 券 ID，按此分组 |
| `couponCode` | 券码，同 ID 可能多张 |
| `tradeDateTime` | 有效期区间 |
| `products[].productCode` | 适用商品编码 |
| `products[].productName` | 适用商品名 |
| `promotionId` | 活动 ID |

**没有可用券时返回 `data: []`，不是报错，也不是 null。**

这是"券双层交集"的实证来源。实测三家门店：

| 门店 | 门店券 |
|---|---|
| 3330421 高科商业中心 | `[]` 空 |
| 3330306 万达广场 | `[]` 空 |
| 3330197 迎宾广场 | 1 张：9.9元中杯冰美式 / `264B97DBE02BE6CF996AA6914151C4A9` / 适用 `507411` |

而账户里实际有 4 张券。**只看 `query-my-coupons` 会得出"我有 4 张券可用"的错误结论，实际这三家店里只有 1 张能用。** 这就是为什么必须取交集。

### `calculate-price`（唯一可信的金额来源）

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `storeCode` | string | **是** | |
| `orderType` | integer | **是** | |
| `beType` | integer | **是** | |
| `beCode` | string | 条件必填 | beType=1 不传，其余必传 |
| `items[]` | array | 否 | 商品行列表 |
| `items[].productCode` | string | **是** | 来自 query-meals |
| `items[].quantity` | integer | **是** | ≥ 1 |
| `items[].couponId` | string | 否 | 用券时传 |
| `items[].couponCode` | string | 否 | 用券时传 |
| `items[].modification` | object | 否 | 特制选项，`values[]{code,key,quantity}` |
| `items[].roundList` | array | 否 | 套餐子项 |
| `reservationDate` | string | 否 | 预约场景 |
| `needTableware` | boolean | 否 | 餐具 |
| `withOrder` | object | 否 | 随单购 |

**返回金额单位全部是「分」，展示时除以 100。** 这是最容易出错的地方。

| 字段 | 含义 |
|---|---|
| `productOriginalPrice` | 商品原价（分） |
| `productPrice` | 商品现价（分，已含促销折扣） |
| `deliveryOriginalPrice` / `deliveryPrice` | 配送费原价/现价（分） |
| `packingOriginalPrice` / `packingPrice` | 打包费（分） |
| `tablewarePrice` | 餐具费（分） |
| `originalPrice` | 含所有费用的原价（分） |
| `discount` | 优惠金额（分） |
| `price` | **应付金额（分）** |
| `productList[]` | `{productCode, productName, quantity, originalSubtotal, subtotal}` |
| `takeWayList[]` | `{code, title, subtitle}` 取餐方式，到店下单需携带 |
| `enjoyed` / `enjoyable` | 已享受/可享受的优惠详情 |

**实测三组对比，说明为什么金额只能认这个接口：**

1. **到店无券**：`507411` × 1 → `price: 1190` = ¥11.90（原价 1900，促销已减 710）
2. **到店带券**（同门店同商品 + 9.9 元券）→ `productPrice: 990`、`price: 990` = ¥9.90。券确实生效，比促销价再省 ¥2.00。且 `discount` 从 710 变为 910。
3. **外送无券**（同门店同商品）→ `productPrice: 1190`、`deliveryPrice: 600`、`originalPrice: 2500`、`price: 1790` = ¥17.90

第 3 组是关键：**同样的商品，外送比到店贵 ¥6.00，全部来自配送费**。`price` 已经把配送费算进去了，而 `productPrice` 没有。若只看 `productPrice` 报"¥11.90"，用户到支付页会看到 ¥17.90。

`takeWayList` 实测返回三项：`eat-in`（堂食）、`take-in-store`（店内自提）、`take-dt-quick`（得来速）。到店下单时需携带 `code`。

### `available-coupons` / `auto-bind-coupons`

⚠️ 未实测。后者是写操作，必须用户明确同意后才调。

## 五、订单（⚠️ 未实测）

`create-order`（写操作）、`query-order`、`order-list`、`cancel-order`（写操作）四个工具本次未实测，因为测试不应产生真实订单。

已知规则（来自官方工具描述，未实测）：`create-order` 返回订单号与支付链接；不幂等，超时后先 `order-list` 核实再重试。

首次真实下单时需核对：必填项集合、`takeWayList[].code` 是否传入、返回的支付链接字段名。

## 六、商城、积分与活动（⚠️ 非主链路）

`mall-points-products`、`mall-product-detail`、`mall-create-order`、`mall-order-list`、`mall-order-detail`、`query-lottery-info`、`draw-lottery`、`query-my-prizes`、`campaign-calendar`、`query-partystore-date`、`query-partystore-session`、`party-order-create`。

均未实测。仅在用户明确要求积分兑换、抽奖、活动日历时使用，写操作同样先确认后执行。

## 参数取值原则（实测确认的硬规则）

1. **`beCode` 必须从返回里读，不能自己拼。** 虽实测发现外送 `beCode = storeCode + "02"`，但这是巧合还是规则未确认。到店自取没有 `beCode`。切换就餐方式必须重新取。
2. **`orderType` 与 `beType` 是两个不同维度，都要传。** `orderType=1` 涵盖到店自取+得来速，`orderType=2` 涵盖麦乐送+团餐；`beType` 才是具体方式。只传一个会校验失败。
3. **`searchType` 决定返回质量。** `1` 收藏（无距离、无营业状态、可能 600050），`2` 搜索（有真实距离、有营业状态）。判断"最近"用 `2`。
4. **餐品编码只从 `query-meals` 取。**
5. **券 ID 只从 `query-store-coupons` 取**，`query-my-coupons` 不给 ID。
6. **金额一律以 `calculate-price` 的 `price` 为准，且要除以 100。** `productPrice` 不含配送费。
7. **字符串类型参数不要传数字。** `query-my-coupons` 的 `page`/`pageSize`、积分字段都是字符串。

## 调用纪律

- **并发**：`now-time-info` 与 `query-my-account` 可并发。门店逐家校验必须串行，因为要"命中即停"。
- **命中即停有效**：实测第一家店（3330421）菜单里没有目标餐品，第二家（3330197）有 —— 这正是逐店校验的意义。若按距离取最近就下单，会失败。
- **缓存**：同一轮对话里门店菜单与券列表可复用，避免 429。用户改口径（换店、换时段、领新券）后必须重查。
- **幂等**：`create-order` 不幂等。超时后先 `order-list` 查，确认无单再重试。
- **失败上报**：把原始 code 与 message 一并告诉用户，给可行动作，不要只说"出错了"。

## 运行时核对清单

> **✅ 已完成（2026-10-24，真实 Token 实测）**
> - [x] 端点存活、鉴权行为（403 / 401 差异）
> - [x] 工具名真实性：文档引用的 33 个工具全部存在于官方 v1.0.9 清单
> - [x] `query-nearby-stores` 入参：`beType` + `searchType` 必填，`city`/`keyword` 仅 searchType=2 必填
> - [x] `distance` 单位是**米**；收藏场景恒为 0
> - [x] `query-meals` 需显式传 `storeCode` + `orderType` + `beType`；餐品编码在 `categories[].meals[].code` 与 `meals{code}` 的 key
> - [x] 早餐/正餐菜单确实是两套（10:27 只有早餐品）
> - [x] `query-store-coupons` 与 `query-my-coupons` 的差异：前者给 `couponId`/`couponCode`，后者不给
> - [x] 无可用券时 `query-store-coupons` 返回 `data: []`，非报错
> - [x] 券双层交集的实际效果：账户 4 张 → 三店交集仅 1 张
> - [x] `calculate-price` 金额单位是**分**；`price` 含配送费，`productPrice` 不含
> - [x] 外送 `beCode` 有值，到店自取无 `beCode`
> - [x] 配送费实测 ¥6.00（600 分），计入 `price`

> **⬜ 待验证**
> - [ ] `create-order` 必填项、`takeWayList[].code` 是否需传入、支付链接字段名
> - [ ] `beType=5`（得来速）的 `beCode` 与到店、外送的区别
> - [ ] `600050` 的实际触发文案（本次账号有收藏，未触发）
> - [ ] `query-meal-detail` 的套餐组成结构与换品字段
> - [ ] 预约场景 `reservationDate` 的校验边界
> - [x] 早餐/正餐的切换时间：10:27 为早餐档、10:35 已切正餐档，切换发生在 10:30 前后

> **2026-10-24 补充实测（第二轮，含端到端决策链路）**
> - [x] 券与商品不匹配 → `600012 促销规则不支持该商品`（失败，非静默）
> - [x] 业务错误走 `success:false` + 6 位 code，HTTP 状态可能仍是 200
> - [x] 端到端决策冲突实例：最近店（1.1km）有巨无霸但无券；次近店（2.0km）有 9.9 元咖啡券但只适用咖啡
> - [x] `takeWayList` 在到店场景返回 2–3 项，随门店支持情况变化（两家店一个有得来速一个没有）
