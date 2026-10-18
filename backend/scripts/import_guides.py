"""旅游攻略测试语料批量导入程序

将本地 JSON + Markdown 攻略文件批量导入 MySQL travel_guides 表，
并复用 sync_guide_to_rag() 同步到 Qdrant。

用法:
    cd backend
    python scripts/import_guides.py --dir data/seed_guides --author-username admin --dry-run
    python scripts/import_guides.py --dir data/seed_guides --author-username admin
    python scripts/import_guides.py --dir data/seed_guides --resync-only
"""

import argparse
import asyncio
import io
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Windows GBK 终端兼容：重新配置 stdout/stderr 为 UTF-8，
# 避免 EsAgent 框架中的 emoji 字符导致 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 确保从 backend 根目录运行时 import 正确
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel, Field, field_validator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.db_session import AsyncSessionLocal
from models.guide import TravelGuide, GuideStatus, ContentFormat
from models.user import User
from services.guide_rag_service import sync_guide_to_rag, sync_guide_to_basic_rag, remove_guide_from_rag, remove_guide_from_basic_rag
from core.logger import logger


# ========== 枚举兼容转换 ==========

def parse_guide_status(value: str) -> GuideStatus:
    """兼容枚举 name/value 以及大小写差异"""
    value = (value or "published").strip().lower()
    for item in GuideStatus:
        if item.value.lower() == value or item.name.lower() == value:
            return item
    raise ValueError(f"非法攻略状态: {value}")


def parse_content_format(value: str) -> ContentFormat:
    """兼容枚举 name/value 以及大小写差异"""
    value = (value or "markdown").strip().lower()
    for item in ContentFormat:
        if item.value.lower() == value or item.name.lower() == value:
            return item
    raise ValueError(f"非法内容格式: {value}")


# ========== 种子攻略数据模型 ==========

class SeedGuide(BaseModel):
    """种子攻略元数据"""
    import_key: str
    title: str
    city: str
    summary: str = ""
    content_file: Optional[str] = None
    content: Optional[str] = None
    content_format: str = "markdown"
    tags: List[str] = Field(default_factory=list)
    status: str = "published"
    is_official: bool = True
    is_ai_generated: bool = False
    author_id: Optional[int] = None
    author_username: Optional[str] = None

    @field_validator("import_key", "title", "city")
    @classmethod
    def must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("不能为空")
        return v.strip()

    @field_validator("is_ai_generated")
    @classmethod
    def must_be_false(cls, v: bool) -> bool:
        if v:
            logger.warning("is_ai_generated=true 的攻略不会被 sync_guide_to_rag 同步到 Qdrant")
        return v


# ========== 核心函数 ==========

def load_seed_guide(json_path: Path) -> tuple[SeedGuide, str]:
    """读取 JSON + 关联 Markdown 正文"""
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    seed = SeedGuide(**raw)

    # content_file 和 content 至少有一个
    if seed.content_file:
        md_path = json_path.parent / seed.content_file
        if not md_path.exists():
            raise FileNotFoundError(f"正文文件不存在: {md_path}")
        content = md_path.read_text(encoding="utf-8")
    elif seed.content:
        content = seed.content
    else:
        raise ValueError("content_file 和 content 至少填一个")

    return seed, content


async def resolve_author_id(
    session: AsyncSession,
    seed: SeedGuide,
    default_author_id: Optional[int],
    default_username: Optional[str],
) -> int:
    """按优先级解析作者 ID: seed.author_id > seed.author_username 查库 > default_author_id > default_username 查库"""
    # 1. seed 明确指定 author_id
    if seed.author_id:
        return seed.author_id

    # 2. seed 指定 author_username，查库
    username = seed.author_username or default_username
    if username:
        result = await session.scalar(
            select(User).where(User.username == username)
        )
        if result:
            return result.id
        raise ValueError(f"用户不存在: {username}")

    # 3. 默认 author_id
    if default_author_id:
        return default_author_id

    raise ValueError("无法确定作者 ID：请指定 --author-id 或 --author-username")


async def find_existing_guide(
    session: AsyncSession,
    import_key: str,
) -> Optional[TravelGuide]:
    """通过 content_path 查找已有攻略"""
    content_path = f"seed://{import_key}"
    return await session.scalar(
        select(TravelGuide).where(TravelGuide.content_path == content_path)
    )


async def upsert_one_guide(
    session: AsyncSession,
    seed: SeedGuide,
    content: str,
    author_id: int,
) -> tuple[TravelGuide, str]:
    """插入或更新攻略，返回 (guide, action)"""
    existing = await find_existing_guide(session, seed.import_key)

    if existing:
        existing.title = seed.title
        existing.city = seed.city
        existing.summary = seed.summary or ""
        existing.content = content
        existing.content_format = parse_content_format(seed.content_format)
        existing.content_path = f"seed://{seed.import_key}"
        existing.tags = seed.tags
        existing.status = parse_guide_status(seed.status)
        existing.is_official = seed.is_official
        existing.is_ai_generated = seed.is_ai_generated
        existing.author_id = author_id
        await session.flush()
        await session.refresh(existing)
        return existing, "update"

    guide = TravelGuide(
        title=seed.title,
        city=seed.city,
        summary=seed.summary or "",
        content=content,
        content_format=parse_content_format(seed.content_format),
        content_path=f"seed://{seed.import_key}",
        tags=seed.tags,
        status=parse_guide_status(seed.status),
        is_official=seed.is_official,
        is_ai_generated=seed.is_ai_generated,
        author_id=author_id,
    )
    session.add(guide)
    await session.flush()
    await session.refresh(guide)
    return guide, "insert"


async def sync_one_guide_to_qdrant(guide: TravelGuide) -> Dict[str, str]:
    """同步单篇攻略到 Qdrant（增强版 + 基础版两个 collection）"""
    result = {
        "qdrant_delete_status": "skipped",
        "qdrant_sync_status": "skipped",
        "basic_sync_status": "skipped",
    }

    # 先删除两个 collection 的旧向量
    try:
        await remove_guide_from_rag(guide.id)
        result["qdrant_delete_status"] = "deleted"
    except Exception as e:
        logger.warning(f"删除攻略 {guide.id} 旧 Qdrant 向量失败: {e}")
        result["qdrant_delete_status"] = "failed"

    try:
        await remove_guide_from_basic_rag(guide.id)
    except Exception as e:
        logger.warning(f"删除攻略 {guide.id} 旧基础 Qdrant 向量失败: {e}")

    # 判断是否需要同步
    if guide.status == GuideStatus.PUBLISHED and not guide.is_ai_generated:
        try:
            success = await sync_guide_to_rag(guide)
            result["qdrant_sync_status"] = "synced" if success else "failed"
        except Exception as e:
            logger.error(f"同步攻略 {guide.id} 到 Qdrant 失败: {e}")
            result["qdrant_sync_status"] = "failed"

        try:
            basic_success = await sync_guide_to_basic_rag(guide)
            result["basic_sync_status"] = "synced" if basic_success else "failed"
        except Exception as e:
            logger.error(f"同步攻略 {guide.id} 到基础 Qdrant 失败: {e}")
            result["basic_sync_status"] = "failed"
    else:
        # 非 published 或 AI 生成：只删除不同步
        if result["qdrant_delete_status"] == "deleted":
            result["qdrant_sync_status"] = "removed"
        else:
            result["qdrant_sync_status"] = "skipped"

    return result


async def resync_one_guide(session, guide: TravelGuide, seed_is_ai_generated: bool = False) -> Dict[str, str]:
    """resync-only 模式：同步 Qdrant，并修复 is_ai_generated 不一致"""
    if guide.is_ai_generated and not seed_is_ai_generated:
        guide.is_ai_generated = False
        await session.flush()
    return await sync_one_guide_to_qdrant(guide)


# ========== 主流程 ==========

async def import_guides(args: argparse.Namespace) -> None:
    """主导入流程"""
    seed_dir = Path(args.dir).resolve()
    if not seed_dir.is_dir():
        print(f"[ERROR] 目录不存在: {seed_dir}")
        sys.exit(1)

    # 收集所有 JSON 文件（忽略 _ 开头的）
    json_files = sorted([
        f for f in seed_dir.glob("*.json")
        if not f.name.startswith("_")
    ])

    if not json_files:
        print(f"[WARN] 目录中没有 JSON 文件: {seed_dir}")
        return

    print(f"[DIR] 种子攻略目录: {seed_dir}")
    print(f"[INFO] 发现 {len(json_files)} 个 JSON 文件")
    print(f"[MODE] {'DRY-RUN' if args.dry_run else 'RESYNC-ONLY' if args.resync_only else 'IMPORT'}")
    print()

    results: List[Dict] = []
    success_count = 0
    fail_count = 0
    insert_count = 0
    update_count = 0
    resync_count = 0
    qdrant_synced = 0
    qdrant_failed = 0
    basic_synced = 0
    basic_failed = 0

    async with AsyncSessionLocal() as session:
        for json_path in json_files:
            record = {
                "file": json_path.name,
                "import_key": None,
                "guide_id": None,
                "title": None,
                "city": None,
                "action": "pending",
                "mysql_status": "skipped",
                "qdrant_delete_status": "skipped",
                "qdrant_sync_status": "skipped",
                "error": None,
            }

            try:
                # 读取和校验
                seed, content = load_seed_guide(json_path)
                record["import_key"] = seed.import_key
                record["title"] = seed.title
                record["city"] = seed.city

                # resync-only 模式
                if args.resync_only:
                    existing = await find_existing_guide(session, seed.import_key)
                    if not existing:
                        raise ValueError(
                            f"resync-only: 未找到 content_path=seed://{seed.import_key} 的攻略"
                        )
                    record["guide_id"] = existing.id
                    record["action"] = "resync"

                    if not args.dry_run:
                        qdrant_result = await resync_one_guide(session, existing, seed.is_ai_generated)
                        record.update(qdrant_result)
                        if qdrant_result["qdrant_sync_status"] == "synced":
                            qdrant_synced += 1
                        elif qdrant_result["qdrant_sync_status"] == "failed":
                            qdrant_failed += 1
                    else:
                        record["qdrant_delete_status"] = "dry-run"
                        record["qdrant_sync_status"] = "dry-run"

                    resync_count += 1
                    success_count += 1
                    print(f"  [OK] [{seed.import_key}] resync (guide_id={existing.id})")
                    results.append(record)
                    continue

                # 正常导入模式
                author_id = await resolve_author_id(
                    session, seed, args.author_id, args.author_username
                )

                if args.dry_run:
                    existing = await find_existing_guide(session, seed.import_key)
                    record["action"] = "dry-run (" + ("update" if existing else "insert") + ")"
                    record["mysql_status"] = "dry-run"
                    record["qdrant_delete_status"] = "dry-run"
                    record["qdrant_sync_status"] = "dry-run"
                    success_count += 1
                    print(f"  [OK] [{seed.import_key}] dry-run: {'update' if existing else 'insert'}")
                else:
                    guide, action = await upsert_one_guide(session, seed, content, author_id)
                    await session.commit()
                    await session.refresh(guide)

                    record["guide_id"] = guide.id
                    record["action"] = action
                    record["mysql_status"] = "ok"

                    if action == "insert":
                        insert_count += 1
                    else:
                        update_count += 1

                    # 同步 Qdrant
                    qdrant_result = await sync_one_guide_to_qdrant(guide)
                    record.update(qdrant_result)
                    if qdrant_result["qdrant_sync_status"] == "synced":
                        qdrant_synced += 1
                    elif qdrant_result["qdrant_sync_status"] == "failed":
                        qdrant_failed += 1
                    if qdrant_result.get("basic_sync_status") == "synced":
                        basic_synced += 1
                    elif qdrant_result.get("basic_sync_status") == "failed":
                        basic_failed += 1

                    success_count += 1
                    print(f"  [OK] [{seed.import_key}] {action} (guide_id={guide.id}, qdrant={qdrant_result['qdrant_sync_status']})")

            except Exception as e:
                fail_count += 1
                record["action"] = "failed"
                record["error"] = str(e)
                print(f"  [FAIL] [{json_path.name}] 失败: {e}")

                if args.fail_fast:
                    results.append(record)
                    break

            results.append(record)

    # 写入报告
    report_path = Path(args.report) if args.report else seed_dir / "_import_report.json"
    report = {
        "timestamp": datetime.now().isoformat(),
        "mode": "dry-run" if args.dry_run else "resync-only" if args.resync_only else "import",
        "summary": {
            "total_files": len(json_files),
            "success": success_count,
            "failed": fail_count,
            "insert": insert_count,
            "update": update_count,
            "resync": resync_count,
            "qdrant_synced": qdrant_synced,
            "qdrant_failed": qdrant_failed,
            "basic_synced": basic_synced,
            "basic_failed": basic_failed,
        },
        "details": results,
    }

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("=" * 50)
    print(f" 导入汇总")
    print(f"  总文件数: {len(json_files)}")
    print(f"  成功: {success_count}")
    print(f"  失败: {fail_count}")
    print(f"  INSERT: {insert_count}")
    print(f"  UPDATE: {update_count}")
    print(f"  RESYNC: {resync_count}")
    print(f"  Qdrant 同步成功: {qdrant_synced}")
    print(f"  Qdrant 同步失败: {qdrant_failed}")
    print(f"  基础 Qdrant 同步成功: {basic_synced}")
    print(f"  基础 Qdrant 同步失败: {basic_failed}")
    print(f"  报告路径: {report_path}")
    print("=" * 50)

    if fail_count > 0 and not args.dry_run:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="旅游攻略测试语料批量导入")
    parser.add_argument("--dir", required=True, help="种子攻略目录")
    parser.add_argument("--author-id", type=int, default=None, help="默认作者 ID")
    parser.add_argument("--author-username", default="admin", help="默认作者用户名 (默认: admin)")
    parser.add_argument("--dry-run", action="store_true", help="只读取和校验，不写 MySQL，不同步 Qdrant")
    parser.add_argument("--resync-only", action="store_true", help="不修改 MySQL，只重新同步 Qdrant")
    parser.add_argument("--fail-fast", action="store_true", help="遇到错误立即停止")
    parser.add_argument("--report", default=None, help="导入报告输出路径")

    args = parser.parse_args()

    # 手动创建事件循环，跟 init_admin.py 一致
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(import_guides(args))
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


if __name__ == "__main__":
    main()
