"""离线批量复核 CLI 入口。

观测组每晚可在无 Web/Redis 的环境下逐方案复核：
    python -m scripts.batch_review_cli --studies study-a,study-b --name "夜间批次"
    python -m scripts.batch_review_cli --all                       # 复核全部方案
    python -m scripts.batch_review_cli --batch batch-xxxx --resume # 中断后续跑，不重复已完成项

逐项保留补值、独立遮挡误差与失败原因；坏方案不拖垮其他方案；
数据或参数变更时按输入指纹拒绝沿用旧结果。汇总按有效遮挡点加权，
原始缺失不进入分母，边缘不可估单列。完全沿用单次复核 analyze 口径。
"""
import argparse
import json
import os
import sys

# 强制离线模式：即使配置了 Redis 也直接在本进程执行，不依赖队列
os.environ.setdefault("TASK_MODE", "inline")

from src.services import batch_review as service
from src.utils import repository as repo
from src.utils.repository import init_db


def main(argv=None):
    parser = argparse.ArgumentParser(description="芦浦测站连续遮挡方案离线批量复核")
    parser.add_argument("--studies", help="逗号分隔的研究方案ID")
    parser.add_argument("--all", action="store_true", help="选择全部研究方案")
    parser.add_argument("--name", default="离线批量复核", help="批次名称")
    parser.add_argument("--batch", help="已有批次ID，配合 --resume 续跑")
    parser.add_argument("--resume", action="store_true", help="续跑指定批次，跳过已完成且未变更的项")
    args = parser.parse_args(argv)

    init_db()
    if args.resume:
        if not args.batch:
            parser.error("--resume 需要同时提供 --batch 批次ID")
        batch = service.execute(args.batch)
    else:
        if args.all:
            study_ids = [s["id"] for s in repo.all_rows("studies")]
        elif args.studies:
            study_ids = [x.strip() for x in args.studies.split(",") if x.strip()]
        else:
            parser.error("请用 --studies id1,id2 或 --all 指定方案")
        payload = type("Input", (), {"name": args.name, "study_ids": study_ids})()
        batch = service.create(payload, user={"email": "offline-cli", "role": "admin"})

    summary = batch.get("summary", {})
    report = {
        "batch_id": batch["id"],
        "name": batch["name"],
        "status": batch["status"],
        "item_total": summary.get("item_total", len(batch["items"])),
        "completed": summary.get("completed_count"),
        "failed": summary.get("failed_count"),
        "rts_weighted_mae": summary.get("rts_weighted_mae"),
        "rts_weight_denominator": summary.get("rts_weight_denominator"),
        "pchip_weighted_mae": summary.get("pchip_weighted_mae"),
        "pchip_weight_denominator": summary.get("pchip_weight_denominator"),
        "rts_observation_interval_coverage": summary.get("rts_observation_interval_coverage"),
        "edge_unestimable_count": summary.get("edge_unestimable_count"),
        "items": [{"study_id": i["study_id"], "status": i["status"],
                   "fingerprint": i["fingerprint"], "error": i["error"]}
                  for i in batch["items"]],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # 有失败项时返回非零，便于夜间脚本发现；成功项结果已落库不回滚
    return 1 if batch["status"] in ("failed", "partial") else 0


if __name__ == "__main__":
    sys.exit(main())
