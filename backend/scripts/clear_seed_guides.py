"""清理种子攻略脚本

删除所有 content_path 以 seed:// 开头的攻略。
先删除 Qdrant 向量，成功后再删除 MySQL 记录。
Qdrant 删除失败时不删除 MySQL，避免留下脏向量。

用法:
    cd backend
    python scripts/clear_seed_guides.py --dry-run
    python scripts/clear_seed_guides.py
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.db_session import AsyncSessionLocal
from models.guide import TravelGuide
from services.guide_rag_service import remove_guide_from_rag
from core.logger import logger


async def clear_seed_guides(args: argparse.Namespace) -> None:
    """清理所有种子攻略"""
    async with AsyncSessionLocal() as session:
        # 查询所有 seed 攻略
        result = await session.scalars(
            select(TravelGuide).where(TravelGuide.content_path.like("seed://%"))
        )
        guides = result.all()

        if not guides:
            print("[INFO] 没有找到种子攻略 (content_path LIKE 'seed://%')")
            return

        print(f"[INFO] 找到 {len(guides)} 篇种子攻略")
        print()

        deleted_count = 0
        failed_count = 0
        skipped_count = 0

        for guide in guides:
            content_path = guide.content_path or ""
            tag = "[PREVIEW]" if args.dry_run else "[DELETE]"
            print(f"  {tag} [{content_path}] id={guide.id} title={guide.title}")

            if args.dry_run:
                skipped_count += 1
                continue

            # 先删除 Qdrant 向量
            qdrant_ok = False
            try:
                success = await remove_guide_from_rag(guide.id)
                qdrant_ok = success
            except Exception as e:
                logger.warning(f"删除攻略 {guide.id} Qdrant 向量失败: {e}")
                qdrant_ok = False

            # Qdrant 删除失败 → 不删除 MySQL，避免脏向量
            if not qdrant_ok:
                print(f"    [WARN] Qdrant 删除失败，跳过 MySQL 删除 (guide_id={guide.id})")
                failed_count += 1
                continue

            # Qdrant 删除成功 → 删除 MySQL 记录
            try:
                await session.delete(guide)
                deleted_count += 1
            except Exception as e:
                logger.error(f"删除攻略 {guide.id} MySQL 记录失败: {e}")
                failed_count += 1

        if not args.dry_run:
            await session.commit()

        print()
        print("=" * 50)
        print(f" 清理汇总")
        if args.dry_run:
            print(f"  将删除: {len(guides)} 篇种子攻略 (dry-run)")
        else:
            print(f"  总数: {len(guides)}")
            print(f"  已删除: {deleted_count}")
            print(f"  失败(Qdrant/MySQL): {failed_count}")
        print("=" * 50)

        if failed_count > 0 and not args.dry_run:
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="清理所有种子攻略")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不实际删除")
    args = parser.parse_args()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(clear_seed_guides(args))
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


if __name__ == "__main__":
    main()
