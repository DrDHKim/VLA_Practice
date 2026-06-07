from __future__ import annotations

import importlib.util
import platform
import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OFFLINE_DIR = REPO_ROOT / "data" / "offline"
CARLA_DIR = OFFLINE_DIR / "simulators" / "carla"
REQUIRED_MODULES = [
    "torch",
    "torchvision",
    "transformers",
    "accelerate",
    "peft",
    "datasets",
    "hydra",
    "pydantic",
    "cv2",
    "numpy",
    "scipy",
    "tqdm",
    "pytest",
]
SYSTEM_TOOLS = {
    "git": "repository work",
    "git-lfs": "large file pointers in external repos/datasets",
    "ffmpeg": "video export/debug clips from driving episodes",
    "cmake": "native extension builds when a dependency has no wheel",
}


def ok(message: str) -> None:
    print(f"[OK] {message}")


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def fail(message: str) -> None:
    print(f"[FAIL] {message}")


def size_gib(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total / (1024**3)


def check_platform() -> int:
    issues = 0
    system = platform.system()
    machine = platform.machine()
    mac_version = platform.mac_ver()[0] or "unknown"
    if system == "Darwin" and machine == "arm64":
        ok(f"macOS arm64 detected: {mac_version}")
    else:
        warn(f"expected macOS arm64, got system={system}, machine={machine}")

    py = sys.version_info
    if py.major == 3 and py.minor == 10:
        ok(f"Python {py.major}.{py.minor}.{py.micro}")
    else:
        fail(f"expected Python 3.10, got {py.major}.{py.minor}.{py.micro}")
        issues += 1
    return issues


def check_disk() -> int:
    issues = 0
    usage = shutil.disk_usage(REPO_ROOT)
    free_gib = usage.free / (1024**3)
    if free_gib >= 40:
        ok(f"free disk space: {free_gib:.1f}GiB")
    else:
        fail(f"free disk space is low: {free_gib:.1f}GiB. Keep at least 40GiB for CARLA logs/checkpoints.")
        issues += 1

    offline_gib = size_gib(OFFLINE_DIR)
    if offline_gib <= 120:
        ok(f"offline cache: {offline_gib:.1f}GiB / 120GiB")
    else:
        fail(f"offline cache over budget: {offline_gib:.1f}GiB / 120GiB")
        issues += 1
    return issues


def check_system_tools() -> int:
    for tool, purpose in SYSTEM_TOOLS.items():
        path = shutil.which(tool)
        if path:
            ok(f"{tool}: {path}")
        else:
            warn(f"{tool} is not installed or not on PATH. Needed for {purpose}.")
    return 0


def check_modules() -> int:
    issues = 0
    missing = [name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None]
    if missing:
        fail("missing Python modules: " + ", ".join(missing))
        issues += len(missing)
    else:
        ok("required Python modules are importable")

    carla_spec = importlib.util.find_spec("carla")
    if carla_spec is None:
        warn("carla Python package is not installed. M1 needs CARLA PythonAPI wheel or PYTHONPATH.")
    else:
        ok("carla Python package is importable")
    return issues


def check_torch() -> int:
    issues = 0
    try:
        import torch
    except Exception as exc:  # pragma: no cover - diagnostic script
        fail(f"torch import failed: {exc}")
        return 1

    ok(f"torch {torch.__version__}")
    mps_built = torch.backends.mps.is_built()
    mps_available = torch.backends.mps.is_available()
    if mps_available:
        ok("MPS is available")
    elif mps_built:
        warn("MPS is built but not available in this process. Use CPU smoke mode unless a local terminal shows MPS=true.")
    else:
        warn("MPS is not built into this torch wheel. Use CPU smoke mode on MacBook.")
    return issues


def check_offline_assets() -> int:
    issues = 0
    required_dirs = [OFFLINE_DIR / "hf_models" / "Qwen2.5-VL-3B-Instruct"]
    for path in required_dirs:
        if path.exists():
            ok(f"exists: {path.relative_to(REPO_ROOT)}")
        else:
            fail(f"missing: {path.relative_to(REPO_ROOT)}")
            issues += 1

    carla_runtime_markers = list(CARLA_DIR.glob("CarlaUE4*")) + list(CARLA_DIR.glob("CARLA_*"))
    if carla_runtime_markers:
        ok("CARLA runtime candidate exists under data/offline/simulators/carla")
    else:
        warn(
            "no verified CARLA server runtime found. Use a Linux/Windows server, "
            "or validate the experimental CrossOver/D3DMetal + Windows CARLA path separately."
        )

    crossover_wine = Path("/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin/wine")
    crossover_bottle = Path.home() / "Library" / "Application Support" / "CrossOver" / "Bottles" / "carla-rgb64"
    crossover_source = CARLA_DIR / "crossover_source" / "drive_c"
    if crossover_wine.exists():
        ok(f"CrossOver wine exists: {crossover_wine}")
    else:
        warn("CrossOver is not installed. See docs/carla_mac_setup.md.")
    if crossover_bottle.exists():
        ok(f"CrossOver CARLA bottle exists: {crossover_bottle}")
    else:
        warn("CrossOver CARLA bottle carla-rgb64 is not installed. See docs/carla_mac_setup.md.")
    if (crossover_source / "CARLA").exists() and (crossover_source / "Python37").exists():
        ok("CrossOver CARLA source prefix exists under data/offline/simulators/carla/crossover_source")
    else:
        warn("CrossOver CARLA source prefix is incomplete. See docs/carla_mac_setup.md.")
    return issues


def main() -> int:
    print("MacBook readiness check")
    print(f"repo: {REPO_ROOT}")
    issues = 0
    issues += check_platform()
    issues += check_disk()
    issues += check_system_tools()
    issues += check_modules()
    issues += check_torch()
    issues += check_offline_assets()
    if issues:
        print(f"result: {issues} blocking issue(s)")
        return 1
    print("result: no blocking issues; review WARN lines before CARLA/MPS work")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
