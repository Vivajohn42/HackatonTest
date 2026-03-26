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

TERMINAL_TYPES = [
    "MQS-F-2.8", "MQS-M-2.8", "MCP-F-2.8", "MCP-M-2.8", "MLK-F-1.2",
    "MLK-M-1.2", "JPT-F-0.64", "JPT-M-0.64", "MCON-F-1.2", "MCON-M-1.2",
]

SEAL_TYPES = [None, "SEAL-S", "SEAL-M", "SEAL-L"]

WIRE_TYPES = [
    ("FLRY-A 0.22mm2", 0.22), ("FLRY-A 0.35mm2", 0.35),
    ("FLRY-B 0.50mm2", 0.50), ("FLRY-B 0.75mm2", 0.75),
    ("FLRY-B 1.00mm2", 1.00), ("FLRY-B 1.50mm2", 1.50),
    ("FLRY-B 2.50mm2", 2.50),
]


def create_cassette_types() -> list[CassetteType]:
    types = []
    ct_id = 0
    for terminal in TERMINAL_TYPES:
        for seal in SEAL_TYPES[:2]:
            ct_id += 1
            seal_desc = f" + {seal}" if seal else ""
            types.append(CassetteType(
                id=f"CT-{ct_id:03d}",
                terminal_type=terminal,
                seal_type=seal,
                description=f"{terminal}{seal_desc}",
            ))
    return types


def create_cassette_pool(cassette_types: list[CassetteType], copies: int = 2) -> list[Cassette]:
    pool = []
    cass_id = 0
    for i, ct in enumerate(cassette_types):
        num_copies = copies + 1 if i < len(cassette_types) // 2 else copies
        for _ in range(num_copies):
            cass_id += 1
            pool.append(Cassette(
                id=f"CASS-{cass_id:03d}",
                cassette_type=ct,
                state=CassetteState.AVAILABLE,
            ))
    return pool


def create_orders(
    cassette_types: list[CassetteType],
    num_orders: int = 150,
    shift_duration_min: float = 480.0,
    seed: int = 42,
) -> list[ProductionOrder]:
    rng = random.Random(seed)
    orders = []

    for i in range(num_orders):
        wire_name, wire_cs = rng.choice(WIRE_TYPES)
        ct_left = rng.choice(cassette_types)
        ct_right = rng.choice(cassette_types)

        quantity = rng.choice([25, 50, 100, 150, 200, 300, 500])
        wire_length = rng.choice([150, 200, 300, 500, 750, 1000, 1500, 2000])

        prio_roll = rng.random()
        if prio_roll < 0.05:
            priority = OrderPriority.URGENT
        elif prio_roll < 0.20:
            priority = OrderPriority.HIGH
        elif prio_roll < 0.90:
            priority = OrderPriority.NORMAL
        else:
            priority = OrderPriority.LOW

        if priority == OrderPriority.URGENT:
            due_time = rng.uniform(60, shift_duration_min * 0.5)
        elif priority == OrderPriority.HIGH:
            due_time = rng.uniform(120, shift_duration_min * 0.75)
        else:
            due_time = rng.uniform(shift_duration_min * 0.3, shift_duration_min) if rng.random() > 0.3 else None

        orders.append(ProductionOrder(
            id=f"ORD-{i + 1:04d}",
            wire_type=wire_name,
            wire_cross_section_mm2=wire_cs,
            wire_length_mm=wire_length,
            quantity=quantity,
            cassette_type_left=ct_left,
            cassette_type_right=ct_right,
            priority=priority,
            due_time=due_time,
        ))

    return orders


def create_sample_plant(
    num_machines: int = 3,
    num_orders: int = 150,
    seed: int = 42,
) -> Plant:
    cassette_types = create_cassette_types()
    cassette_pool = create_cassette_pool(cassette_types)

    rng = random.Random(seed)
    for cassette in rng.sample(cassette_pool, min(6, len(cassette_pool))):
        cassette.state = CassetteState.READY

    machines = [
        A650Machine(id=f"A650-{i + 1}")
        for i in range(num_machines)
    ]

    orders = create_orders(cassette_types, num_orders=num_orders, seed=seed)

    return Plant(
        name="Beispielwerk Dierikon",
        machines=machines,
        setup_machine=SetupMachine(id="SETUP-1", setup_duration_min=12.0),
        cassette_pool=cassette_pool,
        cassette_types=cassette_types,
        orders=orders,
    )
