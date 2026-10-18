"""Step 5: 新增 ~20 条查询覆盖未测试攻略"""
import json, os, sys

# Read restructured queries
with open("data/eval/rag_eval_queries_restructured.jsonl", encoding="utf-8") as f:
    queries = [json.loads(l) for l in f if l.strip()]

# Load guide titles
guide_titles = set()
for fname in os.listdir("data/seed_guides"):
    if fname.endswith(".json") and fname != "_import_report.json":
        with open(f"data/seed_guides/{fname}", encoding="utf-8") as fh:
            guide_titles.add(json.load(fh)["title"])

# New queries
new_queries = [
    # 杭州 (1)
    dict(id="RAG-HZ-021", query="杭州想看博物馆和历史文化，怎么安排一天", city="杭州",
         expected_city="杭州", intent_type="attraction", difficulty="medium",
         positive_titles=["杭州历史文化与博物馆攻略"],
         acceptable_titles=["杭州第一次来旅游攻略", "杭州两天一晚经典游攻略"],
         must_title="杭州历史文化与博物馆攻略",
         positive_sections=["attraction", "route", "tip"],
         required_keywords=["杭州", "博物馆", "历史文化"],
         negative_titles=["北京历史文化路线攻略", "西安历史文化三日游攻略"]),

    # 北京 (1)
    dict(id="RAG-BJ-017", query="北京第一次来有哪些必吃的，烤鸭涮肉炸酱面怎么选", city="北京",
         expected_city="北京", intent_type="food", difficulty="easy",
         positive_titles=["北京美食与餐饮选择攻略"],
         acceptable_titles=["北京第一次来五日游攻略", "北京旅游防坑与防骗指南"],
         must_title="北京美食与餐饮选择攻略",
         positive_sections=["food", "tip"],
         required_keywords=["北京", "美食", "烤鸭", "涮肉", "炸酱面"],
         negative_titles=["成都美食火锅避坑攻略", "西安美食与餐饮选择攻略"]),

    # 成都 (1)
    dict(id="RAG-CD-018", query="成都地铁去都江堰青城山方便吗，要多久", city="成都",
         expected_city="成都", intent_type="transport", difficulty="medium",
         positive_titles=["成都地铁公交与市内交通攻略"],
         acceptable_titles=["成都都江堰青城山一日游攻略", "成都第一次来三日游攻略"],
         must_title="成都地铁公交与市内交通攻略",
         positive_sections=["transport", "route", "tip"],
         required_keywords=["成都", "地铁", "都江堰", "青城山", "交通"],
         negative_titles=["西安地铁公交与市内交通攻略", "北京地铁出行攻略"]),

    # 西安 (4)
    dict(id="RAG-XA-012", query="西安城墙钟楼鼓楼半天怎么走，晚上好看吗", city="西安",
         expected_city="西安", intent_type="route", difficulty="medium",
         positive_titles=["西安城墙钟鼓楼经典 Citywalk 攻略"],
         acceptable_titles=["西安夜游与美食攻略", "西安历史文化三日游攻略"],
         must_title="西安城墙钟鼓楼经典 Citywalk 攻略",
         positive_sections=["route", "attraction", "tip"],
         required_keywords=["西安", "城墙", "钟楼", "鼓楼", "夜景"],
         negative_titles=["西安大雁塔大唐不夜城夜游攻略"]),
    dict(id="RAG-XA-013", query="西安地铁公交去钟楼大雁塔兵马俑方便吗", city="西安",
         expected_city="西安", intent_type="transport", difficulty="medium",
         positive_titles=["西安地铁公交与市内交通攻略"],
         acceptable_titles=["西安住宿区域选择攻略", "西安兵马俑游玩攻略"],
         must_title="西安地铁公交与市内交通攻略",
         positive_sections=["transport", "tip"],
         required_keywords=["西安", "地铁", "公交", "钟楼", "大雁塔", "兵马俑"],
         negative_titles=["北京地铁出行攻略", "厦门地铁 BRT 轮渡与市内交通攻略"]),
    dict(id="RAG-XA-014", query="华山一天能往返吗，从西安怎么去", city="西安",
         expected_city="西安", intent_type="route", difficulty="hard",
         positive_titles=["西安华山一日游攻略"],
         acceptable_titles=["西安地铁公交与市内交通攻略", "西安旅游防坑与防骗指南"],
         must_title="西安华山一日游攻略",
         positive_sections=["route", "transport", "tip"],
         required_keywords=["华山", "西安", "一日游", "往返"],
         negative_titles=["成都都江堰青城山一日游攻略"]),
    dict(id="RAG-XA-015", query="西安除了兵马俑还有哪些美食值得吃", city="西安",
         expected_city="西安", intent_type="food", difficulty="medium",
         positive_titles=["西安美食与餐饮选择攻略"],
         acceptable_titles=["西安夜游与美食攻略", "西安旅游防坑与防骗指南", "西安兵马俑游玩攻略"],
         must_title="西安美食与餐饮选择攻略",
         positive_sections=["food", "tip"],
         required_keywords=["西安", "美食", "兵马俑", "回民街"],
         negative_titles=["成都美食火锅避坑攻略"]),

    # 厦门 (9)
    dict(id="RAG-XM-012", query="厦门第一次来住哪里方便，鼓浪屿和中山路怎么选", city="厦门",
         expected_city="厦门", intent_type="hotel", difficulty="medium",
         positive_titles=["厦门住宿区域选择攻略"],
         acceptable_titles=["厦门第一次来三天两晚攻略", "厦门鼓浪屿游玩攻略", "厦门地铁 BRT 轮渡与市内交通攻略"],
         must_title="厦门住宿区域选择攻略",
         positive_sections=["hotel", "transport", "tip"],
         required_keywords=["厦门", "住宿", "鼓浪屿", "中山路"],
         negative_titles=["杭州住宿区域选择攻略", "北京住宿区域选择攻略"]),
    dict(id="RAG-XM-013", query="厦门鼓浪屿船票码头怎么选，怎么去最稳", city="厦门",
         expected_city="厦门", intent_type="transport", difficulty="medium",
         positive_titles=["厦门地铁 BRT 轮渡与市内交通攻略"],
         acceptable_titles=["厦门鼓浪屿游玩攻略", "厦门旅游防坑与防骗指南"],
         must_title="厦门地铁 BRT 轮渡与市内交通攻略",
         positive_sections=["transport", "tip"],
         required_keywords=["厦门", "鼓浪屿", "船票", "码头", "轮渡"],
         negative_titles=["杭州地铁公交出行攻略", "北京地铁出行攻略"]),
    dict(id="RAG-XM-014", query="厦门海鲜怎么吃不踩坑，中山路八市曾厝垵怎么选", city="厦门",
         expected_city="厦门", intent_type="food", difficulty="medium",
         positive_titles=["厦门美食海鲜与餐饮选择攻略"],
         acceptable_titles=["厦门旅游防坑与防骗指南", "厦门第一次来三天两晚攻略"],
         must_title="厦门美食海鲜与餐饮选择攻略",
         positive_sections=["food", "tip"],
         required_keywords=["厦门", "海鲜", "中山路", "八市", "曾厝垵"],
         negative_titles=["成都美食火锅避坑攻略", "西安美食与餐饮选择攻略"]),
    dict(id="RAG-XM-015", query="厦门第一次来三天两晚怎么玩，不想太赶", city="厦门",
         expected_city="厦门", intent_type="route", difficulty="easy",
         positive_titles=["厦门第一次来三天两晚攻略"],
         acceptable_titles=["厦门鼓浪屿游玩攻略", "厦门住宿区域选择攻略", "厦门环岛路沙滩海岸线游玩攻略"],
         must_title="厦门第一次来三天两晚攻略",
         positive_sections=["route", "transport", "hotel"],
         required_keywords=["厦门", "第一次来", "三天两晚", "鼓浪屿"],
         negative_titles=["杭州第一次来旅游攻略", "北京第一次来五日游攻略"]),
    dict(id="RAG-XM-016", query="厦门带老人怎么玩，鼓浪屿和环岛路会不会太累", city="厦门",
         expected_city="厦门", intent_type="route", difficulty="medium",
         positive_titles=["厦门老人轻松游攻略"],
         acceptable_titles=["厦门住宿区域选择攻略", "厦门鼓浪屿游玩攻略", "厦门环岛路沙滩海岸线游玩攻略"],
         must_title="厦门老人轻松游攻略",
         positive_sections=["route", "hotel", "tip"],
         required_keywords=["厦门", "老人", "鼓浪屿", "环岛路"],
         negative_titles=["杭州3天2晚老人轻松游攻略", "北京老人轻松游攻略"]),
    dict(id="RAG-XM-017", query="厦门沙坡尾和曾厝垵哪个更值得去，适合拍照吗", city="厦门",
         expected_city="厦门", intent_type="route", difficulty="medium",
         positive_titles=["厦门沙坡尾曾厝垵与文艺街区 Citywalk 攻略"],
         acceptable_titles=["厦门情侣三日游攻略", "厦门住宿区域选择攻略", "厦门旅游防坑与防骗指南"],
         must_title="厦门沙坡尾曾厝垵与文艺街区 Citywalk 攻略",
         positive_sections=["route", "tip", "hotel"],
         required_keywords=["厦门", "沙坡尾", "曾厝垵", "拍照"],
         negative_titles=["西安城墙钟鼓楼经典 Citywalk 攻略", "北京情侣周末与胡同 Citywalk 攻略"]),
    dict(id="RAG-XM-018", query="厦门环岛路黄厝白城沙滩怎么选，想看海拍照", city="厦门",
         expected_city="厦门", intent_type="attraction", difficulty="medium",
         positive_titles=["厦门环岛路沙滩海岸线游玩攻略"],
         acceptable_titles=["厦门情侣三日游攻略", "厦门亲子游攻略", "厦门住宿区域选择攻略"],
         must_title="厦门环岛路沙滩海岸线游玩攻略",
         positive_sections=["attraction", "route", "tip"],
         required_keywords=["厦门", "环岛路", "黄厝", "白城沙滩", "看海"],
         negative_titles=["厦门鼓浪屿游玩攻略", "杭州西湖一日游攻略"]),
    dict(id="RAG-XM-019", query="厦门大学南普陀植物园一天怎么安排，厦大能进去吗", city="厦门",
         expected_city="厦门", intent_type="attraction", difficulty="medium",
         positive_titles=["厦门大学南普陀与万石植物园攻略"],
         acceptable_titles=["厦门第一次来三天两晚攻略", "厦门旅游防坑与防骗指南"],
         must_title="厦门大学南普陀与万石植物园攻略",
         positive_sections=["attraction", "route", "tip"],
         required_keywords=["厦门大学", "南普陀", "植物园", "参观"],
         negative_titles=["厦门鼓浪屿游玩攻略", "杭州历史文化与博物馆攻略"]),
    dict(id="RAG-XM-020", query="厦门集美学村值得去吗，厦门北站返程顺路吗", city="厦门",
         expected_city="厦门", intent_type="route", difficulty="medium",
         positive_titles=["厦门集美学村与园博苑文化慢游攻略"],
         acceptable_titles=["厦门地铁 BRT 轮渡与市内交通攻略", "厦门第一次来三天两晚攻略"],
         must_title="厦门集美学村与园博苑文化慢游攻略",
         positive_sections=["route", "transport", "tip"],
         required_keywords=["厦门", "集美学村", "厦门北站", "园博苑"],
         negative_titles=["厦门鼓浪屿游玩攻略", "北京历史文化路线攻略"]),
]

# Verify all titles exist
missing = []
for q in new_queries:
    for t in q.get("positive_titles", []):
        if t not in guide_titles:
            missing.append(f'{q["id"]}: positive="{t}"')
    for t in q.get("acceptable_titles", []):
        if t not in guide_titles:
            missing.append(f'{q["id"]}: acceptable="{t}"')
    for t in q.get("negative_titles", []):
        if t not in guide_titles:
            missing.append(f'{q["id"]}: negative="{t}"')
    mt = q.get("must_title", "")
    if mt and mt not in guide_titles:
        missing.append(f'{q["id"]}: must_title="{mt}"')

if missing:
    print(f"[ERR] {len(missing)} 个标题缺失:")
    for m in missing:
        print(f"  {m}")
    sys.exit(1)

# Append to queries
all_queries = queries + new_queries

# Final stats
pos_counts = [len(q["positive_titles"]) for q in all_queries]
acc_counts = [len(q["acceptable_titles"]) for q in all_queries]
print(f"原始: {len(queries)} 条")
print(f"新增: {len(new_queries)} 条")
print(f"总计: {len(all_queries)} 条")
print(f"avg positive: {sum(pos_counts)/len(pos_counts):.2f}")
print(f"avg acceptable: {sum(acc_counts)/len(acc_counts):.2f}")

# Per city
from collections import Counter
city_dist = Counter(q["expected_city"] for q in all_queries)
print(f"城市分布: {dict(sorted(city_dist.items()))}")

# Write
out_path = "data/eval/rag_eval_queries.jsonl"
with open(out_path, "w", encoding="utf-8") as f:
    for q in all_queries:
        f.write(json.dumps(q, ensure_ascii=False) + "\n")
print(f"\n最终文件: {out_path}")
