"""Docker compose operations for RAG Memory."""

import subprocess
from pathlib import Path
from typing import Optional
from .paths import Paths


class DockerManager:
    """Manage Docker containers for RAG Memory."""

    @staticmethod
    def is_initialized() -> bool:
        """Check if RAG Memory has been initialized."""
        return Paths.docker_compose_file().exists() and Paths.config_yaml().exists()

    @staticmethod
    def run_compose(command: list[str], capture_output: bool = False) -> Optional[subprocess.CompletedProcess]:
        """Run a docker-compose command.

        Args:
            command: List of command arguments to pass to docker-compose
            capture_output: Whether to capture output for processing

        Returns:
            CompletedProcess object or None if not initialized
        """
        compose_file = Paths.docker_compose_file()
        env_file = Paths.env_file()

        if not compose_file.exists():
            print("❌ Not initialized. Please run setup first.")
            print(f"   Expected docker-compose.yml at: {compose_file}")
            return None

        cmd = [
            'docker-compose',
            '-f', str(compose_file),
            '--project-name', 'rag-memory'
        ]

        # Add env file if it exists
        if env_file.exists():
            cmd.extend(['--env-file', str(env_file)])

        cmd.extend(command)

        if capture_output:
            # Redirect stderr to devnull to suppress docker-compose warnings
            return subprocess.run(cmd, capture_output=True, text=True, stderr=subprocess.DEVNULL)
        else:
            return subprocess.run(cmd, stderr=subprocess.DEVNULL)

    @staticmethod
    def start() -> Optional[subprocess.CompletedProcess]:
        """Start all RAG Memory services."""
        print("Starting RAG Memory services...")
        # Use --force-recreate to handle any stuck/conflicting containers
        result = DockerManager.run_compose(['up', '-d', '--force-recreate', '--remove-orphans'])
        if result and result.returncode == 0:
            print("✅ Services started successfully")
            print("   MCP Server: http://localhost:8001/sse")
            print("   Neo4j Browser: http://localhost:7475")
        elif result:
            print("❌ Failed to start services. Check logs with: rag logs")
        return result

    @staticmethod
    def stop() -> Optional[subprocess.CompletedProcess]:
        """Stop all RAG Memory services."""
        print("Stopping RAG Memory services...")
        # Use down with --remove-orphans and --volumes to clean up everything
        result = DockerManager.run_compose(['down', '--remove-orphans'])
        if result and result.returncode == 0:
            print("✅ Services stopped")
        return result

    @staticmethod
    def restart() -> Optional[subprocess.CompletedProcess]:
        """Restart all RAG Memory services."""
        print("Restarting RAG Memory services...")
        DockerManager.stop()
        return DockerManager.start()

    @staticmethod
    def status() -> Optional[str]:
        """Check service status.

        Returns:
            Status output or None if not initialized
        """
        # Use docker ps directly to filter only -local containers
        # docker-compose ps doesn't support name filtering
        cmd = [
            'docker', 'ps', '-a',
            '--filter', 'label=com.docker.compose.project=rag-memory',
            '--filter', 'name=-local',
            '--format', 'table {{.Names}}\t{{.Image}}\t{{.Command}}\t{{.Status}}\t{{.Ports}}'
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        if result.returncode == 0:
            return result.stdout
        return None

    @staticmethod
    def logs(service: Optional[str] = None, tail: int = 50, follow: bool = False) -> Optional[subprocess.CompletedProcess]:
        """View Docker container logs.

        Args:
            service: Specific service to show logs for (None for all)
            tail: Number of lines to show
            follow: Whether to follow log output

        Returns:
            CompletedProcess object or None
        """
        cmd = ['logs', f'--tail={tail}']
        if follow:
            cmd.append('-f')
        if service:
            cmd.append(service)

        return DockerManager.run_compose(cmd)

    @staticmethod
    def exec(service: str, command: list[str]) -> Optional[subprocess.CompletedProcess]:
        """Execute a command in a running container.

        Args:
            service: Service name to exec into
            command: Command to execute

        Returns:
            CompletedProcess object or None
        """
        cmd = ['exec', service] + command
        return DockerManager.run_compose(cmd)