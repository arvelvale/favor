"""极简 BM25 实现，纯标准库，无第三方依赖。

BM25 打分考虑三件事：词在片段里出现几次(tf)、片段有多长(长度归一)、
这个词在所有片段里有多罕见(idf)。分数越高表示字面越相关。
"""
import math
from collections import Counter


class BM25Index:
    def __init__(self, docs_tokens, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.docs = [Counter(tokens) for tokens in docs_tokens]
        self.lens = [sum(counter.values()) for counter in self.docs]
        self.n = len(self.docs)
        self.avgdl = (sum(self.lens) / self.n) if self.n else 0.0

        df = Counter()
        for counter in self.docs:
            df.update(counter.keys())

        self.idf = {}
        for term, freq in df.items():
            self.idf[term] = math.log(1.0 + (self.n - freq + 0.5) / (freq + 0.5))

    def scores(self, query_tokens):
        """返回与建库片段等长的分数列表。"""
        result = [0.0] * self.n
        if not self.n or not query_tokens:
            return result

        for term in set(query_tokens):
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i, counter in enumerate(self.docs):
                tf = counter.get(term, 0)
                if not tf:
                    continue
                if self.avgdl:
                    norm = 1.0 - self.b + self.b * self.lens[i] / self.avgdl
                else:
                    norm = 1.0
                denom = tf + self.k1 * norm
                result[i] += idf * tf * (self.k1 + 1.0) / denom
        return result
