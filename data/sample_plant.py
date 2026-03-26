from __future__ import annotations

import random
from simulator.models import (
    A650Machine,
    Cassette,
    CassetteState,
    CassetteType,
    OrderPriority,
    Plant,
    ProductionOrder,
    SetupMachine,
)


ARTICLES = [
    ("Kabelbaum KFZ-A",         "T-A", "T-B", 300),
    ("Kabelbaum KFZ-B",         "T-A", "T-C", 250),
    ("Steuerleitung CAN-Bus",   "T-C", "T-D", 400),
    ("Sensorleitung Typ Y",     "T-B", "T-D", 200),
    ("Motorleitung ML-1",       "T-C", "T-B", 180),
    ("Gebaeudeverteilung GV-2", "T-D", "T-A", 500),
    ("ABS-Sensorleitung",       "T-E", "T-F", 350),
    ("Zuendkabel ZK-3",         "T-A", "T-D", 150),
    ("Lichtkabel LK-1",         "T-B", "T-C", 220),
    ("Klimaleitung KL-4",       "T-G", "T-H", 280),
    ("Tuerverkabelung TV-2",    "T-E", "T-A", 190),
    ("Heckleuchte HL-1",        "T-F", "T-B", 160),
    ("Frontscheinwerfer FS-3",  "T-G", "T-D", 240),
    ("Sitzheizung SH-2",        "T-H", "T-C", 310),
    ("Dachantenne DA-1",        "T-E", "T-H", 120),
]


def create_cassette_types() -> list[CassetteType]:
    return [
        CassetteType(id="T-A", terminal_type="MQS-F-2.8", roll_capacity=8000,
                      description="MQS Female 2.8mm"),
        CassetteType(id="T-B", terminal_type="MQS-M-2.8", roll_capacity=8000,
                      description="MQS Male 2.8mm"),
        CassetteType(id="T-C", terminal_type="MCP-F-2.8", roll_capacity=6000,
                      description="MCP Female 2.8mm"),
        CassetteType(id="T-D", terminal_type="MCP-M-2.8", roll_capacity=6000,
                      description="MCP Male 2.8mm"),
        CassetteType(id="T-E", terminal_type="JPT-F-0.64", roll_capacity=12000,
                      description="JPT Female 0.64mm"),
        CassetteType(id="T-F", terminal_type="JPT-M-0.64", roll_capacity=12000,
                      description="JPT Male 0.64mm"),
        CassetteType(id="T-G", terminal_type="MCON-F-1.2", roll_capacity=10000,
                      description="MCON Female 1.2mm"),
        CassetteType(id="T-H", terminal_type="MCON-M-1.2", roll_capacity=10000,
                      description="MCON Male 1.2mm"),
    ]


def create_cassette_pool(cassette_types: list[CassetteType], copies: int = 3) -> list[Cassette]:
    pool = []
    cass_id = 0
    for ct in cassette_types:
        for _ in range(copies):
            cass_id += 1
            pool.append(Cassette(
                id=f"CASS-{cass_id:03d}",
                cassette_type=ct,
                state=CassetteState.AVAILABLE,
                roll_remaining=0,
            ))
    return pool


def create_orders(
    cassette_types: list[CassetteType],
    num_orders: int = 12,
    seed: int = 42,
) -> list[ProductionOrder]:
    rng = random.Random(seed)
    ct_map = {ct.id: ct for ct in cassette_types}
    orders = []

    for i in range(num_orders):
        article_name, s1_key, s2_key, base_leadsets = rng.choice(ARTICLES)
        leadsets = int(base_leadsets * rng.uniform(0.5, 1.5))
        leadsets = max(50, min(600, leadsets))

        prio_roll = rng.random()
        if prio_roll < 0.05:
            priority = OrderPriority.URGENT
        elif prio_roll < 0.20:
            priority = OrderPriority.HIGH
        elif prio_roll < 0.90:
            priority = OrderPriority.NORMAL
        else:
            priority = OrderPriority.LOW

        shift_sec = 36000.0
        if priority == OrderPriority.URGENT:
            due_time = rng.uniform(3600, shift_sec * 0.4)
        elif priority == OrderPriority.HIGH:
            due_time = rng.uniform(7200, shift_sec * 0.7)
        else:
            due_time = rng.uniform(shift_sec * 0.3, shift_sec) if rng.random() > 0.3 else None

        orders.append(ProductionOrder(
            id=f"J{i + 1:03d}",
            article=article_name,
            leadsets=leadsets,
            cassette_type_s1=ct_map[s1_key],
            cassette_type_s2=ct_map[s2_key],
            priority=priority,
            due_time=due_time,
        ))

    return orders


def create_sample_plant(
    num_machines: int = 3,
    num_orders: int = 12,
    seed: int = 42,
) -> Plant:
    cassette_types = create_cassette_types()
    cassette_pool = create_cassette_pool(cassette_types, copies=3)

    rng = random.Random(seed)
    initial_ready = rng.sample(cassette_pool, min(8, len(cassette_pool)))
    for cassette in initial_ready:
        cassette.state = CassetteState.READY
        cassette.roll_remaining = cassette.cassette_type.roll_capacity

    machines = [
        A650Machine(id=f"Maschine {i + 1}")
        for i in range(num_machines)
    ]

    orders = create_orders(cassette_types, num_orders=num_orders, seed=seed)

    return Plant(
        name="Beispielwerk Dierikon",
        machines=machines,
        setup_machine=SetupMachine(id="ASSEMBLY-1", setup_duration_min=12.0),
        cassette_pool=cassette_pool,
        cassette_types=cassette_types,
        orders=orders,
    )
