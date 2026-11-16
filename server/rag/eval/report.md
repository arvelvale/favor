# RAG A 档检索评测成绩表

评测方式：纯本地 BM25 检索，不调用大模型；`Recall@k` 按题级命中统计。

| 指标 | 数值 | 判定 |
|---|---|---|
| 总题数 | 35 | 有依据题 32，无依据对照 3 |
| 检索深度 top-k | 4 | 与 RAG_TOP_K 一致 |
| Recall@4 | 100% | ≥80% 算可用；60~80% 需查切块/语料；<60% 别调生成 |
| 无依据拒答率 | 100% | 对照题应检索为空，越高越好 |
| 有依据题误空率 | 0% | 越低越好 |
| 首位命中率 P@1 | 97% | 最相关的资料排第一，越高越好 |
| 平均无关片段数 | 1.12 条/题 | top-k 中非期望来源，越低越好 |
| 平均检索耗时 | 2.24 ms | 仅检索环节 |
| 最慢检索耗时 | 61.61 ms | 仅检索环节 |

## 逐题明细

| 编号 | 问题 | 期望来源 | 实际命中 | 首位 | 判定 |
|---|---|---|---|---|---|
| Q01 | 每天应该吃多少蔬菜 | cdg2022-03-vegetables-fruits或cdg2022-10-vegetables-fruits-detail或cdg2022-09-pagoda-layers | cdg2022-03-vegetables-fruits、cdg2022-10-vegetables-fruits-detail、cdg2022-10-vegetables-fruits-detail、cdg2022-09-pagoda-layers | ✓ | 通过 |
| Q02 | 成年人每天食盐不超过多少 | cdg2022-05-salt-oil-sugar或hc2019-02-salt-reduction或hc2019-01-three-reductions | cdg2022-05-salt-oil-sugar、nhc2024-05-obesity、hc2019-01-three-reductions | ✓ | 通过 |
| Q03 | 每天烹调油摄入量建议 | cdg2022-05-salt-oil-sugar或cdg2022-09-pagoda-layers或hc2019-01-three-reductions | cnsoc2025-01-milk-by-age、cnsoc2025-01-milk-by-age、cdg2022-05-salt-oil-sugar、nhc2024-03-dyslipidemia | ✗ | 通过 |
| Q04 | 添加糖每天最好控制在多少以下 | hc2019-03-sugar-children或cdg2022-05-salt-oil-sugar或hc2019-01-three-reductions | cdg2022-05-salt-oil-sugar、hc2019-03-sugar-children、nhc2024-05-obesity | ✓ | 通过 |
| Q05 | 每周中等强度身体活动要多少分钟 | cdg2022-02-energy-balance | cdg2022-02-energy-balance、cdg2022-14-older-pagoda | ✓ | 通过 |
| Q06 | 平衡膳食宝塔每天谷类吃多少 | cdg2022-11-pagoda-by-energy或cdg2022-09-pagoda-layers | cdg2022-11-pagoda-by-energy、cdg2022-14-older-pagoda、cdg2022-11-pagoda-by-energy、cdg2022-09-pagoda-layers | ✓ | 通过 |
| Q07 | 每天应该喝多少水 | cdg2022-06-meals-water | cdg2022-06-meals-water、cdg2022-01-food-variety、cdg2022-05-salt-oil-sugar、cdg2022-03-vegetables-fruits | ✓ | 通过 |
| Q08 | 奶类每天摄入量推荐 | cdg2022-03-vegetables-fruits或cdg2022-09-pagoda-layers或cnsoc2025-01-milk-by-age | cdg2022-03-vegetables-fruits、cdg2022-09-pagoda-layers、cdg2022-09-pagoda-layers、cdg2022-10-vegetables-fruits-detail | ✓ | 通过 |
| Q09 | 儿童每天需要多少钙 | cnsoc2025-02-calcium-vitamin-d | cnsoc2025-02-calcium-vitamin-d、cnsoc2025-02-calcium-vitamin-d、cnsoc2025-01-milk-by-age | ✓ | 通过 |
| Q10 | 低钠盐哪些人要慎用 | hc2019-02-salt-reduction | hc2019-02-salt-reduction、hc2019-02-salt-reduction | ✓ | 通过 |
| Q11 | 牛奶和乳饮料怎么区分 | cnsoc2025-03-milk-misconceptions | cnsoc2025-03-milk-misconceptions、cnsoc2025-03-milk-misconceptions | ✓ | 通过 |
| Q12 | 每天吃几种食物比较好 | cdg2022-01-food-variety | cdg2022-01-food-variety | ✓ | 通过 |
| Q13 | 深色蔬菜要占一半吗 | cdg2022-03-vegetables-fruits或cdg2022-10-vegetables-fruits-detail | cdg2022-10-vegetables-fruits-detail、cdg2022-09-pagoda-layers、nhc2024-04-hyperuricemia、cdg2022-03-vegetables-fruits | ✓ | 通过 |
| Q14 | 食物多样合理搭配是什么意思 | cdg2022-01-food-variety | cdg2022-01-food-variety | ✓ | 通过 |
| Q15 | 吃动平衡健康体重怎么做 | cdg2022-02-energy-balance | cdg2022-02-energy-balance、nhc2024-02-hypertension、nhc2024-01-hyperglycemia、nhc2024-03-dyslipidemia | ✓ | 通过 |
| Q16 | 适量吃鱼禽蛋瘦肉每天多少 | cdg2022-04-fish-poultry-eggs或cdg2022-09-pagoda-layers | cdg2022-04-fish-poultry-eggs、cdg2022-14-older-pagoda、cdg2022-14-older-pagoda | ✓ | 通过 |
| Q17 | 规律进餐包括哪些内容 | cdg2022-06-meals-water | cdg2022-06-meals-water、nhc2024-05-obesity、nhc2024-01-hyperglycemia | ✓ | 通过 |
| Q18 | 会看营养标签要看哪些项目 | cdg2022-07-label-cooking或hc2019-05-label-targets | hc2019-05-label-targets、hc2019-05-label-targets、cdg2022-07-label-cooking、hc2019-03-sugar-children | ✓ | 通过 |
| Q19 | 公筷分餐杜绝浪费怎么做 | cdg2022-08-hygiene-waste | cdg2022-08-hygiene-waste | ✓ | 通过 |
| Q20 | 1600 千卡能量水平谷类吃多少 | cdg2022-11-pagoda-by-energy | cdg2022-11-pagoda-by-energy、cdg2022-11-pagoda-by-energy、cdg2022-09-pagoda-layers、cdg2022-09-pagoda-layers | ✓ | 通过 |
| Q21 | 各类食物提供哪些营养素 | cdg2022-12-food-nutrients | cdg2022-12-food-nutrients、cdg2022-12-food-nutrients | ✓ | 通过 |
| Q22 | 我国居民超重肥胖现状如何 | hc2019-04-nutrition-status | hc2019-04-nutrition-status、hc2019-04-nutrition-status、hc2019-01-three-reductions、hc2019-01-three-reductions | ✓ | 通过 |
| Q23 | 儿童含糖饮料摄入要注意什么 | hc2019-03-sugar-children | hc2019-03-sugar-children、hc2019-03-sugar-children、nhc2024-01-hyperglycemia、cdg2022-05-salt-oil-sugar | ✓ | 通过 |
| Q24 | 2030 年合理膳食行动目标有哪些 | hc2019-01-three-reductions或hc2019-05-label-targets | hc2019-05-label-targets、hc2019-05-label-targets、hc2019-01-three-reductions、hc2019-01-three-reductions | ✓ | 通过 |
| Q25 | 儿童维生素 D 需要多少 | cnsoc2025-02-calcium-vitamin-d | cnsoc2025-02-calcium-vitamin-d、cnsoc2025-02-calcium-vitamin-d、cnsoc2025-01-milk-by-age、hc2019-04-nutrition-status | ✓ | 通过 |
| Q26 | 糖尿病患者每天膳食纤维吃多少 | nhc2024-01-hyperglycemia | nhc2024-01-hyperglycemia、nhc2024-01-hyperglycemia、nhc2024-03-dyslipidemia、nhc2024-03-dyslipidemia | ✓ | 通过 |
| Q27 | 高血压患者每天食盐摄入量是多少 | nhc2024-02-hypertension或hc2019-02-salt-reduction | nhc2024-02-hypertension、hc2019-02-salt-reduction、nhc2024-02-hypertension、hc2019-02-salt-reduction | ✓ | 通过 |
| Q28 | 高血脂每天烹调油不超过多少 | nhc2024-03-dyslipidemia | nhc2024-03-dyslipidemia、nhc2024-03-dyslipidemia、cdg2022-05-salt-oil-sugar、nhc2024-05-obesity | ✓ | 通过 |
| Q29 | 痛风患者每天应该喝多少水 | nhc2024-04-hyperuricemia | nhc2024-04-hyperuricemia、nhc2024-04-hyperuricemia | ✓ | 通过 |
| Q30 | 减肥期间早中晚三餐供能比是多少 | nhc2024-05-obesity | nhc2024-05-obesity、nhc2024-05-obesity | ✓ | 通过 |
| Q31 | 高龄老年人膳食指南核心推荐有哪些 | cdg2022-13-older-adults | cdg2022-13-older-adults、cdg2022-13-older-adults | ✓ | 通过 |
| Q32 | 老年人每天应该喝多少水 | cdg2022-14-older-pagoda | cdg2022-14-older-pagoda、cdg2022-13-older-adults、cdg2022-14-older-pagoda、cdg2022-13-older-adults | ✓ | 通过 |
| N01 | 阿司匹林的用法用量 | 应无命中 | （空） | — | 通过 |
| N02 | 股票代码 600519 今天涨跌 | 应无命中 | （空） | — | 通过 |
| N03 | 左甲状腺素钠片一片多少毫克 | 应无命中 | （空） | — | 通过 |

## 说明

- 本表只评估「检索是否把正确资料交给模型」，不评估模型最终回答质量。
- P@1（首位命中率）衡量排序质量：正确的资料是否排在第一条；Recall@k 只要求出现在 top-k 任意位置。
- 排序用两阶段实现：先用原始 BM25 分数判定有无依据（安全底线），再在合格候选内按标题/小标题/标签命中重排。
- 端到端的「无 RAG / 有 RAG」回答对照需要 `.env` 与 API Key，不属于离线评测范围。
- 对照题（N01~N03）故意选取知识库不覆盖的用药、行情、疾病治疗问题；检索命中即为缺陷。
- 语料已覆盖糖尿病/高血压等慢病「饮食原则」，但未覆盖用药剂量与治疗方案；此类问题若命中饮食资料属检索层正常行为，由 Prompt 高风险词规则强制追加「请咨询医生」兜底。
- 绝对分数门槛 RAG_MIN_ABS_SCORE 默认值 10.0 来自本次实测分界；语料规模变化后需重跑本脚本复核。
