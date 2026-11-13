# ========================RAG 评估模块========================
"""
轻量评估:用固定数据集度量检索与回答质量,不引入额外评估框架。
    1. 检索质量:关键词召回率 + 期望来源命中率(粗召回 + rerank 精排后的 top_n)
    2. 回答质量(--with-answer):答案关键词覆盖率,作为忠实度的代理指标
    3. rerank 消融(--no-rerank):基线只用粗召回截断到 top_n,与默认对照量化 rerank 贡献
运行:python -m evals.run_eval [--with-answer] [--no-rerank]
报告:打印并保存到 evals/results/
"""

import argparse
import json
import os
from datetime import datetime

from rag.rag_service import RagSummarizeService
from utils.cofig_handler import chroma_conf
from utils.path_tool import get_abspath

DATASET_PATH = get_abspath("evals/dataset.jsonl")
RESULT_DIR = get_abspath("evals/results")


def load_dataset(path: str) -> list[dict]:
    """逐行读取 jsonl 数据集,跳过空行。"""
    cases = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def keyword_coverage(keywords: list[str], text: str) -> float:
    """关键词在文本中出现的比例,作为召回/忠实的代理指标。"""
    if not keywords:
        return 0.0
    return sum(1 for kw in keywords if kw in text) / len(keywords)


def _answer_from_docs(service: RagSummarizeService, query: str, docs: list) -> str:
    """基线模式用已检索片段直接总结,上下文拼接与 rag_summarize 保持一致。"""
    context = ""
    for counter, doc in enumerate(docs, start=1):
        context += f"【参考资料{counter}】：参考资料：{doc.page_content} | 参考元数据：{doc.metadata}\n"
    return service.chain.invoke({"input": query, "context": context})


def eval_case(
    service: RagSummarizeService, case: dict, with_answer: bool, use_rerank: bool
) -> dict:
    """单条评估:检索片段算召回与来源命中,可选再算答案覆盖率。"""
    if use_rerank:
        docs = service.retriever_docs(case["query"])
    else:  # 基线:粗召回截断到与 rerank 相同的 top_n,保证对照公平
        docs = service.retriever.invoke(case["query"])[: chroma_conf["rerank_top_n"]]
    context = "\n".join(d.page_content for d in docs)
    sources = {os.path.basename(d.metadata.get("source", "")) for d in docs}
    result = {
        "query": case["query"],
        "retrieved": len(docs),
        "retrieval_keyword_recall": keyword_coverage(case["keywords"], context),
        "source_hit": case["source"] in sources if case.get("source") else None,
    }
    if with_answer:
        if use_rerank:
            answer = service.rag_summarize(case["query"])
        else:
            answer = _answer_from_docs(service, case["query"], docs)
        result["answer_keyword_coverage"] = keyword_coverage(case["keywords"], answer)
    return result


def build_report(results: list[dict], with_answer: bool, use_rerank: bool) -> dict:
    """汇总各条结果为一个报告字典。"""
    n = len(results)
    src = [r["source_hit"] for r in results if r["source_hit"] is not None]
    report = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "cases": n,
        "with_answer": with_answer,
        "rerank": use_rerank,
        "avg_retrieval_keyword_recall": sum(
            r["retrieval_keyword_recall"] for r in results
        )
        / n,
        "source_hit_rate": sum(src) / len(src) if src else None,
        "results": results,
    }
    if with_answer:
        report["avg_answer_keyword_coverage"] = (
            sum(r["answer_keyword_coverage"] for r in results) / n
        )
    return report


def main():
    parser = argparse.ArgumentParser(description="RAG 轻量评估")
    parser.add_argument(
        "--with-answer",
        action="store_true",
        help="额外调用模型,评估答案关键词覆盖率(默认只评检索,省 API 调用)",
    )
    parser.add_argument(
        "--no-rerank",
        action="store_true",
        help="基线模式:只用粗召回截断到 top_n,不做 rerank,用于对照 rerank 贡献",
    )
    args = parser.parse_args()
    use_rerank = not args.no_rerank

    cases = load_dataset(DATASET_PATH)
    if not cases:
        print("数据集为空,无可评估用例")
        return
    service = RagSummarizeService()
    results = [eval_case(service, c, args.with_answer, use_rerank) for c in cases]
    report = build_report(results, args.with_answer, use_rerank)

    print(f"模式: {'rerank 精排' if use_rerank else 'no-rerank 基线(粗召回 top_n)'}")
    for r in results:
        line = (
            f"[召回{r['retrieval_keyword_recall']:.2f} | 来源{r['source_hit']} | "
            f"{r['retrieved']}条] {r['query']}"
        )
        if args.with_answer:
            line += f" | 答案覆盖{r['answer_keyword_coverage']:.2f}"
        print(line)
    print(f"平均检索关键词召回率: {report['avg_retrieval_keyword_recall']:.2%}")
    print(f"期望来源命中率: {report['source_hit_rate']:.2%}")
    if args.with_answer:
        print(f"平均答案关键词覆盖率: {report['avg_answer_keyword_coverage']:.2%}")

    os.makedirs(RESULT_DIR, exist_ok=True)
    out = os.path.join(RESULT_DIR, f"report_{datetime.now():%Y%m%d_%H%M%S}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"报告已保存: {out}")


if __name__ == "__main__":
    main()
