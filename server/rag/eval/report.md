# RAG A 档检索评测成绩表

评测方式：纯本地 BM25 检索，不调用大模型；`Recall@k` 按题级命中统计。

| 指标 | 数值 | 判定 |
|---|---|---|
| 总题数 | 45 | 有依据题 42，无依据对照 3 |
| 检索深度 top-k | 4 | 与 RAG_TOP_K 一致 |
| Recall@4 | 100% | ≥80% 算可用；60~80% 需查切块/语料；<60% 别调生成 |
| 无依据拒答率 | 100% | 对照题应检索为空，越高越好 |
| 有依据题误空率 | 0% | 越低越好 |
| 首位命中率 P@1 | 95% | 最相关的资料排第一，越高越好 |
| 平均无关片段数 | 1.19 条/题 | top-k 中非期望来源，越低越好 |
| 平均检索耗时 | 3.90 ms | 仅检索环节 |
| 最慢检索耗时 | 115.20 ms | 仅检索环节 |

## 逐题明细

| 编号 | 问题 | 期望来源 | 实际命中 | 首位 | 判定 |
|---|---|---|---|---|---|
| Q01 | 每天应该吃多少蔬菜 | cdg2022-03-vegetables-fruits或cdg2022-09-pagoda-layers或cdg2022-10-vegetables-fruits-detail | cdg2022-03-vegetables-fruits、cdg2022-10-vegetables-fruits-detail、cdg2022-10-vegetables-fruits-detail、cdg2022-09-pagoda-layers | ✓ | 通过 |
| Q02 | 成年人每天食盐不超过多少 | hc2019-01-three-reductions或cdg2022-05a-salt-oil-sugar-detail或hc2019-02-salt-reduction或cdg2022-05-salt-oil-sugar或tcnss2025-canteen-oil-salt | cdg2022-05-salt-oil-sugar、cdg2022-05a-salt-oil-sugar-detail、nhc2024-05-obesity、tcnss2025-canteen-oil-salt | ✓ | 通过 |
| Q03 | 每天烹调油摄入量建议 | cdg2022-05-salt-oil-sugar或cdg2022-05a-salt-oil-sugar-detail或cdg2022-09-pagoda-layers或hc2019-01-three-reductions | cnsoc2025-01-milk-by-age、cdg2022-05a-salt-oil-sugar-detail、cdg2022-05-salt-oil-sugar、cdg2022-05a-salt-oil-sugar-detail | ✗ | 通过 |
| Q04 | 添加糖每天最好控制在多少以下 | cdg2022-05-salt-oil-sugar或hc2019-03-sugar-children或cdg2022-05a-salt-oil-sugar-detail或hc2019-01-three-reductions | cdg2022-05a-salt-oil-sugar-detail、cdg2022-05-salt-oil-sugar、nhc2024-05-obesity | ✓ | 通过 |
| Q05 | 每周中等强度身体活动要多少分钟 | cdg2022-02-energy-balance | cdg2022-02-energy-balance、nhc2024-06-child-obesity、cdg2022-15-school-age、cdg2022-14-older-pagoda | ✓ | 通过 |
| Q06 | 平衡膳食宝塔每天谷类吃多少 | cdg2022-11-pagoda-by-energy或cdg2022-09-pagoda-layers | cdg2022-11-pagoda-by-energy、cdg2022-14-older-pagoda、cdg2022-11-pagoda-by-energy、cdg2022-09-pagoda-layers | ✓ | 通过 |
| Q07 | 每天应该喝多少水 | cdg2022-06-meals-water | cdg2022-06-meals-water、cdg2022-15-school-age、cdg2022-01-food-variety、cdg2022-05-salt-oil-sugar | ✓ | 通过 |
| Q08 | 奶类每天摄入量推荐 | cdg2022-03-vegetables-fruits或cnsoc2025-01-milk-by-age或cdg2022-09-pagoda-layers | cdg2022-03-vegetables-fruits、cdg2022-09-pagoda-layers、cdg2022-09-pagoda-layers、cdg2022-10-vegetables-fruits-detail | ✓ | 通过 |
| Q09 | 儿童每天需要多少钙 | cnsoc2025-02-calcium-vitamin-d | nhc2024-06-child-obesity、cnsoc2025-02-calcium-vitamin-d、cnsoc2025-02-calcium-vitamin-d、nhc2024-06-child-obesity | ✗ | 通过 |
| Q10 | 低钠盐哪些人要慎用 | cnsoc2014-cardio-nutrition或hc2019-02-salt-reduction | hc2019-02-salt-reduction、hc2019-02-salt-reduction、cnsoc2014-cardio-nutrition | ✓ | 通过 |
| Q11 | 牛奶和乳饮料怎么区分 | cnsoc2025-03-milk-misconceptions | cnsoc2025-03-milk-misconceptions、cnsoc2025-03-milk-misconceptions | ✓ | 通过 |
| Q12 | 每天吃几种食物比较好 | cdg2022-01a-food-variety-detail或cdg2022-01-food-variety | cdg2022-01-food-variety、nhc2024-08-iron-rich-foods-infants、cdg2022-01a-food-variety-detail、nhc2024-06-child-obesity | ✓ | 通过 |
| Q13 | 深色蔬菜要占一半吗 | cdg2022-03-vegetables-fruits或cdg2022-10-vegetables-fruits-detail | cdg2022-10-vegetables-fruits-detail、cdg2022-09-pagoda-layers、nhc2024-04-hyperuricemia、cdg2022-14-older-pagoda | ✓ | 通过 |
| Q14 | 食物多样合理搭配是什么意思 | cdg2022-01a-food-variety-detail或cdg2022-01-food-variety | cdg2022-01-food-variety、cdg2022-01a-food-variety-detail、cdg2022-01a-food-variety-detail、cdc2015-food-compatibility-myth | ✓ | 通过 |
| Q15 | 吃动平衡健康体重怎么做 | cdg2022-02-energy-balance | cdg2022-02-energy-balance、nhc2024-02-hypertension、nhc2024-01-hyperglycemia、nhc2024-03-dyslipidemia | ✓ | 通过 |
| Q16 | 适量吃鱼禽蛋瘦肉每天多少 | cdg2022-04-fish-poultry-eggs或cdg2016-04-fish-poultry-eggs-meat或cdg2022-09-pagoda-layers | cdg2016-04-fish-poultry-eggs-meat、cdg2022-04-fish-poultry-eggs、cdg2016-04-fish-poultry-eggs-meat、cdg2022-14-older-pagoda | ✓ | 通过 |
| Q17 | 规律进餐包括哪些内容 | cdg2022-06-meals-water | cdg2022-06-meals-water、nhc2024-05-obesity、nhc2024-01-hyperglycemia、tcnss2025-sleep-older | ✓ | 通过 |
| Q18 | 会看营养标签要看哪些项目 | hc2019-05-label-targets或cdg2022-07-label-cooking | hc2019-05-label-targets、hc2019-05-label-targets、cdg2022-07-label-cooking、tcnss2025-children-snacks | ✓ | 通过 |
| Q19 | 公筷分餐杜绝浪费怎么做 | cdg2022-08-hygiene-waste | cdg2022-08-hygiene-waste | ✓ | 通过 |
| Q20 | 1600 千卡能量水平谷类吃多少 | cdg2022-11-pagoda-by-energy | cdg2022-11-pagoda-by-energy、cdg2022-11-pagoda-by-energy、tcnss2022-energy-restriction、cdg2022-09-pagoda-layers | ✓ | 通过 |
| Q21 | 各类食物提供哪些营养素 | cdg2022-12-food-nutrients | cdg2022-12-food-nutrients、cdg2022-12-food-nutrients、cnsoc2025-nutrient-density | ✓ | 通过 |
| Q22 | 我国居民超重肥胖现状如何 | hc2019-04-nutrition-status | hc2019-04-nutrition-status、hc2019-04-nutrition-status、hc2019-01-three-reductions、hc2019-01-three-reductions | ✓ | 通过 |
| Q23 | 儿童含糖饮料摄入要注意什么 | hc2019-03-sugar-children | hc2019-03-sugar-children、hc2019-03-sugar-children、cdg2022-15-school-age、nhc2024-06-child-obesity | ✓ | 通过 |
| Q24 | 2030 年合理膳食行动目标有哪些 | hc2019-05-label-targets或hc2019-01-three-reductions | hc2019-05-label-targets、hc2019-05-label-targets、hc2019-01-three-reductions、hc2019-01-three-reductions | ✓ | 通过 |
| Q25 | 儿童维生素 D 需要多少 | cnsoc2025-02-calcium-vitamin-d | cnsoc2025-02-calcium-vitamin-d、cnsoc2024-fever-nutrition、cnsoc2024-fever-nutrition、cnsoc2025-02-calcium-vitamin-d | ✓ | 通过 |
| Q26 | 糖尿病患者每天膳食纤维吃多少 | cnsoc2014-cardio-nutrition或nhc2024-01-hyperglycemia | nhc2024-01-hyperglycemia、nhc2024-01-hyperglycemia、cnsoc2014-cardio-nutrition、nhc2024-07-ckd | ✓ | 通过 |
| Q27 | 高血压患者每天食盐摄入量是多少 | cnsoc2014-cardio-nutrition或nhc2024-02-hypertension或hc2019-02-salt-reduction | nhc2024-02-hypertension、cnsoc2014-cardio-nutrition、hc2019-02-salt-reduction、nhc2024-02-hypertension | ✓ | 通过 |
| Q28 | 高血脂每天烹调油不超过多少 | nhc2024-03-dyslipidemia或cdg2022-05a-salt-oil-sugar-detail | nhc2024-03-dyslipidemia、nhc2024-03-dyslipidemia、cdg2022-05-salt-oil-sugar、cdg2022-05a-salt-oil-sugar-detail | ✓ | 通过 |
| Q29 | 痛风患者每天应该喝多少水 | nhc2024-04-hyperuricemia | nhc2024-04-hyperuricemia、nhc2024-04-hyperuricemia、cnsoc2014-cardio-nutrition、cdg2022-05-salt-oil-sugar | ✓ | 通过 |
| Q30 | 减肥期间早中晚三餐供能比是多少 | nhc2024-05-obesity | nhc2024-05-obesity | ✓ | 通过 |
| Q31 | 高龄老年人膳食指南核心推荐有哪些 | cdg2022-13-older-adults | cdg2022-13-older-adults、cdg2022-13-older-adults、cdg2016-older-adults-detail、cdg2016-older-adults-detail | ✓ | 通过 |
| Q32 | 老年人每天应该喝多少水 | cdg2016-older-adults-detail或cdg2022-14-older-pagoda | cdg2016-older-adults-detail、cdg2016-older-adults-detail、cdg2022-14-older-pagoda、cdg2022-13-older-adults | ✓ | 通过 |
| N01 | 阿司匹林的用法用量 | 应无命中 | （空） | — | 通过 |
| N02 | 股票代码 600519 今天涨跌 | 应无命中 | （空） | — | 通过 |
| N03 | 左甲状腺素钠片一片多少毫克 | 应无命中 | （空） | — | 通过 |
| Q33 | 平衡膳食可以降低哪些慢性病风险 | cdg2022-01a-food-variety-detail | cdg2022-01a-food-variety-detail、cnsoc2014-cardio-nutrition、cnsoc2014-cardio-nutrition、cnsoc2025-nutrient-density | ✓ | 通过 |
| Q34 | 隐性盐有哪些来源 做菜怎么减少盐 | tcnss2025-canteen-oil-salt或hc2019-02-salt-reduction或cdg2022-05a-salt-oil-sugar-detail | cdg2022-05a-salt-oil-sugar-detail、cdg2022-05a-salt-oil-sugar-detail、tcnss2025-canteen-oil-salt、tcnss2025-canteen-oil-salt | ✓ | 通过 |
| Q35 | 智慧选择食品标识是什么意思 怎么看 | tcnss2025-smart-choice-label | tcnss2025-smart-choice-label、tcnss2025-smart-choice-label | ✓ | 通过 |
| Q36 | 单位食堂每天烹调油和食盐控制目标是多少 | cdg2022-05-salt-oil-sugar或tcnss2025-canteen-oil-salt | tcnss2025-canteen-oil-salt、tcnss2025-canteen-oil-salt | ✓ | 通过 |
| Q37 | 发热儿童每升高一度体温要增加多少液体摄入 | cnsoc2024-fever-nutrition | cnsoc2024-fever-nutrition | ✓ | 通过 |
| Q38 | 4岁到6岁儿童每天钙和维生素C推荐摄入量是多少 | cnsoc2024-fever-nutrition或cnsoc2025-02-calcium-vitamin-d | cnsoc2024-fever-nutrition、tcnss2022-pregnancy-minerals、cnsoc2024-fever-nutrition、tcnss2022-pregnancy-minerals | ✓ | 通过 |
| Q39 | 膳食纤维和全谷物对心血管疾病有什么好处 | cnsoc2014-cardio-nutrition或cdg2022-01a-food-variety-detail | cnsoc2014-cardio-nutrition、cnsoc2014-cardio-nutrition、cdg2022-01a-food-variety-detail | ✓ | 通过 |
| Q40 | 心血管病预防每天蔬菜水果吃多少 盐控制在多少 | cnsoc2014-cardio-nutrition或cdg2022-05-salt-oil-sugar | cnsoc2014-cardio-nutrition、cnsoc2014-cardio-nutrition、cdg2022-03-vegetables-fruits、cdg2022-09-pagoda-layers | ✓ | 通过 |
| Q41 | 食物相克是真的吗 螃蟹和柿子不能一起吃吗 | cdc2015-food-compatibility-myth | cdc2015-food-compatibility-myth、cdc2015-food-compatibility-myth | ✓ | 通过 |
| Q42 | 土豆和鸡蛋能一起吃吗 会不会中毒 | cdc2015-food-compatibility-myth | cdc2015-food-compatibility-myth、cdc2015-food-compatibility-myth | ✓ | 通过 |

## 说明

- 本表只评估「检索是否把正确资料交给模型」，不评估模型最终回答质量。
- P@1（首位命中率）衡量排序质量：正确的资料是否排在第一条；Recall@k 只要求出现在 top-k 任意位置。
- 排序用两阶段实现：先用原始 BM25 分数判定有无依据（安全底线），再在合格候选内按标题/小标题/标签命中重排。
- 端到端的「无 RAG / 有 RAG」回答对照需要 `.env` 与 API Key，不属于离线评测范围。
- 对照题（N01~N03）故意选取知识库不覆盖的用药、行情、疾病治疗问题；检索命中即为缺陷。
- 语料已覆盖糖尿病/高血压等慢病「饮食原则」，但未覆盖用药剂量与治疗方案；此类问题若命中饮食资料属检索层正常行为，由 Prompt 高风险词规则强制追加「请咨询医生」兜底。
- 绝对分数门槛 RAG_MIN_ABS_SCORE 默认值 12.0 来自本次实测分界（误命中对照题 11.50，正常题最低 13.06）；语料规模变化后需重跑本脚本复核。
