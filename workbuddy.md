开发过程摘要

```
需求理解：以麦当劳官方活动仓库 mcd-developer-innovation-challenge 的 README.md 与 activityGuidelines.md 为依据，确认参赛项目必须包含 README.md、CONTEST_DECLARATION.md（官方原文）、MCP_INTEGRATION.md、mcp-config.example.json、源代码等文件，且须真实调用麦当劳 MCP。
MCP 连通性核验：通过 WorkBuddy 中已配置的 mcd-mcp 自定义连接器（https://mcp.mcd.cn，Bearer Token 鉴权）实际调用 now-time-info、query-my-account、query-nearby-stores 三个工具，全部成功返回，确认服务可用、账号已授权（并读得真实麦享会积分数据），同时记录了 query-nearby-stores 在收藏为空时返回业务码 600050 的行为。
Skill 规范加载：调用 WorkBuddy 内置 skill-creator 技能，按其规范生成 skill 骨架（init_skill.py），并遵循渐进式披露原则组织内容。
创意构思：选定「麦麦产品最近在售点」——选择餐品 + 查询匹配优惠券 + 查找最近可以使用且有售卖餐品的麦当劳门店 + 确认后下单的点餐决策 Skill。
开发实现：
    编写 SKILL.md（五步工作流：确认餐品 → 找门店 → 按预算搭配 → 匹配优惠算价 → 确认后下单；含 beType/orderType/beCode 配对规则、预约规则、写操作先确认后执行等安全约束）。
    编写 references/mcd-tools.md 工具速查表（仅记录实际核验过的参数 schema，避免臆造）。
    按活动要求补齐 README.md、MCP_INTEGRATION.md、mcp-config.example.json（仅 ${MCD_MCP_TOKEN} 环境变量占位符）、CONTEST_DECLARATION.md（官方原文未改动）。
验证：通过 skill-creator 的 package_skill.py 完成结构与规范校验。
```

结论

本项目为"麦当劳 MCP + WorkBuddy Skill"的真实最小可运行实现：无自建后端，源代码即 SKILL.md 及其参考文档，安装进 WorkBuddy 后即可通过自然语言驱动麦当劳 MCP 完成找店、搭配、比价、下单全链路。
