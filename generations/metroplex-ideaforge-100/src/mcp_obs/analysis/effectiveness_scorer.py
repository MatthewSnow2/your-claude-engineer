"""Tool effectiveness scoring engine for MCP observability layer."""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict

from ..storage.database import Database
from ..storage.models import ToolEffectivenessMetric, ToolCallStatus

logger = logging.getLogger(__name__)


class EffectivenessScorer:
    """Analyzes tool call patterns to generate effectiveness scores."""

    def __init__(self, database: Database):
        """
        Initialize the effectiveness scorer.

        Args:
            database: Database instance for querying tool call data
        """
        self.db = database

    async def calculate_tool_score(
        self, tool_name: str, window_hours: int = 24
    ) -> Optional[ToolEffectivenessMetric]:
        """
        Calculate effectiveness score (0-100) for a specific tool.

        Scoring factors:
        - Success rate (40% weight)
        - Average execution time vs baseline (20% weight)
        - Retry rate / retry patterns (20% weight)
        - Error diversity (10% weight) - many different errors = worse
        - Recent trend (10% weight) - improving or degrading

        Args:
            tool_name: Name of the tool to score
            window_hours: Time window in hours for analysis (default: 24)

        Returns:
            ToolEffectivenessMetric or None if no data found
        """
        if not self.db._connection:
            logger.error("Database connection not initialized")
            return None

        stats = await self.db.get_tool_call_stats(tool_name, window_hours)
        if not stats or stats["total_calls"] == 0:
            logger.warning(f"No tool calls found for {tool_name} in last {window_hours} hours")
            return None

        # Calculate individual score components
        success_score = self._calculate_success_score(stats)
        performance_score = self._calculate_performance_score(stats)
        retry_score = self._calculate_retry_score(stats)
        error_diversity_score = await self._calculate_error_diversity_score(tool_name, window_hours)
        trend_score = await self._calculate_trend_score(tool_name, window_hours)

        # Weighted combination
        effectiveness_score = (
            success_score * 0.40
            + performance_score * 0.20
            + retry_score * 0.20
            + error_diversity_score * 0.10
            + trend_score * 0.10
        )

        # Detect failure patterns
        failure_patterns = await self._detect_failure_patterns(tool_name, window_hours)

        # Generate improvement suggestions
        improvement_suggestions = self._generate_improvement_suggestions(
            effectiveness_score, stats, failure_patterns
        )

        # Determine trend
        trend = await self._determine_trend(tool_name, window_hours)

        return ToolEffectivenessMetric(
            tool_name=tool_name,
            measurement_window_hours=window_hours,
            total_calls=stats["total_calls"],
            success_count=stats["success_count"],
            failure_count=stats["failure_count"],
            timeout_count=stats["timeout_count"],
            retry_count=stats["retry_count"],
            average_execution_ms=stats["avg_execution_time"],
            effectiveness_score=round(effectiveness_score, 2),
            failure_patterns=failure_patterns,
            improvement_suggestions=improvement_suggestions,
            trend=trend,
        )

    async def get_all_tool_scores(
        self, window_hours: int = 24
    ) -> List[ToolEffectivenessMetric]:
        """
        Get effectiveness scores for all tools.

        Args:
            window_hours: Time window in hours for analysis

        Returns:
            List of ToolEffectivenessMetric for all tools
        """
        if not self.db._connection:
            logger.error("Database connection not initialized")
            return []

        tool_names = await self.db.get_unique_tools()
        scores = []

        for tool_name in tool_names:
            score = await self.calculate_tool_score(tool_name, window_hours)
            if score:
                scores.append(score)

        # Sort by effectiveness score (descending)
        scores.sort(key=lambda x: x.effectiveness_score, reverse=True)
        return scores

    async def detect_retry_patterns(self, tool_name: str) -> List[Dict[str, Any]]:
        """
        Detect retry patterns for a tool.

        Args:
            tool_name: Name of the tool to analyze

        Returns:
            List of retry pattern dictionaries
        """
        if not self.db._connection:
            logger.error("Database connection not initialized")
            return []

        retry_sequences = await self.db.get_retry_sequences(tool_name)

        patterns = []
        for sequence in retry_sequences:
            patterns.append({
                "session_id": sequence["session_id"],
                "sequence_length": sequence["sequence_length"],
                "time_span_seconds": sequence["time_span_seconds"],
                "eventual_success": sequence["eventual_success"],
            })

        return patterns

    async def generate_recommendations(self) -> List[Dict[str, Any]]:
        """
        Generate improvement recommendations for low-scoring tools.

        Returns:
            List of recommendation dictionaries categorized by severity
        """
        scores = await self.get_all_tool_scores(window_hours=24)

        recommendations = []

        for score in scores:
            if score.effectiveness_score < 50:
                # Critical: Low-scoring tools
                recommendations.append({
                    "severity": "critical",
                    "tool_name": score.tool_name,
                    "score": score.effectiveness_score,
                    "category": "replace",
                    "message": f"Tool '{score.tool_name}' has critically low effectiveness ({score.effectiveness_score:.1f}%). Consider replacing with alternative.",
                    "suggestions": score.improvement_suggestions,
                    "failure_patterns": score.failure_patterns,
                })
            elif score.effectiveness_score < 70:
                # Warning: Medium-scoring tools
                recommendations.append({
                    "severity": "warning",
                    "tool_name": score.tool_name,
                    "score": score.effectiveness_score,
                    "category": "optimize",
                    "message": f"Tool '{score.tool_name}' has moderate effectiveness ({score.effectiveness_score:.1f}%). Consider optimizations.",
                    "suggestions": score.improvement_suggestions,
                    "failure_patterns": score.failure_patterns,
                })
            elif score.effectiveness_score >= 70 and score.trend == "degrading":
                # Info: Degrading tools
                recommendations.append({
                    "severity": "info",
                    "tool_name": score.tool_name,
                    "score": score.effectiveness_score,
                    "category": "monitor",
                    "message": f"Tool '{score.tool_name}' is degrading ({score.effectiveness_score:.1f}%). Monitor for further decline.",
                    "suggestions": score.improvement_suggestions,
                    "failure_patterns": score.failure_patterns,
                })

        return recommendations

    async def get_effectiveness_trends(
        self, tool_name: str, periods: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get effectiveness trend data over time periods.

        Args:
            tool_name: Name of the tool to analyze
            periods: Number of time periods to analyze (default: 7)

        Returns:
            List of trend data dictionaries
        """
        if not self.db._connection:
            logger.error("Database connection not initialized")
            return []

        trends = []

        # Analyze each 24-hour period
        for i in range(periods):
            # Calculate the time window for this period
            end_offset = i * 24
            start_offset = (i + 1) * 24

            # Get stats for this period
            start_time = datetime.utcnow() - timedelta(hours=start_offset)
            end_time = datetime.utcnow() - timedelta(hours=end_offset)

            tool_calls = await self.db.get_tool_calls_by_tool(
                tool_name, start_time, end_time
            )

            if not tool_calls:
                continue

            success_count = sum(1 for tc in tool_calls if tc.status == ToolCallStatus.SUCCESS)
            total_calls = len(tool_calls)
            success_rate = (success_count / total_calls * 100) if total_calls > 0 else 0

            avg_exec_time = sum(tc.execution_time_ms for tc in tool_calls) / total_calls if total_calls > 0 else 0

            trends.append({
                "period": f"{start_offset}-{end_offset}h ago",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "total_calls": total_calls,
                "success_rate": success_rate,
                "avg_execution_time_ms": avg_exec_time,
            })

        return trends

    # Private helper methods

    def _calculate_success_score(self, stats: Dict[str, Any]) -> float:
        """Calculate success rate score (0-100)."""
        if stats["total_calls"] == 0:
            return 0.0

        success_rate = (stats["success_count"] / stats["total_calls"]) * 100
        return success_rate

    def _calculate_performance_score(self, stats: Dict[str, Any]) -> float:
        """
        Calculate performance score based on execution time.

        Baseline: < 100ms = 100, 100-500ms = 80, 500-1000ms = 60, > 1000ms = 40
        """
        avg_time = stats["avg_execution_time"]

        if avg_time < 100:
            return 100.0
        elif avg_time < 500:
            return 80.0
        elif avg_time < 1000:
            return 60.0
        else:
            # Exponential decay after 1000ms
            return max(40.0 - ((avg_time - 1000) / 100), 0.0)

    def _calculate_retry_score(self, stats: Dict[str, Any]) -> float:
        """
        Calculate retry score.

        Low retry rate = high score, high retry rate = low score
        """
        if stats["total_calls"] == 0:
            return 100.0

        retry_rate = (stats["retry_count"] / stats["total_calls"]) * 100

        # Retry rate > 20% is concerning
        if retry_rate < 5:
            return 100.0
        elif retry_rate < 10:
            return 80.0
        elif retry_rate < 20:
            return 60.0
        else:
            return max(40.0 - (retry_rate - 20), 0.0)

    async def _calculate_error_diversity_score(
        self, tool_name: str, window_hours: int
    ) -> float:
        """
        Calculate error diversity score.

        Few unique errors = high score, many unique errors = low score
        """
        start_time = datetime.utcnow() - timedelta(hours=window_hours)
        tool_calls = await self.db.get_tool_calls_by_tool(
            tool_name, start_time, datetime.utcnow()
        )

        # Get unique error messages
        error_messages = set()
        for tc in tool_calls:
            if tc.status in [ToolCallStatus.FAILURE, ToolCallStatus.TIMEOUT] and tc.error_message:
                error_messages.add(tc.error_message)

        unique_errors = len(error_messages)

        # Fewer unique errors is better (indicates consistent, fixable issue)
        if unique_errors == 0:
            return 100.0
        elif unique_errors <= 2:
            return 80.0
        elif unique_errors <= 5:
            return 60.0
        else:
            return max(40.0 - (unique_errors - 5) * 5, 0.0)

    async def _calculate_trend_score(
        self, tool_name: str, window_hours: int
    ) -> float:
        """
        Calculate trend score based on recent performance vs older performance.

        Improving = 100, stable = 75, degrading = 50
        """
        # Split window in half
        half_window = window_hours // 2

        now = datetime.utcnow()
        mid_point = now - timedelta(hours=half_window)
        start_point = now - timedelta(hours=window_hours)

        # Get recent calls (last half)
        recent_calls = await self.db.get_tool_calls_by_tool(tool_name, mid_point, now)

        # Get older calls (first half)
        older_calls = await self.db.get_tool_calls_by_tool(tool_name, start_point, mid_point)

        if not recent_calls or not older_calls:
            return 75.0  # Neutral if not enough data

        recent_success_rate = sum(1 for tc in recent_calls if tc.status == ToolCallStatus.SUCCESS) / len(recent_calls) * 100
        older_success_rate = sum(1 for tc in older_calls if tc.status == ToolCallStatus.SUCCESS) / len(older_calls) * 100

        diff = recent_success_rate - older_success_rate

        if diff > 10:
            return 100.0  # Improving
        elif diff < -10:
            return 50.0  # Degrading
        else:
            return 75.0  # Stable

    async def _detect_failure_patterns(
        self, tool_name: str, window_hours: int
    ) -> List[str]:
        """Detect common failure patterns."""
        start_time = datetime.utcnow() - timedelta(hours=window_hours)
        tool_calls = await self.db.get_tool_calls_by_tool(
            tool_name, start_time, datetime.utcnow()
        )

        error_counts = defaultdict(int)

        for tc in tool_calls:
            if tc.status in [ToolCallStatus.FAILURE, ToolCallStatus.TIMEOUT]:
                if tc.error_message:
                    # Categorize error messages
                    error_key = self._categorize_error(tc.error_message)
                    error_counts[error_key] += 1

        # Return top 5 most common error patterns
        sorted_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)
        return [f"{error} ({count} occurrences)" for error, count in sorted_errors[:5]]

    def _categorize_error(self, error_message: str) -> str:
        """Categorize error message into pattern."""
        error_lower = error_message.lower()

        if "timeout" in error_lower:
            return "Timeout"
        elif "connection" in error_lower or "network" in error_lower:
            return "Network/Connection"
        elif "permission" in error_lower or "access" in error_lower:
            return "Permission/Access"
        elif "not found" in error_lower or "404" in error_lower:
            return "Resource Not Found"
        elif "invalid" in error_lower or "validation" in error_lower:
            return "Invalid Input/Validation"
        elif "rate limit" in error_lower or "quota" in error_lower:
            return "Rate Limit/Quota"
        else:
            # Truncate long error messages
            return error_message[:50] + ("..." if len(error_message) > 50 else "")

    def _generate_improvement_suggestions(
        self, score: float, stats: Dict[str, Any], failure_patterns: List[str]
    ) -> List[str]:
        """Generate improvement suggestions based on metrics."""
        suggestions = []

        # Success rate suggestions
        if stats["total_calls"] > 0:
            success_rate = (stats["success_count"] / stats["total_calls"]) * 100
            if success_rate < 50:
                suggestions.append("Critical: Success rate is very low. Review tool implementation and error handling.")
            elif success_rate < 70:
                suggestions.append("Improve error handling and input validation to increase success rate.")

        # Performance suggestions
        if stats["avg_execution_time"] > 1000:
            suggestions.append(f"High average execution time ({stats['avg_execution_time']:.0f}ms). Consider caching or optimization.")

        # Retry suggestions
        if stats["total_calls"] > 0:
            retry_rate = (stats["retry_count"] / stats["total_calls"]) * 100
            if retry_rate > 20:
                suggestions.append("High retry rate indicates unstable execution. Investigate root cause of failures.")

        # Timeout suggestions
        if stats["timeout_count"] > stats["total_calls"] * 0.1:
            suggestions.append("Frequent timeouts detected. Consider increasing timeout threshold or optimizing tool.")

        # Failure pattern suggestions
        if failure_patterns:
            suggestions.append(f"Address common failure patterns: {', '.join(failure_patterns[:3])}")

        if not suggestions:
            suggestions.append("Tool is performing well. Continue monitoring for any degradation.")

        return suggestions

    async def _determine_trend(self, tool_name: str, window_hours: int) -> str:
        """Determine if tool effectiveness is improving, stable, or degrading."""
        # Split window in half
        half_window = window_hours // 2

        now = datetime.utcnow()
        mid_point = now - timedelta(hours=half_window)
        start_point = now - timedelta(hours=window_hours)

        # Get recent calls (last half)
        recent_calls = await self.db.get_tool_calls_by_tool(tool_name, mid_point, now)

        # Get older calls (first half)
        older_calls = await self.db.get_tool_calls_by_tool(tool_name, start_point, mid_point)

        if not recent_calls or not older_calls:
            return "stable"

        recent_success_rate = sum(1 for tc in recent_calls if tc.status == ToolCallStatus.SUCCESS) / len(recent_calls) * 100
        older_success_rate = sum(1 for tc in older_calls if tc.status == ToolCallStatus.SUCCESS) / len(older_calls) * 100

        diff = recent_success_rate - older_success_rate

        if diff > 10:
            return "improving"
        elif diff < -10:
            return "degrading"
        else:
            return "stable"
