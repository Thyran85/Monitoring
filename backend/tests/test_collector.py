"""
Tests de la collecte de métriques — Étape 2.

Exécution :
    cd backend && ./venv/bin/python -m tests.test_collector
"""

from __future__ import annotations

import sys

from collector import metrics


def _check(label: str, condition: bool, detail: str = "") -> bool:
    status = "OK  " if condition else "FAIL"
    print(f"[{status}] {label}" + (f" — {detail}" if detail else ""))
    return condition


def main() -> int:
    ok = True

    # --- CPU ---
    cpu = metrics.collect_cpu()
    ok &= _check("CPU : pourcentage global 0-100", 0 <= cpu["percent"] <= 100, f"{cpu['percent']}%")
    ok &= _check("CPU : un pourcentage par cœur", len(cpu["per_core"]) == cpu["core_count"],
                 f"{len(cpu['per_core'])} cœurs pour {cpu['core_count']} logiques")
    ok &= _check("CPU : chaque cœur dans 0-100",
                 all(0 <= v <= 100 for v in cpu["per_core"]))

    # --- RAM ---
    ram = metrics.collect_ram()
    ok &= _check("RAM : totale > 0", ram["total_mb"] > 0, f"{ram['total_mb']} Mo")
    ok &= _check("RAM : utilisée <= totale", 0 < ram["used_mb"] <= ram["total_mb"])
    ok &= _check("RAM : disponible <= totale", 0 < ram["available_mb"] <= ram["total_mb"])
    ok &= _check("RAM : pourcentage 0-100", 0 <= ram["percent"] <= 100, f"{ram['percent']}%")
    ok &= _check("RAM : used + available ≈ total (±5%)",
                 abs(ram["used_mb"] + ram["available_mb"] - ram["total_mb"])
                 / ram["total_mb"] < 0.05)

    # --- Disque ---
    disk = metrics.collect_disk("/")
    ok &= _check("DISK : totale > 0", disk["total_gb"] > 0, f"{disk['total_gb']} Go")
    ok &= _check("DISK : utilisé + libre ≈ total (±1%)",
                 abs(disk["used_gb"] + disk["free_gb"] - disk["total_gb"])
                 / disk["total_gb"] < 0.01)
    ok &= _check("DISK : pourcentage 0-100", 0 <= disk["percent"] <= 100, f"{disk['percent']}%")
    ok &= _check("DISK : path renseigné", disk["path"] == "/", disk["path"])

    # --- Snapshot complet ---
    snap = metrics.collect_all()
    ok &= _check("SNAPSHOT : horodatage ISO 8601 UTC", snap["collected_at"].endswith("+00:00"),
                 snap["collected_at"])
    ok &= _check("SNAPSHOT : clés cpu/ram/disk présentes",
                 all(k in snap for k in ("cpu", "ram", "disk")))

    # --- Machine ---
    machine = metrics.collect_machine()
    ok &= _check("MACHINE : hostname renseigné", bool(machine["hostname"]), machine["hostname"])
    ok &= _check("MACHINE : IP locale valide",
                 machine["ip_address"].count(".") == 3, machine["ip_address"])
    ok &= _check("MACHINE : CPU cores > 0", machine["cpu_cores"] > 0)

    # --- Sérialisation CLOB ---
    json_str = metrics.cpu_cores_json(cpu)
    ok &= _check("CLOB : JSON valide", json_str.startswith("["), json_str[:60])

    print()
    print("TOUS LES TESTS PASSENT" if ok else "DES TESTS ONT ÉCHOUÉ")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
