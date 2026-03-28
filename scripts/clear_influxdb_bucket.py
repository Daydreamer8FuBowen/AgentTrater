#!/usr/bin/env python
"""清空 InfluxDB 指定 bucket 中的全部数据。

脚本会删除 bucket 内自创建以来到现在的所有数据点。
使用前请确保：
1. InfluxDB 服务正在运行
2. 配置文件中的 token、url、org、bucket 正确
3. 该 token 有删除权限

用法:
    python scripts/clear_influxdb_bucket.py        # 交互模式，需确认
    python scripts/clear_influxdb_bucket.py --force # 直接清空，不需确认
"""

import argparse
import sys
from datetime import datetime, timezone

from influxdb_client import InfluxDBClient

from agent_trader.core.config import Settings


def clear_influxdb_bucket(force: bool = False):
    """清空 InfluxDB bucket 中的全部数据。

    Args:
        force: 如果为 True，跳过确认提示直接删除
    """

    # 加载配置
    settings = Settings()
    influx_config = settings.influx

    print(f"🔗 连接到 InfluxDB: {influx_config.url}")
    print(f"📦 Bucket: {influx_config.bucket}")
    print(f"🏢 Organization: {influx_config.org}")
    print()

    # 创建客户端，增加超时时间处理大量数据删除
    # InfluxDBClient 的 timeout 参数是毫秒单位
    client = InfluxDBClient(
        url=influx_config.url,
        token=influx_config.token,
        org=influx_config.org,
        timeout=300000,  # 300 秒（5 分钟）用于删除大量数据
    )

    # 测试连接
    try:
        if not client.ping():
            print("❌ 无法连接到 InfluxDB，请检查配置和服务状态")
            return False
        print("✅ InfluxDB 连接成功")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False

    print()

    # 获取 delete API
    delete_api = client.delete_api()
    org = influx_config.org
    bucket = influx_config.bucket

    # 设定删除时间范围：从很早的时间到现在
    start = "1970-01-01T00:00:00Z"  # Unix epoch
    stop = datetime.now(tz=timezone.utc).isoformat()

    try:
        print(f"🗑️  正在删除数据范围: {start} 到 {stop}")
        print("   (这将删除 bucket 中的所有数据)")
        print()

        # 确认删除
        if not force:
            confirm = input("⚠️  确认删除? (输入 'yes' 以确认): ")
            if confirm.lower() != "yes":
                print("❌ 已取消操作")
                return False
        else:
            print("⚠️  使用 --force 标志，跳过确认，直接执行删除...")
        print()

        print("🔄 正在执行删除操作... (可能需要几分钟)")

        # 执行删除
        delete_api.delete(
            start=start,
            stop=stop,
            bucket=bucket,
            org=org,
            predicate="",  # 空 predicate 表示删除所有数据
        )

        print("✅ 数据删除成功!")
        print()

        # 验证结果
        try:
            query_api = client.query_api()
            query = f'''from(bucket: "{bucket}")
            |> range(start: 1970-01-01T00:00:00Z)
            |> limit(n: 1)'''
            tables = query_api.query(org=org, query=query)

            total_records = 0
            for table in tables:
                total_records += len(table.records)

            if total_records == 0:
                print("✓ 验证完成: bucket 已清空（0 条记录）")
            else:
                print(f"⚠️  验证: bucket 仍有 {total_records} 条记录")
        except Exception as e:
            print(f"⚠️  验证查询异常: {e}")

        return True

    except Exception as e:
        print(f"❌ 删除操作失败: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        print()
        print("🔌 关闭连接...")
        client.close()
        print("完成!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="清空 InfluxDB bucket 中的全部数据")
    parser.add_argument("--force", action="store_true", help="跳过确认提示，直接删除")

    args = parser.parse_args()
    success = clear_influxdb_bucket(force=args.force)
    sys.exit(0 if success else 1)
