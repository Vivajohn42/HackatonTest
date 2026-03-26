#!/usr/bin/env python3
import copy
import sys

from data.sample_plant import create_sample_plant
from scheduler.naive import NaiveScheduler
from scheduler.optimized import OptimizedScheduler
from simulator.engine import SimulationEngine


def print_job_overview(completed_orders):
    print(f"\n{'Job':<6} {'Artikel':<25} {'S1':>4} {'S2':>4} {'Leadsets':>9} {'Status':<8} {'Start':>8} {'Ende':>8} {'Dauer':>8}")
    print("-" * 95)
    for order in completed_orders:
        start = f"R{int(order.start_time)}" if order.start_time else "-"
        end = f"R{int(order.end_time)}" if order.end_time else "-"
        duration = f"{int(order.end_time - order.start_time)}s" if order.start_time and order.end_time else "-"
        status = "Done" if order.is_completed else "..."
        print(f"{order.id:<6} {order.article:<25} {order.cassette_type_s1.id:>4} {order.cassette_type_s2.id:>4} "
              f"{order.produced:>4}/{order.leadsets:<4} {status:<8} {start:>8} {end:>8} {duration:>8}")


def run_comparison(num_orders: int = 12, num_machines: int = 3, seed: int = 42) -> None:
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
    print(f"Assembly Station:  {base_plant.setup_machine.setup_duration_min} min Setup-Dauer")

    schedulers = [
        NaiveScheduler(),
        OptimizedScheduler(),
    ]

    results = []
    for scheduler in schedulers:
        plant = copy.deepcopy(base_plant)
        engine = SimulationEngine(plant, scheduler)
        result = engine.run(max_time_sec=36000.0)
        results.append((scheduler.name, result, engine))

        print(f"\n{'_' * 60}")
        print(f"Scheduler: {scheduler.name}")
        print(result.summary())

        print("\nJob-Uebersicht:")
        seen = set()
        unique_orders = []
        for o in engine.completed_orders:
            if o.id not in seen:
                seen.add(o.id)
                unique_orders.append(o)
        print_job_overview(unique_orders)

    if len(results) == 2:
        name1, r1, _ = results[0]
        name2, r2, _ = results[1]
        print(f"\n{'=' * 60}")
        print("VERGLEICH")
        print(f"{'=' * 60}")

        changeover_diff = r1.total_changeovers - r2.total_changeovers
        time_saved = r1.total_changeover_sec - r2.total_changeover_sec
        completed_diff = r2.orders_completed - r1.orders_completed
        leadset_diff = r2.total_leadsets_produced - r1.total_leadsets_produced

        print(f"Kassettenwechsel eingespart: {changeover_diff} ({time_saved:.0f} sec)")
        print(f"Mehr Auftraege abgeschlossen: {completed_diff}")
        print(f"Mehr Leadsets produziert:     {leadset_diff}")
        print(f"Warteticks Naive:            {r1.total_wait_ticks}")
        print(f"Warteticks Optimiert:        {r2.total_wait_ticks}")

        for name, r, _ in results:
            avg_util = sum(r.machine_utilization.values()) / len(r.machine_utilization) if r.machine_utilization else 0
            print(f"Avg Auslastung {name}: {avg_util:.1%}")


def main() -> None:
    num_orders = 12
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
