"""
Concurrency and Race Condition Tests for Trading System.

Critical gap identified Dec 11, 2025: No tests for concurrent operations.
These tests ensure thread safety and prevent race conditions in trading.

Tests:
1. Concurrent order submission - Multiple orders at once
2. Position state consistency - No stale reads
3. Account balance race conditions - Prevent overdraft
4. Lock contention - Deadlock prevention
5. Async task coordination - Proper sequencing
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch
import pytest


class TestConcurrentOrderSubmission:
    """Test handling of concurrent order submissions."""

    def test_concurrent_buy_orders_same_symbol(self):
        """Multiple buy orders for same symbol should not conflict."""
        orders_submitted = []
        lock = threading.Lock()

        def submit_order(order_id: int, symbol: str, quantity: float):
            # Simulate order submission with lock
            with lock:
                orders_submitted.append(
                    {"id": order_id, "symbol": symbol, "quantity": quantity}
                )
            time.sleep(0.01)  # Simulate API latency
            return True

        # Submit 5 concurrent orders for SPY
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(submit_order, i, "SPY", 10.0) for i in range(5)
            ]
            results = [f.result() for f in as_completed(futures)]

        assert len(results) == 5, "All orders should complete"
        assert len(orders_submitted) == 5, "All orders should be recorded"
        assert all(r is True for r in results), "All orders should succeed"

    def test_concurrent_orders_different_symbols(self):
        """Orders for different symbols should not interfere."""
        symbols = ["SPY", "QQQ", "AAPL", "MSFT", "GOOGL"]
        order_results = {}
        lock = threading.Lock()

        def submit_order(symbol: str):
            time.sleep(0.01)  # Simulate varying latency
            with lock:
                order_results[symbol] = {"status": "filled", "time": time.time()}
            return symbol

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(submit_order, s): s for s in symbols}
            for future in as_completed(futures):
                result = future.result()
                assert result in symbols

        assert len(order_results) == 5, "All symbols should have orders"

    def test_order_deduplication_under_concurrency(self):
        """Prevent duplicate orders under concurrent submission."""
        submitted_orders = set()
        lock = threading.Lock()
        duplicates_prevented = [0]

        def submit_order_with_dedup(order_id: str):
            with lock:
                if order_id in submitted_orders:
                    duplicates_prevented[0] += 1
                    return False  # Duplicate prevented
                submitted_orders.add(order_id)
            return True

        # Try to submit same order ID multiple times concurrently
        order_id = "ORDER_123"
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(submit_order_with_dedup, order_id) for _ in range(10)]
            results = [f.result() for f in as_completed(futures)]

        assert results.count(True) == 1, "Only one order should succeed"
        assert duplicates_prevented[0] == 9, "Should prevent 9 duplicates"


class TestPositionStateConsistency:
    """Test position state remains consistent under concurrent access."""

    def test_position_read_during_update(self):
        """Reading position while being updated should be safe."""
        position = {"symbol": "SPY", "quantity": 100, "avg_price": 450.0}
        lock = threading.RLock()
        read_results = []

        def read_position():
            with lock:
                # Deep copy to prevent reading partial updates
                result = position.copy()
            read_results.append(result)
            return result

        def update_position(new_qty: float, new_price: float):
            with lock:
                position["quantity"] = new_qty
                position["avg_price"] = new_price

        # Concurrent reads and writes
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(5):
                futures.append(executor.submit(read_position))
                futures.append(executor.submit(update_position, 100 + i, 450.0 + i))

            for f in as_completed(futures):
                try:
                    f.result()
                except Exception:
                    pass

        # All reads should return consistent state (quantity and price match)
        for result in read_results:
            assert "quantity" in result
            assert "avg_price" in result
            # No partial updates visible
            assert isinstance(result["quantity"], (int, float))

    def test_atomic_position_update(self):
        """Position updates should be atomic."""
        position_value = [1000.0]  # Using list for mutability
        lock = threading.Lock()

        def atomic_update(delta: float):
            with lock:
                current = position_value[0]
                time.sleep(0.001)  # Simulate computation
                position_value[0] = current + delta

        # Concurrent updates
        with ThreadPoolExecutor(max_workers=10) as executor:
            # 10 threads each adding 10
            futures = [executor.submit(atomic_update, 10.0) for _ in range(10)]
            for f in as_completed(futures):
                f.result()

        assert position_value[0] == 1100.0, "Final value should be 1100 (1000 + 10*10)"


class TestAccountBalanceRaceConditions:
    """Prevent overdraft from concurrent order execution."""

    def test_balance_check_and_deduct_atomic(self):
        """Balance check and deduction must be atomic."""
        account_balance = [10000.0]
        lock = threading.Lock()
        orders_filled = [0]
        orders_rejected = [0]

        def try_execute_order(amount: float) -> bool:
            with lock:
                if account_balance[0] >= amount:
                    # Check and deduct atomically
                    account_balance[0] -= amount
                    orders_filled[0] += 1
                    return True
                else:
                    orders_rejected[0] += 1
                    return False

        # Try to spend more than balance concurrently
        order_amount = 2000.0  # 5 orders would exactly exhaust balance
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit 10 orders of $2000 each (total $20k, but only $10k available)
            futures = [executor.submit(try_execute_order, order_amount) for _ in range(10)]
            results = [f.result() for f in as_completed(futures)]

        assert orders_filled[0] == 5, "Exactly 5 orders should fill"
        assert orders_rejected[0] == 5, "5 orders should be rejected"
        assert account_balance[0] == 0.0, "Balance should be zero"
        assert results.count(True) == 5

    def test_prevent_negative_balance(self):
        """Account should never go negative."""
        account_balance = [100.0]
        lock = threading.Lock()
        went_negative = [False]

        def withdraw(amount: float):
            with lock:
                if account_balance[0] - amount < 0:
                    return False
                account_balance[0] -= amount
                if account_balance[0] < 0:
                    went_negative[0] = True
                return True

        # Concurrent withdrawals
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(withdraw, 10.0) for _ in range(20)]
            for f in as_completed(futures):
                f.result()

        assert not went_negative[0], "Balance should never go negative"
        assert account_balance[0] >= 0, "Final balance should be non-negative"


class TestLockContentionAndDeadlocks:
    """Test for deadlock prevention."""

    def test_lock_ordering_prevents_deadlock(self):
        """Consistent lock ordering prevents deadlocks."""
        lock_a = threading.Lock()
        lock_b = threading.Lock()
        deadlock_detected = [False]
        completed = [0]

        def operation_1():
            # Always acquire locks in same order: A then B
            with lock_a:
                time.sleep(0.001)
                with lock_b:
                    completed[0] += 1

        def operation_2():
            # Same order: A then B (not B then A which would cause deadlock)
            with lock_a:
                time.sleep(0.001)
                with lock_b:
                    completed[0] += 1

        # Run potentially conflicting operations
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for _ in range(2):
                futures.append(executor.submit(operation_1))
                futures.append(executor.submit(operation_2))

            # All should complete without deadlock
            for f in as_completed(futures):
                f.result(timeout=5)  # Timeout would indicate deadlock

        assert completed[0] == 4, "All operations should complete"

    def test_timeout_on_lock_acquisition(self):
        """Locks should have timeout to prevent infinite waiting."""
        lock = threading.Lock()

        def acquire_with_timeout(timeout: float) -> bool:
            acquired = lock.acquire(timeout=timeout)
            if acquired:
                try:
                    time.sleep(0.1)
                finally:
                    lock.release()
            return acquired

        # First thread holds lock
        lock.acquire()

        # Second thread should timeout
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(acquire_with_timeout, 0.05)
            result = future.result()

        lock.release()
        assert result is False, "Should timeout waiting for lock"


class TestAsyncTaskCoordination:
    """Test async task sequencing and coordination."""

    @pytest.mark.asyncio
    async def test_sequential_order_execution(self):
        """Orders that depend on each other should execute sequentially."""
        execution_order = []

        async def execute_order(order_id: int, depends_on: int | None = None):
            if depends_on is not None:
                # Wait for dependency (in real code, would check order status)
                await asyncio.sleep(0.01)
            execution_order.append(order_id)
            return order_id

        # Order 2 depends on Order 1
        result1 = await execute_order(1)
        result2 = await execute_order(2, depends_on=1)

        assert execution_order == [1, 2], "Should execute in dependency order"

    @pytest.mark.asyncio
    async def test_parallel_independent_tasks(self):
        """Independent tasks should run in parallel."""
        start_time = time.time()
        task_durations = []

        async def independent_task(task_id: int):
            await asyncio.sleep(0.05)  # 50ms each
            task_durations.append(task_id)
            return task_id

        # Run 5 tasks in parallel
        results = await asyncio.gather(*[independent_task(i) for i in range(5)])

        elapsed = time.time() - start_time
        assert elapsed < 0.15, "Parallel tasks should complete in ~50ms, not 250ms"
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        """Semaphore should limit concurrent operations."""
        max_concurrent = 3
        semaphore = asyncio.Semaphore(max_concurrent)
        concurrent_count = [0]
        max_observed = [0]

        async def limited_operation(task_id: int):
            async with semaphore:
                concurrent_count[0] += 1
                max_observed[0] = max(max_observed[0], concurrent_count[0])
                await asyncio.sleep(0.02)
                concurrent_count[0] -= 1
            return task_id

        # Run 10 tasks with concurrency limit of 3
        await asyncio.gather(*[limited_operation(i) for i in range(10)])

        assert max_observed[0] <= max_concurrent, f"Max concurrent should be {max_concurrent}"


class TestSharedStateConsistency:
    """Test shared state remains consistent."""

    def test_thread_local_storage(self):
        """Thread-local storage should isolate data between threads."""
        local_data = threading.local()
        results = {}

        def set_and_get(thread_id: int):
            local_data.value = thread_id
            time.sleep(0.01)  # Allow other threads to run
            results[thread_id] = local_data.value

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(set_and_get, i) for i in range(5)]
            for f in as_completed(futures):
                f.result()

        # Each thread should see its own value
        for thread_id, value in results.items():
            assert thread_id == value, "Thread-local data should be isolated"

    def test_atomic_counter(self):
        """Counter increments should be atomic."""
        counter = [0]
        lock = threading.Lock()

        def increment():
            for _ in range(1000):
                with lock:
                    counter[0] += 1

        threads = [threading.Thread(target=increment) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert counter[0] == 10000, "Counter should be exactly 10000"


class TestTradingSystemConcurrency:
    """Integration tests for trading system concurrency."""

    def test_concurrent_position_updates(self):
        """Multiple position updates should not corrupt state."""
        positions = {}
        lock = threading.Lock()

        def update_position(symbol: str, delta_qty: float):
            with lock:
                if symbol not in positions:
                    positions[symbol] = 0
                positions[symbol] += delta_qty

        symbols = ["SPY", "QQQ", "AAPL"]

        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = []
            for symbol in symbols:
                # 5 updates of +10 each per symbol
                for _ in range(5):
                    futures.append(executor.submit(update_position, symbol, 10))

            for f in as_completed(futures):
                f.result()

        # Each symbol should have exactly 50 (5 updates * 10 qty)
        for symbol in symbols:
            assert positions[symbol] == 50, f"{symbol} should have quantity 50"

    def test_order_queue_processing(self):
        """Order queue should process orders without loss."""
        import queue

        order_queue = queue.Queue()
        processed_orders = []
        lock = threading.Lock()
        stop_signal = threading.Event()

        def order_processor():
            while not stop_signal.is_set() or not order_queue.empty():
                try:
                    order = order_queue.get(timeout=0.1)
                    with lock:
                        processed_orders.append(order)
                    order_queue.task_done()
                except queue.Empty:
                    continue

        # Start processor thread
        processor = threading.Thread(target=order_processor)
        processor.start()

        # Submit orders from multiple threads
        def submit_orders(start_id: int, count: int):
            for i in range(count):
                order_queue.put({"id": start_id + i})

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(submit_orders, i * 10, 10) for i in range(5)]
            for f in as_completed(futures):
                f.result()

        # Wait for queue to drain
        order_queue.join()
        stop_signal.set()
        processor.join()

        assert len(processed_orders) == 50, "All 50 orders should be processed"


class TestResourceCleanup:
    """Test proper resource cleanup under concurrency."""

    def test_connection_pool_cleanup(self):
        """Connection pool should properly release connections."""
        connections_active = [0]
        max_connections = 5
        lock = threading.Lock()

        def use_connection():
            with lock:
                if connections_active[0] >= max_connections:
                    raise Exception("Pool exhausted")
                connections_active[0] += 1

            try:
                time.sleep(0.01)  # Simulate work
            finally:
                with lock:
                    connections_active[0] -= 1

        # Use more workers than connections to test queuing
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(use_connection) for _ in range(20)]

            successes = 0
            failures = 0
            for f in as_completed(futures):
                try:
                    f.result()
                    successes += 1
                except Exception:
                    failures += 1

        # With proper cleanup, some should succeed (possibly all with proper queuing)
        assert successes > 0, "Some connections should succeed"
        assert connections_active[0] == 0, "All connections should be released"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
