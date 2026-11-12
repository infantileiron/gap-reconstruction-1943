import hashlib
import json
from src.config.settings import TASK_MODE, REDIS_URL, ARTIFACT_DIR
from src.constants.enums import BatchStatus, BatchItemStatus
from src.models.entities import BatchReview
from src.services.statistics import analyze
from src.utils import repository as repo
from src.utils.identity import new_id, now

QUEUE_NAME = "gap-reconstruction:batch-jobs"


def input_fingerprint(dataset, mask, study):
    # 数据行、掩码与参数任一变更都会改变指纹；旧结果据此被拒绝沿用
    payload = {"dataset": {"id": dataset["id"], "rows": dataset["rows"]},
               "mask": mask, "study": study}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def extract_item(result):
    # 从单次复核结果中抽取逐项留痕：补值、独立遮挡误差、边缘不可估
    production = result["production"]["series"]
    filled = [{"time_hour": p["time_hour"],
               "rts_output": p["rts_output"],
               "pchip_output": p["pchip_output"]}
              for p in production if p["is_gap"]]
    # 边缘不可估：原始缺口中 PCHIP 无法在内点范围估计的时刻（RTS 仍可估时单列说明）
    edge_gaps = [{"time_hour": p["time_hour"],
                  "reason": "位于最早/最晚已知点之外或已知点不足，PCHIP边缘不外推"}
                 for p in production if p["is_gap"] and p["pchip_output"] is None]
    targets = result["validation"]["targets"]
    validation = []
    edge_targets = []
    for p in targets:
        estimable = p["pchip"] is not None
        row = {"time_hour": p["time_hour"],
               "validation_truth": p["validation_truth"],
               "rts_prediction": p["rts_mean"],
               "pchip_prediction": p["pchip"],
               "rts_error": abs(p["rts_mean"] - p["validation_truth"]),
               "pchip_error": abs(p["pchip"] - p["validation_truth"]) if estimable else None,
               "pchip_estimable": estimable,
               "rts_covered": p["observation_low"] <= p["validation_truth"] <= p["observation_high"]}
        validation.append(row)
        if not estimable:
            edge_targets.append({"time_hour": p["time_hour"],
                                 "reason": "遮挡目标落在PCHIP已知点范围之外，边缘不可估"})
    return {
        "station": result["station"],
        "point_count": result["point_count"],
        "observed_count": result["observed_count"],
        "missing_count": result["missing_count"],
        "pchip_unfilled_gaps": result["pchip_unfilled_gaps"],
        "filled_gaps": filled,
        "edge_unestimable": edge_gaps + edge_targets,
        "validation": validation,
        "metrics": result["validation"]["metrics"],
        "checksum": result["checksum"],
    }


def _new_item(study_id, fingerprint):
    return {"study_id": study_id, "status": BatchItemStatus.PENDING.value,
            "fingerprint": fingerprint, "previous_fingerprint": "",
            "error": "", "detail": None, "started_at": "", "finished_at": ""}


def create(data, user):
    study_ids = list(dict.fromkeys(data.study_ids))  # 去重保序
    if not study_ids:
        raise ValueError("批量复核至少选择一个重建方案")
    fingerprints = []
    for sid in study_ids:
        study = repo.get("studies", sid)
        mask = repo.get("masks", study["mask_id"])
        dataset = repo.get("datasets", study["dataset_id"])
        if mask["dataset_id"] != study["dataset_id"]:
            raise ValueError(f"方案 {sid} 的掩码与研究数据集不一致，已拒绝建批")
        fingerprints.append(input_fingerprint(dataset, mask, study))
    batch = BatchReview(new_id("batch"), data.name, study_ids,
                        status=BatchStatus.QUEUED.value,
                        items=[_new_item(sid, fp) for sid, fp in zip(study_ids, fingerprints)],
                        summary={}, created_at=now(), updated_at=now())
    repo.put("batch_reviews", batch)
    if TASK_MODE == "inline":
        return execute(batch.id)
    try:
        import redis
        redis.Redis.from_url(REDIS_URL).rpush(QUEUE_NAME, batch.id)
    except Exception:
        batch.status = BatchStatus.FAILED.value
        batch.error = "队列不可用，请恢复Redis后重新提交，或使用离线CLI入口"
        batch.updated_at = now()
        repo.put("batch_reviews", batch)
        raise ValueError(batch.error)
    return batch


def _run_item(item):
    # 单项失败只记录原因，不抛出，保证坏方案不拖垮其他方案
    item["status"] = BatchItemStatus.RUNNING.value
    item["started_at"] = now()
    try:
        study = repo.get("studies", item["study_id"])
        mask = repo.get("masks", study["mask_id"])
        dataset = repo.get("datasets", study["dataset_id"])
        # 指纹在执行时按当前数据/参数重算；调用方已负责判定旧结果可否沿用
        fp = input_fingerprint(dataset, mask, study)
        # 完全沿用单次复核口径：同一 analyze 入口，遮挡序列独立重算
        result = analyze(dataset["rows"], mask, study)
        item["fingerprint"] = fp
        item["detail"] = extract_item(result)
        item["status"] = BatchItemStatus.COMPLETED.value
        item["error"] = ""
    except Exception as exc:
        item["status"] = BatchItemStatus.FAILED.value
        item["error"] = str(exc)
    finally:
        item["finished_at"] = now()


def _aggregate(batch):
    # 汇总只统计成功项；按有效遮挡点（原本有值的掩码目标）加权，原始缺失不进分母
    rts_err_sum = rts_weight = 0
    pchip_err_sum = pchip_weight = 0
    covered = target_total = 0
    edge_points = []
    stations = []
    for item in batch["items"]:
        if item["status"] != BatchItemStatus.COMPLETED.value:
            continue
        detail = item["detail"]
        stations.append(detail["station"])
        for row in detail["validation"]:
            target_total += 1  # 掩码目标在 analyze 中已保证原本有值
            rts_err_sum += row["rts_error"]
            rts_weight += 1
            covered += 1 if row["rts_covered"] else 0
            if row["pchip_estimable"]:
                pchip_err_sum += row["pchip_error"]
                pchip_weight += 1
        for edge in detail["edge_unestimable"]:
            edge_points.append({"study_id": item["study_id"],
                                "station": detail["station"],
                                **edge})
    done = [i for i in batch["items"] if i["status"] == BatchItemStatus.COMPLETED.value]
    failed = [i for i in batch["items"] if i["status"] == BatchItemStatus.FAILED.value]
    pending = [i for i in batch["items"]
               if i["status"] in (BatchItemStatus.PENDING.value, BatchItemStatus.RUNNING.value)]
    return {
        "item_total": len(batch["items"]),
        "completed_count": len(done),
        "failed_count": len(failed),
        "pending_count": len(pending),
        "stations": sorted({s for s in stations if s}),
        "rts_weighted_mae": rts_err_sum / rts_weight if rts_weight else None,
        "rts_weight_denominator": rts_weight,
        "pchip_weighted_mae": pchip_err_sum / pchip_weight if pchip_weight else None,
        "pchip_weight_denominator": pchip_weight,
        "rts_observation_interval_coverage": covered / target_total if target_total else None,
        "coverage_denominator": target_total,
        "edge_unestimable_count": len(edge_points),
        "edge_unestimable": edge_points,
        "failed_study_ids": [i["study_id"] for i in failed],
        "aggregation_rule": "按有效遮挡点（原本有值的掩码目标）等权加权；原始缺失不进入分母；PCHIP边缘不可估单列且不进入PCHIP分母",
    }


def _fingerprint_for_study(study_id):
    # 引用失效（方案/掩码/数据被删）返回 None，由执行环节记录为单项失败
    try:
        study = repo.get("studies", study_id)
        mask = repo.get("masks", study["mask_id"])
        dataset = repo.get("datasets", study["dataset_id"])
    except Exception:
        return None
    return input_fingerprint(dataset, mask, study)


def _current_fingerprints(batch):
    return {item["study_id"]: _fingerprint_for_study(item["study_id"])
            for item in batch["items"]}


def execute(id):
    batch = repo.get("batch_reviews", id)
    if batch["status"] == BatchStatus.COMPLETED.value:
        # 已完成批次：数据/参数未变才直接返回；任一变更则拒绝沿用旧结果并重算
        current = _current_fingerprints(batch)
        if all(current[i["study_id"]] == i["fingerprint"] for i in batch["items"]):
            return batch
    batch["status"] = BatchStatus.RUNNING.value
    batch["updated_at"] = now()
    repo.put("batch_reviews", batch)
    for item in batch["items"]:
        # 中断续跑：已完成且指纹未变的项直接跳过，不重复计算
        if item["status"] == BatchItemStatus.COMPLETED.value:
            current_fp = _fingerprint_for_study(item["study_id"])
            if current_fp == item["fingerprint"]:
                continue
            # 数据/参数变更或引用失效：拒绝沿用旧结果，留痕后重算
            item["previous_fingerprint"] = item["fingerprint"]
            item["status"] = BatchItemStatus.STALE.value
        _run_item(item)
        repo.put("batch_reviews", batch)  # 逐项落盘，中断后已完成项不丢
    batch["summary"] = _aggregate(batch)
    failed = batch["summary"]["failed_count"]
    done = batch["summary"]["completed_count"]
    if failed == 0:
        batch["status"] = BatchStatus.COMPLETED.value
    elif done == 0:
        batch["status"] = BatchStatus.FAILED.value
    else:
        batch["status"] = BatchStatus.PARTIAL.value
    batch["updated_at"] = now()
    repo.put("batch_reviews", batch)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / (id + ".batch.json")).write_text(
        json.dumps({"batch": batch, "summary": batch["summary"]},
                   ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return batch


def list_batches():
    return repo.all_rows("batch_reviews")


def detail(id):
    return repo.get("batch_reviews", id)
