# Train placement compiled with Numba when it is installed: one row of positions across at a time, in a few small arrays instead of
# several deck-sized ones. The arithmetic is that of along_span.worst_trains_as_arrays operation for operation (running maximum, first
# position it is reached, 0 + front vehicle + next vehicle, strictly worse), compiled without fastmath, so the results are the same bits.
try:
    import numpy as np
    from numba import njit
except ImportError:
    worst_trains = None
else:
    @njit(cache=True)
    def worst_trains(signed_one, across_then_along, vehicle_in_front, first_with_room, most_vehicles, sign):
        rows, along = signed_one.shape
        lengths = np.zeros(rows, np.int64)
        responses = np.zeros(rows)
        chosen_at = np.zeros((rows, max(most_vehicles, 1)), np.int64)
        totals = np.empty((max(most_vehicles, 1), along))
        running = np.empty((max(most_vehicles, 1), along))
        chosen = np.empty(max(most_vehicles, 1), np.int64)
        for row in range(rows):
            signed_worst = -np.inf
            for i in range(along):
                totals[0, i] = signed_one[row, i]
            for vehicles in range(1, most_vehicles + 1):
                v = vehicles - 1
                if vehicles > 1:
                    best = totals[v - 1, 0]
                    running[v, 0] = best
                    for i in range(1, along):
                        value = totals[v - 1, i]
                        if value > best:
                            best = value
                        running[v, i] = best
                    for i in range(along):
                        if i < first_with_room:
                            totals[v, i] = -np.inf
                        else:
                            totals[v, i] = signed_one[row, i] + running[v, vehicle_in_front[i]]
                fits = False
                at = 0
                top = totals[v, 0]
                for i in range(along):
                    value = totals[v, i]
                    if np.isfinite(value):
                        fits = True
                    if value > top:
                        top = value
                        at = i
                if not fits:
                    break
                chosen[v] = at
                for length in range(v, 0, -1):
                    target = running[length, vehicle_in_front[chosen[length]]]
                    j = 0
                    while totals[length - 1, j] != target:
                        j += 1
                    chosen[length - 1] = j
                response = 0.0
                for k in range(vehicles):
                    response = response + across_then_along[row, chosen[k]]
                if sign * response > signed_worst:
                    signed_worst = sign * response
                    lengths[row] = vehicles
                    responses[row] = response
                    for k in range(vehicles):
                        chosen_at[row, k] = chosen[k]
        return lengths, responses, chosen_at
