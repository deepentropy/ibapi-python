#!/usr/bin/env python3
"""
Socket Optimization Benchmark
Demonstrates the impact of TCP_NODELAY and buffer tuning on latency.
"""

import socket
import time
import struct
import statistics
from typing import List


def benchmark_socket_config(use_nodelay: bool, buffer_size: int, recv_size: int, iterations: int = 1000):
    """Benchmark socket performance with different configurations"""

    # Create server socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', 0))
    server.listen(1)
    port = server.getsockname()[1]

    # Create client socket with test configuration
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    if use_nodelay:
        client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    if buffer_size:
        client.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, buffer_size)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, buffer_size)

    client.connect(('127.0.0.1', port))
    server_conn, _ = server.accept()

    # Configure server side too
    if use_nodelay:
        server_conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    if buffer_size:
        server_conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, buffer_size)
        server_conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, buffer_size)

    # Warm up
    for _ in range(100):
        test_msg = b"TEST" * 50  # 200 bytes
        client.send(test_msg)
        server_conn.recv(recv_size)

    # Benchmark small messages (typical for IB API control messages)
    small_msg_times = []
    test_msg = b"SMALL_MSG_DATA" * 5  # 70 bytes

    for _ in range(iterations):
        start = time.perf_counter_ns()
        client.send(test_msg)
        data = server_conn.recv(recv_size)
        end = time.perf_counter_ns()
        small_msg_times.append(end - start)

    # Benchmark medium messages (typical for market data)
    medium_msg_times = []
    test_msg = b"MARKET_DATA_TICK_STREAM" * 20  # 460 bytes

    for _ in range(iterations):
        start = time.perf_counter_ns()
        client.send(test_msg)
        data = server_conn.recv(recv_size)
        end = time.perf_counter_ns()
        medium_msg_times.append(end - start)

    # Benchmark large messages (historical data responses)
    large_msg_times = []
    test_msg = b"HISTORICAL_BAR_DATA_PAYLOAD" * 100  # 2700 bytes

    for _ in range(iterations):
        start = time.perf_counter_ns()
        client.send(test_msg)
        received = 0
        while received < len(test_msg):
            chunk = server_conn.recv(recv_size)
            received += len(chunk)
        end = time.perf_counter_ns()
        large_msg_times.append(end - start)

    # Clean up
    client.close()
    server_conn.close()
    server.close()

    return {
        'small': {
            'mean': statistics.mean(small_msg_times),
            'median': statistics.median(small_msg_times),
            'p95': sorted(small_msg_times)[int(0.95 * len(small_msg_times))],
            'p99': sorted(small_msg_times)[int(0.99 * len(small_msg_times))],
        },
        'medium': {
            'mean': statistics.mean(medium_msg_times),
            'median': statistics.median(medium_msg_times),
            'p95': sorted(medium_msg_times)[int(0.95 * len(medium_msg_times))],
            'p99': sorted(medium_msg_times)[int(0.99 * len(medium_msg_times))],
        },
        'large': {
            'mean': statistics.mean(large_msg_times),
            'median': statistics.median(large_msg_times),
            'p95': sorted(large_msg_times)[int(0.95 * len(large_msg_times))],
            'p99': sorted(large_msg_times)[int(0.99 * len(large_msg_times))],
        }
    }


def print_results(title: str, results: dict):
    """Print benchmark results"""
    print(f"\n{title}")
    print("=" * 80)
    for msg_type in ['small', 'medium', 'large']:
        data = results[msg_type]
        print(f"\n{msg_type.upper()} messages:")
        print(f"  Mean:   {data['mean']/1000:>10.2f} μs")
        print(f"  Median: {data['median']/1000:>10.2f} μs")
        print(f"  P95:    {data['p95']/1000:>10.2f} μs")
        print(f"  P99:    {data['p99']/1000:>10.2f} μs")


def calculate_improvement(baseline: dict, optimized: dict) -> dict:
    """Calculate percentage improvements"""
    improvements = {}
    for msg_type in ['small', 'medium', 'large']:
        improvements[msg_type] = {
            metric: ((baseline[msg_type][metric] - optimized[msg_type][metric]) /
                     baseline[msg_type][metric] * 100)
            for metric in ['mean', 'median', 'p95', 'p99']
        }
    return improvements


def main():
    print("\n" + "="*80)
    print("IB API SOCKET OPTIMIZATION BENCHMARK")
    print("Testing impact of TCP_NODELAY and buffer tuning")
    print("="*80)

    iterations = 1000

    # Test 1: Default configuration (current IB API)
    print("\n[1/4] Testing DEFAULT configuration (current IB API)...")
    default_results = benchmark_socket_config(
        use_nodelay=False,
        buffer_size=None,  # OS default (~128KB)
        recv_size=4096,    # Current IB API default
        iterations=iterations
    )
    print_results("DEFAULT Configuration (Current IB API)", default_results)

    # Test 2: TCP_NODELAY only
    print("\n[2/4] Testing TCP_NODELAY enabled...")
    nodelay_results = benchmark_socket_config(
        use_nodelay=True,
        buffer_size=None,
        recv_size=4096,
        iterations=iterations
    )
    print_results("TCP_NODELAY Enabled", nodelay_results)

    # Test 3: Larger buffers only
    print("\n[3/4] Testing LARGE BUFFERS (1MB)...")
    buffer_results = benchmark_socket_config(
        use_nodelay=False,
        buffer_size=1024*1024,  # 1MB
        recv_size=65536,         # 64KB recv
        iterations=iterations
    )
    print_results("Large Buffers (1MB socket, 64KB recv)", buffer_results)

    # Test 4: Full optimization (TCP_NODELAY + large buffers)
    print("\n[4/4] Testing FULLY OPTIMIZED configuration...")
    optimized_results = benchmark_socket_config(
        use_nodelay=True,
        buffer_size=1024*1024,  # 1MB
        recv_size=65536,         # 64KB recv
        iterations=iterations
    )
    print_results("Fully Optimized (TCP_NODELAY + Large Buffers)", optimized_results)

    # Calculate improvements
    print("\n" + "="*80)
    print("IMPROVEMENT ANALYSIS")
    print("="*80)

    # TCP_NODELAY impact
    nodelay_improvement = calculate_improvement(default_results, nodelay_results)
    print("\nTCP_NODELAY Impact:")
    for msg_type in ['small', 'medium', 'large']:
        print(f"\n{msg_type.upper()} messages:")
        for metric in ['mean', 'median', 'p95', 'p99']:
            print(f"  {metric.upper()}: {nodelay_improvement[msg_type][metric]:>6.2f}% faster")

    # Large buffers impact
    buffer_improvement = calculate_improvement(default_results, buffer_results)
    print("\nLarge Buffers Impact:")
    for msg_type in ['small', 'medium', 'large']:
        print(f"\n{msg_type.upper()} messages:")
        for metric in ['mean', 'median', 'p95', 'p99']:
            print(f"  {metric.upper()}: {buffer_improvement[msg_type][metric]:>6.2f}% faster")

    # Full optimization impact
    full_improvement = calculate_improvement(default_results, optimized_results)
    print("\nFully Optimized Impact:")
    for msg_type in ['small', 'medium', 'large']:
        print(f"\n{msg_type.upper()} messages:")
        for metric in ['mean', 'median', 'p95', 'p99']:
            print(f"  {metric.upper()}: {full_improvement[msg_type][metric]:>6.2f}% faster")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    avg_improvement = statistics.mean([
        full_improvement[msg_type]['mean']
        for msg_type in ['small', 'medium', 'large']
    ])

    print(f"\nAverage latency improvement: {avg_improvement:.2f}%")
    print(f"\nTCP_NODELAY is critical for low-latency trading applications.")
    print(f"Larger buffers improve throughput for high-volume data streams.")
    print(f"\nRecommended configuration:")
    print(f"  - socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)")
    print(f"  - socket.setsockopt(socket.SOL_SOCKET, SO_RCVBUF, 1024*1024)")
    print(f"  - socket.setsockopt(socket.SOL_SOCKET, SO_SNDBUF, 1024*1024)")
    print(f"  - socket.recv(65536)  # Instead of recv(4096)")
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
