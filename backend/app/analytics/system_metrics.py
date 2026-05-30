import subprocess

import httpx
import psutil

SERVICES = {
    "backend": "shakti-backend",
    "ai-inference": "shakti-ai-inference",
    "shakti-webrtc": "shakti-webrtc",
    "mysql": "shakti-mysql",
}


def _read_gpu_metrics() -> dict:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        gpu, used, total = [float(value.strip()) for value in result.stdout.splitlines()[0].split(",")]
        return {
            "gpu_percent": gpu,
            "vram_used_mb": used,
            "vram_total_mb": total,
            "vram_percent": (used / total * 100) if total else None,
        }
    except Exception:
        return {"gpu_percent": None, "vram_used_mb": None, "vram_total_mb": None, "vram_percent": None}


def _docker_stats() -> dict:
    try:
        transport = httpx.HTTPTransport(uds="/var/run/docker.sock")
        with httpx.Client(transport=transport, base_url="http://docker", timeout=2) as client:
            service_stats = {}
            for service, container in SERVICES.items():
                response = client.get(f"/containers/{container}/stats", params={"stream": "false"})
                if response.status_code >= 400:
                    continue
                payload = response.json()
                memory = payload.get("memory_stats", {})
                usage = float(memory.get("usage") or 0)
                limit = float(memory.get("limit") or 0)
                service_stats[service] = {
                    "container": container,
                    "ram_used_mb": round(usage / 1024 / 1024, 1),
                    "ram_limit_mb": round(limit / 1024 / 1024, 1) if limit else None,
                    "ram_percent": round((usage / limit) * 100, 1) if limit else None,
                }
            return service_stats
    except Exception:
        return {}


def read_system_metrics() -> dict:
    gpu = _read_gpu_metrics()
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_percent": psutil.virtual_memory().percent,
        "gpu_percent": gpu["gpu_percent"],
        "vram_percent": gpu["vram_percent"],
        "vram_used_mb": gpu["vram_used_mb"],
        "vram_total_mb": gpu["vram_total_mb"],
        "service_memory": _docker_stats(),
    }
