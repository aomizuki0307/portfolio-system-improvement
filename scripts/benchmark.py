"""HTTP benchmark for blog API endpoints."""
import asyncio
import argparse
import time
import statistics
import httpx

BASE_URL = "http://localhost:8000"

ENDPOINTS = [
    ("GET /api/v1/articles", "/api/v1/articles"),
    ("GET /api/v1/articles?page=1&page_size=50", "/api/v1/articles?page=1&page_size=50"),
    ("GET /api/v1/articles/1", "/api/v1/articles/1"),
    ("GET /api/v1/users", "/api/v1/users"),
    ("GET /api/v1/users/1", "/api/v1/users/1"),
    ("GET /api/v1/metrics", "/api/v1/metrics"),
    ("GET /health", "/health"),
]


async def benchmark_endpoint(client: httpx.AsyncClient, name: str, path: str, iterations: int = 50):
    times = []
    query_counts = []
    errors = 0

    # Warmup
    for _ in range(3):
        try:
            await client.get(f"{BASE_URL}{path}")
        except Exception:
            pass

    for _ in range(iterations):
        try:
            start = time.perf_counter()
            resp = await client.get(f"{BASE_URL}{path}")
            elapsed = (time.perf_counter() - start) * 1000

            if resp.status_code == 200:
                times.append(elapsed)
                qc = resp.headers.get("X-Query-Count", "?")
                if qc != "?":
                    query_counts.append(int(qc))
            else:
                errors += 1
        except Exception:
            errors += 1

    if not times:
        return {"name": name, "error": f"All {iterations} requests failed"}

    return {
        "name": name,
        "avg_ms": round(statistics.mean(times), 2),
        "p50_ms": round(sorted(times)[len(times) // 2], 2),
        "p95_ms": round(sorted(times)[int(len(times) * 0.95)], 2),
        "p99_ms": round(sorted(times)[int(len(times) * 0.99)], 2),
        "min_ms": round(min(times), 2),
        "max_ms": round(max(times), 2),
        "queries": round(statistics.mean(query_counts), 1) if query_counts else "N/A",
        "errors": errors,
        "iterations": len(times),
    }


async def run_benchmark(iterations: int = 50):
    print("=" * 80)
    print(f"Blog API Benchmark — {iterations} iterations per endpoint")
    print(f"Target: {BASE_URL}")
    print("=" * 80)

    # Check health
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{BASE_URL}/health")
            if resp.status_code != 200:
                print(f"ERROR: Health check failed ({resp.status_code})")
                return
            print(f"Health: {resp.json()}")
        except Exception as e:
            print(f"ERROR: Cannot connect to {BASE_URL} — {e}")
            return

        print()
        print(f"{'Endpoint':<45} {'Avg':>8} {'P50':>8} {'P95':>8} {'P99':>8} {'Queries':>8} {'Err':>4}")
        print("-" * 80)

        results = []
        for name, path in ENDPOINTS:
            result = await benchmark_endpoint(client, name, path, iterations)
            results.append(result)

            if "error" in result:
                print(f"{result['name']:<45} {'ERROR':>8}")
            else:
                print(
                    f"{result['name']:<45} "
                    f"{result['avg_ms']:>7.1f}ms "
                    f"{result['p50_ms']:>7.1f}ms "
                    f"{result['p95_ms']:>7.1f}ms "
                    f"{result['p99_ms']:>7.1f}ms "
                    f"{str(result['queries']):>8} "
                    f"{result['errors']:>4}"
                )

        print("-" * 80)
        print("\nBenchmark complete.")


def main():
    parser = argparse.ArgumentParser(description="Benchmark blog API")
    parser.add_argument("-n", "--iterations", type=int, default=50, help="Iterations per endpoint")
    parser.add_argument("--base-url", default=BASE_URL, help="API base URL")
    args = parser.parse_args()

    global BASE_URL
    BASE_URL = args.base_url
    asyncio.run(run_benchmark(args.iterations))


if __name__ == "__main__":
    main()
