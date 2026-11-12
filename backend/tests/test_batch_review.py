"""离线批量复核服务端到端验证（不依赖 fastapi/pydantic/redis，纯标准库）。

运行：cd backend && python3 -I tests/test_batch_review.py
使用独立临时 sqlite 库与独立产物目录，结束后清理。
"""
import importlib
import os
import sys
import tempfile
import types
import unittest

# ---- 最小 stub，使无 fastapi 环境下也能导入服务链 ----
_fastapi = types.ModuleType("fastapi")
class HTTPException(Exception):
    def __init__(self, status_code, detail=""):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
_fastapi.HTTPException = HTTPException
sys.modules.setdefault("fastapi", _fastapi)
sys.modules.setdefault("fastapi.security", types.ModuleType("fastapi.security"))
sys.modules["fastapi.security"].HTTPBearer = lambda *a, **k: None

_pydantic = types.ModuleType("pydantic")
class _BaseModel:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
def _Field(default=None, **kw):
    return default
class _ConfigDict(dict):
    pass
_pydantic.BaseModel = _BaseModel
_pydantic.Field = _Field
_pydantic.ConfigDict = _ConfigDict
sys.modules.setdefault("pydantic", _pydantic)

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

TMP = tempfile.mkdtemp(prefix="batch-verify-")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(TMP, "verify.sqlite")
os.environ["ARTIFACT_DIR"] = os.path.join(TMP, "artifacts")
os.environ["TASK_MODE"] = "inline"
os.environ["SEED_DEMO"] = "false"

from src.utils import repository as repo
from src.services import batch_review as br
from src.services.seed import seed
from src.services import mask as mask_service
from src.services import study as study_service
from src.constants.enums import BatchStatus, BatchItemStatus


def rows_for(station):
    ds = repo.get("datasets", "ds-stations")
    return [r for r in ds["rows"] if r["station"] == station]


def make_mask(mask_id, station, start, end):
    ds = repo.get("datasets", "ds-stations")
    selected = [r for r in ds["rows"]
                if r["station"] == station and start <= r["time_hour"] <= end]
    return repo.put("masks", {
        "id": mask_id, "name": f"{station}-{start}", "dataset_id": "ds-stations",
        "station": station, "start_hour": float(start), "end_hour": float(end),
        "target_times": [r["time_hour"] for r in selected], "created_at": "t"})


def make_study(study_id, mask_id, q=0.03, r=0.09, p0=10000.0, level=None):
    return repo.put("studies", {
        "id": study_id, "name": study_id, "dataset_id": "ds-stations",
        "mask_id": mask_id, "q_per_hour": q, "observation_r": r,
        "initial_variance": p0, "initial_level": level, "created_at": "t"})


class Input:
    def __init__(self, name, study_ids):
        self.name = name
        self.study_ids = study_ids


class BatchReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo.init_db()
        seed()
        # LP-02 / LP-03 的窗口都落在已知观测上（避开缺口 330-333 / 350-357）
        make_mask("mask-lp02", "LP-02", 100, 111)
        make_mask("mask-lp03", "LP-03", 100, 111)
        make_study("study-02", "mask-lp02")
        make_study("study-03", "mask-lp03")
        make_study("study-bad-q", "mask-lp02", q=0.0)  # 非法参数 → 该项失败

    def _create(self, ids, name="验证批次"):
        return br.create(Input(name, ids), user={"email": "test", "role": "admin"})

    def test_01_full_batch_all_completed_and_item_trace(self):
        batch = self._create(["study-local-level", "study-02", "study-03"])
        self.assertEqual(batch["status"], BatchStatus.COMPLETED.value)
        self.assertEqual(len(batch["items"]), 3)
        for item in batch["items"]:
            self.assertEqual(item["status"], BatchItemStatus.COMPLETED.value)
            self.assertEqual(len(item["fingerprint"]), 64)
            detail = item["detail"]
            # 逐项保留：补值、独立遮挡误差
            self.assertTrue(all(set(p) >= {"time_hour", "rts_output", "pchip_output"}
                                for p in detail["filled_gaps"]))
            self.assertTrue(all(set(p) >= {"time_hour", "validation_truth",
                                           "rts_error", "pchip_error", "pchip_estimable"}
                                for p in detail["validation"]))
            self.assertEqual(detail["metrics"]["target_count"], 12)
        s = batch["summary"]
        # 3 站 × 12 个有效遮挡点；原始缺失不进分母
        self.assertEqual(s["rts_weight_denominator"], 36)
        self.assertEqual(s["coverage_denominator"], 36)
        self.assertIsNotNone(s["rts_weighted_mae"])
        self.assertGreaterEqual(s["rts_weighted_mae"], 0.0)
        # 加权口径核对：手工按点重算 RTS MAE
        manual = sum(p["rts_error"] for it in batch["items"] for p in it["detail"]["validation"]) / 36
        self.assertAlmostEqual(s["rts_weighted_mae"], manual, places=12)
        self.assertTrue(os.path.exists(os.path.join(
            os.environ["ARTIFACT_DIR"], batch["id"] + ".batch.json")))

    def test_02_bad_item_does_not_break_others(self):
        batch = self._create(["study-local-level", "study-bad-q", "study-03"], "含坏方案批次")
        self.assertEqual(batch["status"], BatchStatus.PARTIAL.value)
        statuses = {i["study_id"]: i["status"] for i in batch["items"]}
        self.assertEqual(statuses["study-bad-q"], BatchItemStatus.FAILED.value)
        self.assertTrue(batch["items"][1]["error"])  # 失败原因逐项保留
        self.assertEqual(statuses["study-local-level"], BatchItemStatus.COMPLETED.value)
        self.assertEqual(statuses["study-03"], BatchItemStatus.COMPLETED.value)
        # 汇总只数有效项：2 站 × 12 点
        self.assertEqual(batch["summary"]["rts_weight_denominator"], 24)
        self.assertEqual(batch["summary"]["failed_count"], 1)
        self.assertIn("study-bad-q", batch["summary"]["failed_study_ids"])

    def test_03_all_failed(self):
        batch = self._create(["study-bad-q"], "全失败批次")
        self.assertEqual(batch["status"], BatchStatus.FAILED.value)
        self.assertIsNone(batch["summary"]["rts_weighted_mae"])
        self.assertEqual(batch["summary"]["rts_weight_denominator"], 0)
        self.assertEqual(batch["summary"]["completed_count"], 0)

    def test_04_resume_skips_completed_and_recovers(self):
        batch = self._create(["study-local-level", "study-02"], "中断批次")
        # 模拟中断：把第二项重置为 pending，第一项保留 completed
        batch["items"][1]["status"] = BatchItemStatus.PENDING.value
        batch["status"] = BatchStatus.RUNNING.value
        repo.put("batch_reviews", batch)
        fp_before = batch["items"][0]["fingerprint"]
        resumed = br.execute(batch["id"])
        self.assertEqual(resumed["status"], BatchStatus.COMPLETED.value)
        self.assertEqual(resumed["items"][0]["fingerprint"], fp_before)  # 未重算：指纹一致直接跳过
        self.assertEqual(resumed["items"][1]["status"], BatchItemStatus.COMPLETED.value)
        self.assertTrue(resumed["items"][1]["finished_at"])

    def test_05_changed_input_rejects_stale_result(self):
        batch = self._create(["study-local-level"], "变更批次")
        old_fp = batch["items"][0]["fingerprint"]
        # 数据变更：直接修改数据集行（模拟重新导入后的内容变化）
        ds = repo.get("datasets", "ds-stations")
        ds["rows"][150]["value"] = 99.999
        repo.put("datasets", ds)
        rerun = br.execute(batch["id"])
        item = rerun["items"][0]
        self.assertEqual(item["status"], BatchItemStatus.COMPLETED.value)
        self.assertNotEqual(item["fingerprint"], old_fp)
        self.assertEqual(item["previous_fingerprint"], old_fp)  # 旧指纹留痕，未沿用旧结果
        # 参数变更同样改变指纹
        study = repo.get("studies", "study-local-level")
        study["q_per_hour"] = 0.05
        repo.put("studies", study)
        fp2 = item["fingerprint"]
        rerun2 = br.execute(batch["id"])
        self.assertNotEqual(rerun2["items"][0]["fingerprint"], fp2)

    def test_06_missing_study_rejected_at_creation(self):
        with self.assertRaises(Exception):
            self._create(["study-not-exist"], "坏引用批次")

    def test_07_edge_unestimable_listed_and_excluded_from_pchip_denominator(self):
        # 构造 PCHIP 边缘不可估场景：遮挡窗口延伸到序列最后已知点(473)，
        # 训练数组里 468-473 被置空后，末端目标超出 PCHIP 可插值范围
        make_mask("mask-edge", "LP-01", 468, 473)
        make_study("study-edge", "mask-edge")
        batch = self._create(["study-edge"], "边缘批次")
        item = batch["items"][0]
        self.assertEqual(item["status"], BatchItemStatus.COMPLETED.value)
        detail = item["detail"]
        # 掩码 6 点全部为 RTS 有效目标（analyze 已保证原本有值）
        self.assertEqual(detail["metrics"]["target_count"], 6)
        # 汇总中 PCHIP 分母只含可估内点；边缘点单列
        pchip_den = batch["summary"]["pchip_weight_denominator"]
        self.assertLess(pchip_den, 6)
        edge_times = {e["time_hour"] for e in detail["edge_unestimable"]}
        self.assertTrue(edge_times)
        # 边缘点的 pchip_error 为 None，绝不以 0 进入分母
        for p in detail["validation"]:
            if not p["pchip_estimable"]:
                self.assertIsNone(p["pchip_error"])
                self.assertIn(p["time_hour"], edge_times)
            else:
                self.assertIsNotNone(p["pchip_error"])
        # RTS 分母仍是全部有效遮挡点，原始缺失不参与
        self.assertEqual(batch["summary"]["rts_weight_denominator"], 6)
        self.assertEqual(batch["summary"]["edge_unestimable_count"], len(edge_times))

    def test_08_single_review_metric_equivalence(self):
        # 批量口径必须与现有单次复核 analyze 完全一致
        from src.services.statistics import analyze
        ds = repo.get("datasets", "ds-stations")
        mask = repo.get("masks", "mask-block12")
        study = repo.get("studies", "study-local-level")
        single = analyze(ds["rows"], mask, study)
        batch = self._create(["study-local-level"], "口径一致性批次")
        item = batch["items"][0]["detail"]
        m1, m2 = single["validation"]["metrics"], item["metrics"]
        for k in m1:
            self.assertEqual(m1[k], m2[k], f"指标 {k} 与单次复核不一致")
        self.assertEqual(single["checksum"], item["checksum"])

    def test_09_resume_pending_failure_then_success_isolation(self):
        # 中断时正处于失败状态的项，续跑仍会被重试（失败不属于已完成）
        batch = self._create(["study-bad-q"], "失败待续批次")
        self.assertEqual(batch["items"][0]["status"], BatchItemStatus.FAILED.value)
        # 修正参数后续跑
        study = repo.get("studies", "study-bad-q")
        study["q_per_hour"] = 0.03
        repo.put("studies", study)
        rerun = br.execute(batch["id"])
        self.assertEqual(rerun["status"], BatchStatus.COMPLETED.value)
        self.assertEqual(rerun["items"][0]["status"], BatchItemStatus.COMPLETED.value)
        self.assertEqual(rerun["items"][0]["error"], "")

    def test_10_missing_reference_is_item_failure_and_isolated(self):
        # 批次建完后删除其中一个方案引用的掩码：该项失败，其他项不受影响
        batch = self._create(["study-local-level", "study-02"], "引用失效批次")
        self.assertEqual(batch["status"], BatchStatus.COMPLETED.value)
        mask = repo.get("masks", "mask-block12")
        conn, q = repo.connect()
        try:
            conn.execute(f"DELETE FROM masks WHERE id={q}", ("mask-block12",))
            conn.commit()
        finally:
            conn.close()
        rerun = br.execute(batch["id"])
        statuses = {i["study_id"]: i["status"] for i in rerun["items"]}
        self.assertEqual(statuses["study-local-level"], BatchItemStatus.FAILED.value)
        self.assertTrue(rerun["items"][0]["error"])
        self.assertEqual(statuses["study-02"], BatchItemStatus.COMPLETED.value)
        self.assertEqual(rerun["status"], BatchStatus.PARTIAL.value)
        # 汇总只纳入存活成功项
        self.assertEqual(rerun["summary"]["rts_weight_denominator"], 12)
        # 恢复掩码后再续跑，失败项自动重试成功
        repo.put("masks", mask)
        recovered = br.execute(rerun["id"])
        self.assertEqual(recovered["status"], BatchStatus.COMPLETED.value)
        self.assertEqual(recovered["items"][0]["status"], BatchItemStatus.COMPLETED.value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
