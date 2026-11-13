from app.engine import get_engine

DEPOT = (3.40, -76.55)
CROSSED_SQUARE = [(3.41, -76.54), (3.45, -76.50), (3.41, -76.50), (3.45, -76.54)]


def test_optimized_route_is_shorter_than_crossing_order():
    result = get_engine().optimize(DEPOT, CROSSED_SQUARE)

    assert result.optimized_km < result.naive_km


def test_order_is_a_permutation_of_stop_indices():
    result = get_engine().optimize(DEPOT, CROSSED_SQUARE)

    assert sorted(result.order) == [0, 1, 2, 3]


def test_no_stops_gives_empty_order_and_zero_distance():
    result = get_engine().optimize(DEPOT, [])

    assert result.order == []
    assert result.optimized_km == 0.0
    assert result.naive_km == 0.0


def test_single_stop_is_a_round_trip():
    result = get_engine().optimize(DEPOT, [(3.45, -76.50)])

    assert result.order == [0]
    assert result.optimized_km == result.naive_km
    assert result.optimized_km > 0


def test_get_engine_returns_the_same_instance():
    assert get_engine() is get_engine()


def test_consecutive_calls_do_not_leak_state():
    engine = get_engine()
    big = engine.optimize(DEPOT, CROSSED_SQUARE)
    small = engine.optimize(DEPOT, CROSSED_SQUARE[:2])
    again = engine.optimize(DEPOT, CROSSED_SQUARE)

    assert sorted(small.order) == [0, 1]
    assert again == big
