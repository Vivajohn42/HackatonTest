#!/usr/bin/env python3
import copy
import sys

from data.sample_plant import create_sample_plant
from scheduler.naive import NaiveScheduler
from scheduler.optimized import OptimizedScheduler
from simulator.engine import SimulationEngine


def run_comparison(num_orders: int = 150, num_machines: int = 3, seed: int = 42) -> None:
    print("=" * 60)
    print("KASSETTEN-PLANUNGS-SYSTEM - Simulationsvergleich")
    print("=" * 60)

    base_plant = create_sample_plant(
        num_machines=num_machines,
        num_orders=num_orders,
        seed=seed,
    )

    print(f"\nWerk:              {base_plant.name}")
    print(f"A650 Maschinen:    {len(base_plant.machines)}")
    print(f"Kassettentypen:    {len(base_plant.cassette_types)}")
    print(f"Kassetten im Pool: {len(base_plant.cassette_pool)}")
    print(f"Auftraege:         {len(base_plant.orders)}")
    print(f"Setup-Dauer:       {base_plant.setup_machine.setup_duration_min} min")

    schedulers = [
        NaiveScheduler(),
        OptimizedScheduler(),
    ]

    results = []
    for scheduler in schedulers:
        plant = copy.deepcopy(base_plant)
        engine = SimulationEngine(plant, scheduler)
        result = engine.run(max_time_min=480.0)
        results.append((scheduler.name, result))

        print(f"\n{'─' * 60}")
        print(f"Scheduler: {scheduler.name}")
        print(result.summary())

    if len(results) == 2:
        name1, r1 = results[0]
        name2, r2 = results[1]
        print(f"\n{'=' * 60}")
        print("VERGLEICH")
        print(f"{'=' * 60}")

        changeover_diff = r1.total_changeovers - r2.total_changeovers
        time_saved = r1.total_changeover_min - r2.total_changeover_min
        completed_diff = r2.orders_completed - r1.orders_completed

        print(f"Kassettenwechsel eingespart: {changeover_diff} ({time_saved:.1f} min)")
        print(f"Mehr Auftraege abgeschlossen: {completed_diff}")

        if r1.total_changeover_min > 0:
            improvement = (time_saved / r1.total_changeover_min) * 100
            print(f"Ruestzeit-Reduktion:          {improvement:.1f}%")

        for name, r in results:
            avg_util = sum(r.machine_utilization.values()) / len(r.machine_utilization) if r.machine_utilization else 0
            print(f"Avg Auslastung {name}: {avg_util:.1%}")


def main() -> None:
    num_orders = 150
    num_machines = 3
    seed = 42

    if len(sys.argv) > 1:
        num_orders = int(sys.argv[1])
    if len(sys.argv) > 2:
        num_machines = int(sys.argv[2])
    if len(sys.argv) > 3:
        seed = int(sys.argv[3])

    run_comparison(num_orders=num_orders, num_machines=num_machines, seed=seed)


if __name__ == "__main__":
    main()
