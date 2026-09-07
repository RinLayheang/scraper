"""KCMS Collaborative Data Labeling Server.

Features:
- Multi-annotator collision prevention via leasing (5-minute lease locks).
- Real-time persistence to `scraper/raw_data/cleaned_comments.csv` and `ai_engine/data/comments.csv`.
- Atomic thread-safe file writes.
- Live progress stats and per-annotator leaderboards.
- History review and label editing.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Path Configuration
# ---------------------------------------------------------------------------
def _find_project_root(start: Path) -> Path:
    curr = start
    for _ in range(5):
        if (curr / "ai_engine").exists() and (curr / "scraper").exists():
            return curr
        if curr.parent == curr:
            break
        curr = curr.parent
    # Fallback to parent of scraper
    return Path(__file__).resolve().parents[2]

PROJECT_ROOT = _find_project_root(Path(__file__).resolve())
CLEANED_CSV_PATH = PROJECT_ROOT / "scraper" / "raw_data" / "cleaned_comments.csv"
AI_ENGINE_CSV_PATH = PROJECT_ROOT / "ai_engine" / "data" / "comments.csv"
STATIC_DIR = Path(__file__).resolve().parent / "static"

LEASE_TIMEOUT_SECONDS = 300  # 5 minutes

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------
class ClaimRequest(BaseModel):
    annotator: str = Field(..., min_length=1)

class HeartbeatRequest(BaseModel):
    comment_id: str
    annotator: str

class SubmitRequest(BaseModel):
    comment_id: str
    annotator: str = Field(..., min_length=1)
    severity_id: int = Field(..., ge=0, le=2)
    target_id: int = Field(..., ge=0, le=2)
    has_pii: bool = False
    notes: Optional[str] = ""

class SkipRequest(BaseModel):
    comment_id: str
    annotator: str

class EditRequest(BaseModel):
    comment_id: str
    annotator: str
    severity_id: int = Field(..., ge=0, le=2)
    target_id: int = Field(..., ge=0, le=2)
    has_pii: bool = False
    notes: Optional[str] = ""

# ---------------------------------------------------------------------------
# Data Store & Leasing Engine
# ---------------------------------------------------------------------------
class LabelStore:
    def __init__(self, primary_csv: Path, mirror_csv: Path) -> None:
        self.primary_csv = primary_csv
        self.mirror_csv = mirror_csv
        self.lock = threading.Lock()
        # Active leases: comment_id -> {"annotator": str, "timestamp": float}
        self.leases: dict[str, dict[str, Any]] = {}
        self.df: pd.DataFrame = self._load_data()

    def _load_data(self) -> pd.DataFrame:
        if not self.primary_csv.exists():
            raise FileNotFoundError(f"Primary dataset not found at {self.primary_csv}")
        
        df = pd.read_csv(self.primary_csv, dtype={"comment_id": str})
        
        # Ensure schema compliance
        required_defaults = {
            "comment_id": "",
            "text": "",
            "severity_id": 0,
            "target_id": 0,
            "has_pii": False,
            "link_flagged": False,
            "annotator": "",
            "split": "train",
            "notes": "",
        }
        for col, default_val in required_defaults.items():
            if col not in df.columns:
                df[col] = default_val
            else:
                if col == "annotator" or col == "notes":
                    df[col] = df[col].fillna("").astype(str)
                elif col in ("severity_id", "target_id"):
                    df[col] = df[col].fillna(0).astype(int)
                elif col in ("has_pii", "link_flagged"):
                    df[col] = df[col].fillna(False).astype(bool)
                else:
                    df[col] = df[col].fillna(default_val)
        return df

    def _clean_expired_leases(self) -> None:
        now = time.time()
        expired = [
            cid for cid, lease in self.leases.items()
            if now - lease["timestamp"] > LEASE_TIMEOUT_SECONDS
        ]
        for cid in expired:
            del self.leases[cid]

    def _save_atomic(self) -> None:
        """Atomically persist dataframe to disk to prevent file corruption."""
        # 1. Primary CSV
        self.primary_csv.parent.mkdir(parents=True, exist_ok=True)
        tmp_primary = self.primary_csv.with_suffix(".tmp")
        self.df.to_csv(tmp_primary, index=False, encoding="utf-8")
        os.replace(tmp_primary, self.primary_csv)

        # 2. Mirror CSV (ai_engine)
        self.mirror_csv.parent.mkdir(parents=True, exist_ok=True)
        tmp_mirror = self.mirror_csv.with_suffix(".tmp")
        self.df.to_csv(tmp_mirror, index=False, encoding="utf-8")
        os.replace(tmp_mirror, self.mirror_csv)

    def get_stats(self) -> dict[str, Any]:
        with self.lock:
            self._clean_expired_leases()
            total = len(self.df)
            is_labeled = self.df["annotator"].str.strip() != ""
            labeled_count = int(is_labeled.sum())
            remaining_count = total - labeled_count

            # Leaderboard by annotator
            annotator_counts = (
                self.df[is_labeled]["annotator"]
                .value_counts()
                .to_dict()
            )

            # Class distribution
            severity_counts = (
                self.df[is_labeled]["severity_id"]
                .value_counts()
                .to_dict()
            )
            target_counts = (
                self.df[is_labeled]["target_id"]
                .value_counts()
                .to_dict()
            )

            # Active annotators currently holding a lease
            active_labelers = list({l["annotator"] for l in self.leases.values()})

            return {
                "total": total,
                "labeled": labeled_count,
                "remaining": remaining_count,
                "percent_complete": round((labeled_count / total * 100) if total else 0, 1),
                "leaderboard": annotator_counts,
                "severity_counts": {
                    "SAFE (0)": int(severity_counts.get(0, 0)),
                    "OFFENSIVE (1)": int(severity_counts.get(1, 0)),
                    "HARMFUL (2)": int(severity_counts.get(2, 0)),
                },
                "target_counts": {
                    "NEITHER (0)": int(target_counts.get(0, 0)),
                    "PERSON (1)": int(target_counts.get(1, 0)),
                    "INSTITUTION (2)": int(target_counts.get(2, 0)),
                },
                "active_leases_count": len(self.leases),
                "active_labelers": active_labelers,
            }

    def claim_comment(self, annotator: str) -> Optional[dict[str, Any]]:
        with self.lock:
            self._clean_expired_leases()
            now = time.time()

            # Check if this annotator already has an active lease
            for cid, lease in self.leases.items():
                if lease["annotator"] == annotator:
                    lease["timestamp"] = now  # Refresh lease
                    row = self.df[self.df["comment_id"] == cid].iloc[0]
                    return self._format_comment_response(row)

            # Find unlabelled comments not currently leased
            is_unlabeled = self.df["annotator"].str.strip() == ""
            unlabeled_df = self.df[is_unlabeled]

            for _, row in unlabeled_df.iterrows():
                cid = str(row["comment_id"])
                if cid not in self.leases:
                    # Lease this comment
                    self.leases[cid] = {"annotator": annotator, "timestamp": now}
                    return self._format_comment_response(row)

            # All comments are labeled or currently leased
            return None

    def refresh_lease(self, comment_id: str, annotator: str) -> bool:
        with self.lock:
            if comment_id in self.leases and self.leases[comment_id]["annotator"] == annotator:
                self.leases[comment_id]["timestamp"] = time.time()
                return True
            return False

    def release_lease(self, comment_id: str, annotator: str) -> None:
        with self.lock:
            if comment_id in self.leases and self.leases[comment_id]["annotator"] == annotator:
                del self.leases[comment_id]

    def submit_label(
        self,
        comment_id: str,
        annotator: str,
        severity_id: int,
        target_id: int,
        has_pii: bool,
        notes: Optional[str] = "",
    ) -> bool:
        with self.lock:
            idx_matches = self.df.index[self.df["comment_id"] == comment_id].tolist()
            if not idx_matches:
                return False
            idx = idx_matches[0]

            # Update dataframe
            self.df.at[idx, "severity_id"] = int(severity_id)
            self.df.at[idx, "target_id"] = int(target_id)
            self.df.at[idx, "has_pii"] = bool(has_pii)
            self.df.at[idx, "annotator"] = str(annotator).strip()
            self.df.at[idx, "notes"] = str(notes or "").strip()

            # Release lease
            if comment_id in self.leases:
                del self.leases[comment_id]

            # Atomic save
            self._save_atomic()
            return True

    def get_history(self, annotator: str, limit: int = 15) -> list[dict[str, Any]]:
        with self.lock:
            user_df = self.df[self.df["annotator"] == annotator]
            recent = user_df.tail(limit).iloc[::-1]  # Most recent first
            return [self._format_comment_response(row) for _, row in recent.iterrows()]

    def _format_comment_response(self, row: pd.Series) -> dict[str, Any]:
        return {
            "comment_id": str(row["comment_id"]),
            "text": str(row["text"]),
            "severity_id": int(row.get("severity_id", 0)),
            "target_id": int(row.get("target_id", 0)),
            "has_pii": bool(row.get("has_pii", False)),
            "link_flagged": bool(row.get("link_flagged", False)),
            "annotator": str(row.get("annotator", "")),
            "notes": str(row.get("notes", "")),
            "split": str(row.get("split", "train")),
        }


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------
app = FastAPI(title="KCMS Collaborative Labeler", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize store
store = LabelStore(primary_csv=CLEANED_CSV_PATH, mirror_csv=AI_ENGINE_CSV_PATH)


@app.get("/api/stats")
def get_stats():
    return store.get_stats()


@app.post("/api/claim")
def claim_comment(payload: ClaimRequest):
    annotator = payload.annotator.strip()
    if not annotator:
        raise HTTPException(status_code=400, detail="Annotator name cannot be empty")
    comment = store.claim_comment(annotator)
    return {"has_comment": comment is not None, "comment": comment}


@app.post("/api/heartbeat")
def heartbeat(payload: HeartbeatRequest):
    refreshed = store.refresh_lease(payload.comment_id, payload.annotator)
    return {"refreshed": refreshed}


@app.post("/api/skip")
def skip_comment(payload: SkipRequest):
    store.release_lease(payload.comment_id, payload.annotator)
    return {"status": "skipped"}


@app.post("/api/submit")
def submit_label(payload: SubmitRequest):
    success = store.submit_label(
        comment_id=payload.comment_id,
        annotator=payload.annotator,
        severity_id=payload.severity_id,
        target_id=payload.target_id,
        has_pii=payload.has_pii,
        notes=payload.notes,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Comment ID not found")
    
    # Return next comment immediately for fast keyboard flow
    next_comment = store.claim_comment(payload.annotator)
    return {
        "status": "saved",
        "has_next": next_comment is not None,
        "next_comment": next_comment,
    }


@app.post("/api/edit")
def edit_label(payload: EditRequest):
    success = store.submit_label(
        comment_id=payload.comment_id,
        annotator=payload.annotator,
        severity_id=payload.severity_id,
        target_id=payload.target_id,
        has_pii=payload.has_pii,
        notes=payload.notes,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Comment ID not found")
    return {"status": "updated"}


@app.get("/api/history")
def get_history(annotator: str, limit: int = 15):
    return {"history": store.get_history(annotator, limit=limit)}


@app.get("/api/export")
def export_csv():
    return FileResponse(
        CLEANED_CSV_PATH,
        media_type="text/csv",
        filename="cleaned_comments_annotated.csv",
    )


# Serve Frontend Static Assets
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
