"""Tests for Deep Agent Observability module."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from src.observability.langsmith_tracer import (
    CostMetrics,
    EvaluationDataset,
    LangSmithTracer,
    Trace,
    TraceSpan,
    TraceType,
    traceable_decision,
)
from src.observability.trade_evaluator import (
    DecisionOutcome,
    DecisionQuality,
    TradeDecisionRecord,
    TradeEvaluator,
)


class TestCostMetrics:
    """Test cost calculation for different models."""

    def test_gpt4o_cost_calculation(self):
        """Test GPT-4o pricing."""
        cost = CostMetrics(input_tokens=1000, output_tokens=500, model="gpt-4o")
        result = cost.calculate_cost()

        # GPT-4o: $2.50/1M input, $10/1M output
        expected = (1000 / 1000 * 0.0025) + (500 / 1000 * 0.01)
        assert abs(result - expected) < 0.0001

    def test_claude_haiku_cost_calculation(self):
        """Test Claude Haiku pricing."""
        cost = CostMetrics(input_tokens=2000, output_tokens=1000, model="claude-3-haiku")
        result = cost.calculate_cost()

        # Haiku: $0.25/1M input, $1.25/1M output
        expected = (2000 / 1000 * 0.00025) + (1000 / 1000 * 0.00125)
        assert abs(result - expected) < 0.0001

    def test_unknown_model_uses_default(self):
        """Test fallback to default pricing."""
        cost = CostMetrics(input_tokens=1000, output_tokens=1000, model="unknown-model")
        result = cost.calculate_cost()

        # Default: $1/1M input, $2/1M output
        expected = (1000 / 1000 * 0.001) + (1000 / 1000 * 0.002)
        assert abs(result - expected) < 0.0001


class TestTraceSpan:
    """Test trace span functionality."""

    def test_span_creation(self):
        """Test creating a span."""
        span = TraceSpan(name="test_span", trace_type=TraceType.DECISION)

        assert span.name == "test_span"
        assert span.trace_type == TraceType.DECISION
        assert span.status == "running"
        assert span.span_id is not None

    def test_span_completion(self):
        """Test completing a span."""
        span = TraceSpan(name="test_span")
        span.complete(outputs={"result": "success"})

        assert span.status == "success"
        assert span.end_time is not None
        assert span.duration_ms > 0
        assert span.outputs["result"] == "success"

    def test_span_error(self):
        """Test span with error."""
        span = TraceSpan(name="test_span")
        span.complete(error="Something went wrong")

        assert span.status == "error"
        assert span.error == "Something went wrong"

    def test_span_metadata(self):
        """Test adding metadata to span."""
        span = TraceSpan(name="test_span")
        span.add_metadata({"symbol": "AAPL", "confidence": 0.85})

        assert span.metadata["symbol"] == "AAPL"
        assert span.metadata["confidence"] == 0.85

    def test_span_cost_tracking(self):
        """Test setting cost on span."""
        span = TraceSpan(name="test_span")
        span.set_cost(input_tokens=500, output_tokens=200, model="gpt-4o-mini")

        assert span.cost.input_tokens == 500
        assert span.cost.output_tokens == 200
        assert span.cost.estimated_cost_usd > 0

    def test_span_serialization(self):
        """Test span to_dict."""
        span = TraceSpan(name="test_span", trace_type=TraceType.TRADE)
        span.add_metadata({"symbol": "AAPL"})
        span.complete()

        data = span.to_dict()

        assert data["name"] == "test_span"
        assert data["trace_type"] == "trade"
        assert data["metadata"]["symbol"] == "AAPL"
        assert data["status"] == "success"


class TestTrace:
    """Test trace functionality."""

    def test_trace_creation(self):
        """Test creating a trace."""
        trace = Trace(name="trading_session")

        assert trace.name == "trading_session"
        assert trace.trace_id is not None
        assert len(trace.spans) == 0

    def test_trace_with_spans(self):
        """Test trace with multiple spans."""
        trace = Trace(name="trading_session")

        span1 = TraceSpan(name="analysis", trace_type=TraceType.ANALYSIS)
        span1.set_cost(100, 50, "gpt-4o-mini")
        span1.complete()

        span2 = TraceSpan(name="decision", trace_type=TraceType.DECISION, parent_id=span1.span_id)
        span2.set_cost(200, 100, "gpt-4o-mini")
        span2.complete()

        trace.add_span(span1)
        trace.add_span(span2)
        trace.complete()

        assert len(trace.spans) == 2
        assert trace.total_duration_ms > 0
        assert trace.total_cost_usd > 0
        assert trace.total_tokens == 450  # 100+50+200+100


class TestLangSmithTracer:
    """Test LangSmith tracer."""

    def test_tracer_initialization(self):
        """Test tracer initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = LangSmithTracer(
                project_name="test-project",
                storage_path=Path(tmpdir),
            )

            assert tracer.project_name == "test-project"
            assert tracer.storage_path == Path(tmpdir)

    def test_trace_context_manager(self):
        """Test trace context manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = LangSmithTracer(storage_path=Path(tmpdir))

            with tracer.trace("test_operation", trace_type=TraceType.ANALYSIS) as span:
                span.add_metadata({"key": "value"})
                span.add_output("result", "done")

            # Check trace was saved
            trace_files = list(Path(tmpdir).glob("traces_*.jsonl"))
            assert len(trace_files) == 1

            # Verify content
            with open(trace_files[0]) as f:
                trace_data = json.loads(f.readline())
                assert len(trace_data["spans"]) == 1
                assert trace_data["spans"][0]["name"] == "test_operation"

    def test_nested_traces(self):
        """Test nested trace spans."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = LangSmithTracer(storage_path=Path(tmpdir))

            with tracer.trace("outer", trace_type=TraceType.DECISION) as outer:
                outer.add_metadata({"level": "outer"})

                with tracer.trace("inner", trace_type=TraceType.ANALYSIS) as inner:
                    inner.add_metadata({"level": "inner"})

            # Check trace was saved with both spans
            trace_files = list(Path(tmpdir).glob("traces_*.jsonl"))
            with open(trace_files[0]) as f:
                trace_data = json.loads(f.readline())
                assert len(trace_data["spans"]) == 2

                # Inner span should have outer as parent
                inner_span = [s for s in trace_data["spans"] if s["name"] == "inner"][0]
                outer_span = [s for s in trace_data["spans"] if s["name"] == "outer"][0]
                assert inner_span["parent_id"] == outer_span["span_id"]

    def test_daily_cost_tracking(self):
        """Test daily cost accumulation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = LangSmithTracer(storage_path=Path(tmpdir))

            # Create trace with cost
            with tracer.trace("expensive_op") as span:
                span.set_cost(10000, 5000, "gpt-4o")

            daily_cost = tracer.get_daily_cost()
            assert daily_cost > 0


class TestEvaluationDataset:
    """Test evaluation dataset."""

    def test_add_example(self):
        """Test adding evaluation examples."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset = EvaluationDataset(name="test", storage_path=Path(tmpdir))

            dataset.add_example(
                inputs={"symbol": "AAPL", "price": 50000},
                expected_output="BUY",
                actual_output="BUY",
            )

            dataset.add_example(
                inputs={"symbol": "AAPL", "price": 3000},
                expected_output="SELL",
                actual_output="HOLD",
            )

            accuracy = dataset.get_accuracy()
            assert accuracy == 0.5  # 1 match out of 2

    def test_get_examples(self):
        """Test retrieving examples."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset = EvaluationDataset(name="test", storage_path=Path(tmpdir))

            for i in range(5):
                dataset.add_example(
                    inputs={"i": i},
                    expected_output=i,
                    actual_output=i,
                )

            examples = dataset.get_examples(limit=3)
            assert len(examples) == 3


class TestTradeEvaluator:
    """Test trade decision evaluator."""

    def test_record_decision(self):
        """Test recording a trade decision."""
        with tempfile.TemporaryDirectory() as tmpdir:
            evaluator = TradeEvaluator(storage_path=Path(tmpdir))

            record_id = evaluator.record_decision(
                symbol="AAPL",
                decision="BUY",
                confidence=0.85,
                reasoning="Strong momentum signal",
                price=50000.0,
                momentum_score=0.8,
            )

            assert record_id is not None
            assert record_id in evaluator._pending

    def test_record_outcome(self):
        """Test recording trade outcome."""
        with tempfile.TemporaryDirectory() as tmpdir:
            evaluator = TradeEvaluator(storage_path=Path(tmpdir))

            # Record decision
            record_id = evaluator.record_decision(
                symbol="AAPL",
                decision="BUY",
                confidence=0.85,
                reasoning="Strong momentum signal",
                price=50000.0,
            )

            # Record outcome (profitable)
            record = evaluator.record_outcome(
                record_id=record_id,
                exit_price=52500.0,  # +5%
            )

            assert record is not None
            assert record.outcome == DecisionOutcome.PROFITABLE
            assert record.profit_pct == pytest.approx(5.0, rel=0.01)
            assert record.quality == DecisionQuality.EXCELLENT

    def test_loss_outcome(self):
        """Test loss outcome classification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            evaluator = TradeEvaluator(storage_path=Path(tmpdir))

            record_id = evaluator.record_decision(
                symbol="AAPL",
                decision="BUY",
                confidence=0.9,
                reasoning="Expected breakout",
                price=50000.0,
            )

            record = evaluator.record_outcome(
                record_id=record_id,
                exit_price=47500.0,  # -5%
            )

            assert record.outcome == DecisionOutcome.LOSS
            assert record.quality == DecisionQuality.POOR

    def test_metrics_calculation(self):
        """Test metrics aggregation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            evaluator = TradeEvaluator(storage_path=Path(tmpdir))

            # Record multiple decisions
            for i in range(5):
                record_id = evaluator.record_decision(
                    symbol="AAPL",
                    decision="BUY",
                    confidence=0.7,
                    reasoning="Test",
                    price=50000.0,
                )
                # 3 wins, 2 losses
                profit = 2.5 if i < 3 else -1.5
                evaluator.record_outcome(
                    record_id=record_id,
                    exit_price=50000 * (1 + profit / 100),
                )

            metrics = evaluator.get_metrics(days=1)

            assert metrics.total_decisions == 5
            assert metrics.resolved_decisions == 5
            assert metrics.profitable_count == 3
            assert metrics.loss_count == 2
            assert metrics.win_rate == pytest.approx(0.6, rel=0.01)


class TestTraceableDecorator:
    """Test traceable decorator."""

    def test_sync_function_tracing(self):
        """Test tracing a sync function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Reset global tracer
            import src.observability.langsmith_tracer as tracer_module

            tracer_module._tracer = LangSmithTracer(storage_path=Path(tmpdir))

            @traceable_decision(name="test_decision")
            def make_decision(symbol: str, price: float) -> str:
                return "BUY"

            result = make_decision(50000.0)

            assert result == "BUY"

            # Check trace was created
            trace_files = list(Path(tmpdir).glob("traces_*.jsonl"))
            assert len(trace_files) == 1

    @pytest.mark.asyncio
    async def test_async_function_tracing(self):
        """Test tracing an async function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.langsmith_tracer as tracer_module

            tracer_module._tracer = LangSmithTracer(storage_path=Path(tmpdir))

            @traceable_decision(name="async_decision")
            async def async_make_decision(symbol: str) -> str:
                return "SELL"

            result = await async_make_decision()

            assert result == "SELL"


class TestTraceDecisionRecord:
    """Test TradeDecisionRecord dataclass."""

    def test_serialization_roundtrip(self):
        """Test serialization and deserialization."""
        record = TradeDecisionRecord(
            record_id="abc123",
            timestamp=datetime.now(timezone.utc),
            symbol="AAPL",
            decision="BUY",
            confidence=0.85,
            reasoning="Strong momentum",
            price_at_decision=50000.0,
            momentum_score=0.8,
            sentiment_score=0.7,
            regime="bullish",
        )

        # Serialize
        data = record.to_dict()

        # Deserialize
        restored = TradeDecisionRecord.from_dict(data)

        assert restored.record_id == record.record_id
        assert restored.symbol == record.symbol
        assert restored.decision == record.decision
        assert restored.confidence == record.confidence


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
