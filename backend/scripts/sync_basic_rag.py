"""同步攻略到基础向量 Qdrant collection

将所有已发布攻略同步到 travel_guides_basic_chunks collection，
仅使用 chunk.content 构建向量，不注入标题、城市、标签、章节。

用法:
    cd backend
    python scripts/sync_basic_rag.py
    python scripts/sync_basic_rag.py --guide-id 123
    python scripts/sync_basic_rag.py --dry-run
"""

import argparse
import asyncio
import io
import sys
from pathlib import Path

# Windows GBK 终端兼容
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select
from dependencies.db_session import AsyncSessionLocal
from models.guide import TravelGuide, GuideStatus
from services.guide_rag_service import sync_guide_to_basic_rag


async def sync_all(dry_run: bool = False, guide_id: int = None):
    async with AsyncSessionLocal() as session:
        if guide_id:
            stmt = select(TravelGuide).where(TravelGuide.id == guide_id)
        else:
            stmt = select(TravelGuide).where(TravelGuide.status == GuideStatus.PUBLISHED)

        result = await session.scalars(stmt)
        guides = result.all()

        if not guides:
            print("[INFO] 没有找到符合条件的攻略")
            return

        print(f"[INFO] 找到 {len(guides)} 篇攻略待同步到基础 collection")
        if dry_run:
            for g in guides:
                print(f"  [DRY-RUN] guide_id={g.id} title={g.title}")
            return

        success = 0
        fail = 0
        for g in guides:
            ok = await sync_guide_to_basic_rag(g)
            if ok:
                success += 1
                print(f"  [OK] guide_id={g.id} title={g.title}")
            else:
                fail += 1
                print(f"  [FAIL] guide_id={g.id} title={g.title}")

        print(f"\n[DONE] 成功: {success}, 失败: {fail}, 总计: {len(guides)}")


def main():
    parser = argparse.ArgumentParser(description="同步攻略到基础向量 Qdrant collection")
    parser.add_argument("--guide-id", type=int, default=None, help="只同步指定 ID 的攻略")
    parser.add_argument("--dry-run", action="store_true", help="只列出，不同步")
    args = parser.parse_args()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(sync_all(dry_run=args.dry_run, guide_id=args.guide_id))
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


if __name__ == "__main__":
    main()
