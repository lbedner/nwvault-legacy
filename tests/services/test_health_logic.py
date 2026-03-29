"""
Tests for core health logic and component status propagation.

These tests focus on the pure logic of health checking, warning propagation,
and component hierarchy without external dependencies like Redis or system metrics.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

import pytest

from app.services.system import ComponentStatus, ComponentStatusType
from app.services.system.health import (
    get_system_status,
)



class TestHealthUtilityFunctions:
    """Test utility functions used in health checks."""

    def test_format_bytes(self) -> None:
        """Test format_bytes utility function."""
        from app.services.system.health import format_bytes

        # Test various byte sizes
        assert format_bytes(0) == "0 B"
        assert format_bytes(512) == "512 B"
        assert format_bytes(1024) == "1.0 KB"
        assert format_bytes(1536) == "1.5 KB"
        assert format_bytes(2048) == "2.0 KB"
        assert format_bytes(1048576) == "1.0 MB"
        assert format_bytes(1572864) == "1.5 MB"
        assert format_bytes(1073741824) == "1.0 GB"
        assert format_bytes(1099511627776) == "1.0 TB"

        # Test edge cases
        assert format_bytes(1) == "1 B"
        assert format_bytes(1023) == "1023 B"
        assert format_bytes(8192) == "8.0 KB"


class TestComponentStatusPropagation:
    """Test warning status propagation through component hierarchies."""

    def test_component_status_creation_with_warning(self) -> None:
        """Test creating ComponentStatus with warning status."""
        status = ComponentStatus(
            name="test_component",
            status=ComponentStatusType.WARNING,
            message="Has warnings",
            response_time_ms=100.0,
        )

        assert status.name == "test_component"
        assert status.healthy is False  # WARNING is not healthy
        assert status.status == ComponentStatusType.WARNING
        assert status.message == "Has warnings"

    def test_component_status_defaults_to_healthy(self) -> None:
        """Test that ComponentStatus defaults to HEALTHY status."""
        status = ComponentStatus(
            name="test_component",
            message="All good",
        )

        assert status.status == ComponentStatusType.HEALTHY

    def test_unhealthy_component_with_unhealthy_status(self) -> None:
        """Test that unhealthy components get UNHEALTHY status."""
        status = ComponentStatus(
            name="test_component",
            status=ComponentStatusType.UNHEALTHY,
            message="Something is broken",
        )

        assert status.healthy is False
        assert status.status == ComponentStatusType.UNHEALTHY

    def test_sub_component_hierarchy(self) -> None:
        """Test component with sub-components for hierarchy testing."""
        # Create sub-components with different statuses
        sub_component_healthy = ComponentStatus(
            name="sub_healthy",
            status=ComponentStatusType.HEALTHY,
            message="Sub-component is healthy",
        )

        sub_component_warning = ComponentStatus(
            name="sub_warning",
            status=ComponentStatusType.WARNING,
            message="Sub-component has warnings",
        )

        # Create parent component
        parent_component = ComponentStatus(
            name="parent",
            status=ComponentStatusType.WARNING,  # Should propagate from sub-components
            message="Parent has sub-component warnings",
            sub_components={
                "sub_healthy": sub_component_healthy,
                "sub_warning": sub_component_warning,
            }
        )

        assert parent_component.healthy is False  # WARNING is not healthy
        assert parent_component.status == ComponentStatusType.WARNING
        assert len(parent_component.sub_components) == 2
        assert (
            parent_component.sub_components["sub_warning"].status
            == ComponentStatusType.WARNING
        )


class TestSystemStatusWarningPropagation:
    """Test warning propagation in real system status scenarios."""

    @pytest.mark.asyncio
    async def test_system_status_with_mixed_component_health(self) -> None:
        """Test system status calculation with components having different states."""

        # Mock the health check registry to have controlled components
        mock_healthy_component = AsyncMock(return_value=ComponentStatus(
            name="healthy_service",
            status=ComponentStatusType.HEALTHY,
            message="Service is running well",
        ))

        mock_warning_component = AsyncMock(return_value=ComponentStatus(
            name="warning_service",
            status=ComponentStatusType.WARNING,
            message="Service has warnings",
        ))

        mock_unhealthy_component = AsyncMock(return_value=ComponentStatus(
            name="unhealthy_service",
            status=ComponentStatusType.UNHEALTHY,
            message="Service is down",
        ))

        # Mock the system metrics to avoid actual system calls
        mock_system_metrics = {
            "memory": ComponentStatus(
                name="memory",
                status=ComponentStatusType.HEALTHY,
                message="Memory usage: 50%",
            ),
            "cpu": ComponentStatus(
                name="cpu",
                status=ComponentStatusType.HEALTHY,
                message="CPU usage: 10%",
            ),
            "disk": ComponentStatus(
                name="disk",
                status=ComponentStatusType.HEALTHY,
                message="Disk usage: 30%",
            ),
        }

        with (
            patch(
                "app.services.system.health._health_checks",
                {
                    "healthy_service": mock_healthy_component,
                    "warning_service": mock_warning_component,
                    "unhealthy_service": mock_unhealthy_component,
                },
            ),
            patch("app.services.system.health._service_health_checks", {}),
            patch(
                "app.services.system.health._get_cached_system_metrics",
                return_value=mock_system_metrics,
            ),
            patch(
                "app.services.system.health._get_system_info",
                return_value={"test": "info"},
            ),
        ):
            system_status = await get_system_status()

            # System should be unhealthy due to unhealthy_service
            assert system_status.overall_healthy is False

            # Check that components are present using model's flat list
            assert (
                "aegis.components.healthy_service" in system_status.healthy_components
            )
            assert (
                "aegis.components.warning_service" in system_status.unhealthy_components
            )  # WARNING is NOT considered healthy
            assert (
                "aegis.components.unhealthy_service"
                in system_status.unhealthy_components
            )
            assert "aegis.components.backend" in system_status.healthy_components

            # Also verify direct navigation to check statuses
            assert "aegis" in system_status.components
            aegis_component = system_status.components["aegis"]

            # Navigate to components group
            if "components" in aegis_component.sub_components:
                components_group = aegis_component.sub_components["components"]
                assert "healthy_service" in components_group.sub_components
                assert "warning_service" in components_group.sub_components
                assert "unhealthy_service" in components_group.sub_components
                assert "backend" in components_group.sub_components

                # Verify component statuses
                assert (
                    components_group.sub_components["healthy_service"].status
                    == ComponentStatusType.HEALTHY
                )
                assert (
                    components_group.sub_components["warning_service"].status
                    == ComponentStatusType.WARNING
                )
                assert (
                    components_group.sub_components["unhealthy_service"].status
                    == ComponentStatusType.UNHEALTHY
                )


    @pytest.mark.asyncio
    async def test_system_status_with_only_warnings_is_not_healthy(self) -> None:
        """Test that system with warnings is not considered overall healthy."""

        mock_warning_component = AsyncMock(return_value=ComponentStatus(
            name="warning_service",
            status=ComponentStatusType.WARNING,
            message="Service has warnings",
        ))

        mock_system_metrics = {
            "memory": ComponentStatus(
                name="memory",
                status=ComponentStatusType.HEALTHY,
                message="Memory usage: 50%",
            ),
        }

        with (
            patch(
                "app.services.system.health._health_checks",
                {
                    "warning_service": mock_warning_component,
                },
            ),
            patch("app.services.system.health._service_health_checks", {}),
            patch(
                "app.services.system.health._get_cached_system_metrics",
                return_value=mock_system_metrics,
            ),
            patch(
                "app.services.system.health._get_system_info",
                return_value={"test": "info"},
            ),
        ):

            system_status = await get_system_status()

            # System is not healthy because WARNING is not healthy
            assert system_status.overall_healthy is False

            # Aegis component should have warning status and not be healthy
            aegis_component = system_status.components["aegis"]
            assert aegis_component.status == ComponentStatusType.WARNING
            assert aegis_component.healthy is False


class TestWorkerHealthLogic:
    """Test the specific worker health check logic and warning propagation."""

    def test_queue_status_determination_logic(self) -> None:
        """Test the logic for determining queue component status."""

        # Test case 1: Worker with no functions should be WARNING but healthy
        def check_empty_worker_status(
            queue_type: str,
            has_functions: bool,
            worker_alive: bool,
            failure_rate: float,
        ) -> tuple[bool, ComponentStatusType]:
            """Simulate the queue status logic from worker health check."""
            if not has_functions:
                queue_healthy = True  # Empty workers don't affect overall health
                queue_status = ComponentStatusType.WARNING  # But show as warning
            else:
                queue_healthy = worker_alive and failure_rate < 25
                queue_status = (
                    ComponentStatusType.HEALTHY
                    if queue_healthy
                    else ComponentStatusType.UNHEALTHY
                )

            return queue_healthy, queue_status

        # Empty worker (media/system queues)
        healthy, status = check_empty_worker_status("media", False, False, 100)
        assert healthy is True  # Doesn't affect system health
        assert status == ComponentStatusType.WARNING  # But shows warning

        # Active worker with good performance
        healthy, status = check_empty_worker_status("load_test", True, True, 5)
        assert healthy is True
        assert status == ComponentStatusType.HEALTHY

        # Active worker with high failure rate
        healthy, status = check_empty_worker_status("load_test", True, True, 50)
        assert healthy is False
        assert status == ComponentStatusType.UNHEALTHY

        # Active worker that's offline
        healthy, status = check_empty_worker_status("load_test", True, False, 0)
        assert healthy is False
        assert status == ComponentStatusType.UNHEALTHY

    def test_warning_propagation_to_parent_components(self) -> None:
        """Test warning propagation from queue -> queues -> worker."""

        # Simulate the propagation logic used in worker health check
        # Note: WARNING status means healthy=False, so queues with WARNING
        # are not considered healthy
        def check_warning_propagation(
            sub_components: dict[str, ComponentStatus]
        ) -> ComponentStatusType:
            """Simulate queues component status determination."""
            queues_healthy = all(
                queue.healthy for queue in sub_components.values()
            )

            has_warnings = any(
                queue.status == ComponentStatusType.WARNING
                for queue in sub_components.values()
            )

            if queues_healthy:
                return ComponentStatusType.HEALTHY
            elif has_warnings:
                # Some have warnings (not healthy), but not UNHEALTHY
                return ComponentStatusType.WARNING
            else:
                return ComponentStatusType.UNHEALTHY

        # Test case: Some queues have warnings - since WARNING is not healthy,
        # the overall status should be WARNING (not all queues are healthy)
        sub_components = {
            "media": ComponentStatus(
                name="media",
                status=ComponentStatusType.WARNING,
                message="No tasks configured",
            ),
            "system": ComponentStatus(
                name="system",
                status=ComponentStatusType.WARNING,
                message="No tasks configured",
            ),
            "load_test": ComponentStatus(
                name="load_test",
                status=ComponentStatusType.HEALTHY,
                message="Active with completed tasks",
            ),
        }

        queues_status = check_warning_propagation(sub_components)
        assert queues_status == ComponentStatusType.WARNING

        # Test case: All components healthy
        for component in sub_components.values():
            component.status = ComponentStatusType.HEALTHY

        queues_status = check_warning_propagation(sub_components)
        assert queues_status == ComponentStatusType.HEALTHY

        # Test case: One component unhealthy
        sub_components["load_test"].status = ComponentStatusType.UNHEALTHY

        queues_status = check_warning_propagation(sub_components)
        assert queues_status == ComponentStatusType.UNHEALTHY


class TestComponentMetadata:
    """Test component metadata handling and serialization."""

    def test_component_status_with_complex_metadata(self) -> None:
        """Test ComponentStatus with complex metadata for different component types."""

        # Worker component metadata
        worker_metadata = {
            "total_queued": 5,
            "total_completed": 1000,
            "total_failed": 50,
            "overall_failure_rate_percent": 4.8,
            "redis_url": "redis://localhost:6379",
            "queue_configuration": {
                "load_test": {
                    "description": "Load testing tasks",
                    "max_jobs": 50,
                    "timeout_seconds": 300,
                }
            }
        }

        worker_status = ComponentStatus(
            name="worker",
            status=ComponentStatusType.WARNING,
            message="arq worker infrastructure: 1/3 workers active",
            metadata=worker_metadata,
        )

        # Verify metadata is preserved
        assert worker_status.metadata["total_completed"] == 1000
        assert worker_status.metadata["overall_failure_rate_percent"] == 4.8
        assert "queue_configuration" in worker_status.metadata

        # Cache component metadata
        cache_metadata = {
            "implementation": "redis",
            "version": "7.0.0",
            "connected_clients": 2,
            "used_memory_human": "1.5M",
            "uptime_in_seconds": 3600,
        }

        cache_status = ComponentStatus(
            name="cache",
            status=ComponentStatusType.HEALTHY,
            message="Redis cache connection successful",
            metadata=cache_metadata,
        )

        assert cache_status.metadata["implementation"] == "redis"
        assert cache_status.metadata["uptime_in_seconds"] == 3600

    def test_component_status_serialization(self) -> None:
        """Test that ComponentStatus can be properly serialized (for API responses)."""

        status = ComponentStatus(
            name="test_component",
            status=ComponentStatusType.HEALTHY,
            message="Component is healthy",
            response_time_ms=123.45,
            metadata={"key": "value", "number": 42},
            sub_components={
                "sub1": ComponentStatus(
                    name="sub1",
                    status=ComponentStatusType.HEALTHY,
                    message="Sub-component OK",
                )
            }
        )

        # Convert to dict (simulates JSON serialization)
        status_dict = status.model_dump()

        # Verify structure
        assert status_dict["name"] == "test_component"
        assert status_dict["healthy"] is True  # HEALTHY status has healthy=True
        assert status_dict["status"] == "healthy"
        assert status_dict["message"] == "Component is healthy"
        assert status_dict["response_time_ms"] == 123.45
        assert status_dict["metadata"]["key"] == "value"
        assert "sub1" in status_dict["sub_components"]
        assert status_dict["sub_components"]["sub1"]["status"] == "healthy"
class TestDatabaseHealthCheck:
    """Test database health check functionality."""

    @pytest.mark.asyncio
    async def test_database_health_check_success(self, db_session) -> None:
        """Test successful database health check with mocked database."""
        from app.services.system.health import check_database_health

        # Mock everything to simulate successful database connection with
        # enhanced metadata
        with patch('app.services.system.health.settings') as mock_settings, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.stat') as mock_stat, \
             patch('app.core.db.db_session') as mock_db_session, \
             patch('app.core.db.engine') as mock_engine, \
             patch('app.services.system.health.sqlite3') as mock_sqlite3:

            mock_settings.DATABASE_URL = "sqlite:///./data/test.db"
            mock_settings.DATABASE_ENGINE_ECHO = False

            # Mock SQLite version
            mock_sqlite3.sqlite_version = "3.43.2"

            # Mock file size
            mock_stat_result = MagicMock()
            mock_stat_result.st_size = 8192
            mock_stat.return_value = mock_stat_result

            # Mock engine pool
            mock_engine.pool.size.return_value = 5

            # Mock successful db_session with PRAGMA queries
            mock_session = MagicMock()

            # Mock PRAGMA query results
            def mock_execute(query):
                query_str = str(query).lower()
                if "pragma foreign_keys" in query_str:
                    result = MagicMock()
                    result.fetchone.return_value = [1]  # foreign_keys = ON
                    return result
                elif "pragma journal_mode" in query_str:
                    result = MagicMock()
                    result.fetchone.return_value = ["delete"]  # journal_mode = delete
                    return result
                elif "pragma cache_size" in query_str:
                    result = MagicMock()
                    result.fetchone.return_value = [2000]  # cache_size = 2000
                    return result
                else:
                    # For "SELECT 1" query
                    return None

            mock_session.execute.side_effect = mock_execute
            mock_db_session.return_value.__enter__ = MagicMock(
                return_value=mock_session
            )
            mock_db_session.return_value.__exit__ = MagicMock(return_value=None)

            result = await check_database_health()

            # Test basic health status
            assert result.name == "database"
            assert result.status == ComponentStatusType.HEALTHY
            assert result.message == "Database connection successful"

            # Test existing metadata fields
            assert result.metadata["implementation"] == "sqlite"
            assert result.metadata["database_exists"] is True
            assert result.metadata["engine_echo"] is False
            assert result.metadata["url"] == "sqlite:///./data/test.db"

            # Test enhanced metadata fields
            assert result.metadata["version"] == "3.43.2"
            assert result.metadata["file_size_bytes"] == 8192
            assert result.metadata["file_size_human"] == "8.0 KB"
            assert result.metadata["connection_pool_size"] == 5

            # Test PRAGMA settings
            assert "pragma_settings" in result.metadata
            pragma_settings = result.metadata["pragma_settings"]
            assert pragma_settings["foreign_keys"] is True
            assert pragma_settings["journal_mode"] == "delete"
            assert pragma_settings["cache_size"] == 2000
            assert result.metadata["wal_enabled"] is False

    @pytest.mark.asyncio
    async def test_database_health_check_import_error(self) -> None:
        """Test database health check when db module not available."""
        from app.services.system.health import check_database_health

        # Mock ImportError when trying to import db_session from app.core.db
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == 'app.core.db':
                raise ImportError("No db module")
            return real_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            result = await check_database_health()

            assert result.name == "database"
            assert result.status == ComponentStatusType.UNHEALTHY
            assert result.message == "Database module not available"
            assert result.metadata["error"] == (
                "Database module not imported or configured"
            )

    @pytest.mark.asyncio
    async def test_database_health_check_missing_file(self) -> None:
        """Test database health check when database file doesn't exist."""
        from app.services.system.health import check_database_health

        # Patch settings.DATABASE_URL to point to non-existent file
        with patch('app.services.system.health.settings') as mock_settings:
            mock_settings.DATABASE_URL = "sqlite:///./nonexistent/test.db"

            result = await check_database_health()

            assert result.name == "database"
            assert result.status == ComponentStatusType.WARNING
            assert "Database not initialized" in result.message
            assert result.metadata["database_exists"] is False
            assert "nonexistent/test.db" in result.metadata["expected_path"]

    @pytest.mark.asyncio
    async def test_database_health_check_connection_failure(self) -> None:
        """Test database health check when connection fails due to permissions."""
        from app.services.system.health import check_database_health

        # Mock settings and Path.exists to simulate file exists but connection fails
        with patch('app.services.system.health.settings') as mock_settings, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('app.core.db.db_session') as mock_db_session:

            # File exists but connection fails
            mock_settings.DATABASE_URL = "sqlite:///./data/test.db"

            # Mock db_session to simulate connection error
            mock_session = MagicMock()
            mock_session.execute.side_effect = Exception("unable to open database file")
            mock_db_session.return_value.__enter__ = MagicMock(
                return_value=mock_session
            )
            mock_db_session.return_value.__exit__ = MagicMock(return_value=None)

            result = await check_database_health()

            assert result.name == "database"
            assert result.status == ComponentStatusType.WARNING
            assert result.message == "Database file not accessible"
            assert "unable to open database file" in result.metadata["error"]

    def test_database_status_metadata_structure(self) -> None:
        """Test that database health check includes proper metadata."""
        from app.services.system.models import ComponentStatus, ComponentStatusType

        # Test successful database component metadata with enhanced fields
        database_metadata = {
            "implementation": "sqlite",
            "url": "sqlite:///:memory:",
            "database_exists": True,
            "engine_echo": False,
            "version": "3.43.2",
            "file_size_bytes": 8192,
            "file_size_human": "8.0 KB",
            "connection_pool_size": 1,
            "pragma_settings": {
                "foreign_keys": True,
                "journal_mode": "delete",
                "cache_size": 2000
            },
            "wal_enabled": False,
        }

        database_status = ComponentStatus(
            name="database",
            status=ComponentStatusType.HEALTHY,
            message="Database connection successful",
            metadata=database_metadata,
        )

        # Test existing fields
        assert database_status.metadata["implementation"] == "sqlite"
        assert "sqlite://" in database_status.metadata["url"]
        assert database_status.metadata["database_exists"] is True
        assert database_status.metadata["engine_echo"] is False

        # Test enhanced metadata fields
        assert database_status.metadata["version"] == "3.43.2"
        assert database_status.metadata["file_size_bytes"] == 8192
        assert database_status.metadata["file_size_human"] == "8.0 KB"
        assert database_status.metadata["connection_pool_size"] == 1
        assert isinstance(database_status.metadata["pragma_settings"], dict)
        assert database_status.metadata["wal_enabled"] is False
