"""Diagnostico empirico del HeuristicBot.

Corre N partidas, identifica las perdidas, y extrae metricas que ayuden a
diagnosticar el patron dominante de fallas.

Metricas capturadas por partida:
- winner, final_turn
- acciones tomadas por el heuristico por tipo (ATTACK, MOVE, CAPTURE, etc.)
- HP promedio de unidades propias al final
- numero de unidades propias muertas durante la partida
- numero de unidades enemigas muertas
- stars maximos acumulados sin gastar
- cities perdidas/capturadas
- distancia minima alcanzada a la city enemiga
- attacks suicidas (atacante muere por retaliation)
- turn en que se entro por primera vez al radio de la city enemiga
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path

from polytopia.agents.heuristic_bot import HeuristicBot
from polytopia.agents.random_bot import RandomBot
from polytopia.engine.actions import legal_actions
from polytopia.engine.rules import apply_action, check_game_over
from polytopia.engine.state_init import create_initial_state
from polytopia.interfaces import ActionType


@dataclass
class GameMetrics:
    seed: int
    winner: int | None
    final_turn: int
    heuristic_player: int

    actions_by_type: dict = field(default_factory=dict)

    heuristic_units_lost: int = 0
    random_units_lost: int = 0
    heuristic_final_hp: float = 0.0

    max_unspent_stars: int = 0
    stars_at_end: int = 0

    heuristic_cities_captured: int = 0
    heuristic_cities_lost: int = 0
    heuristic_final_cities: int = 0

    min_dist_to_enemy_city: int | None = None
    turn_reached_enemy_radius: int | None = None

    suicidal_attacks: int = 0
    successful_kills: int = 0

    ended_turn_with_fresh_units: int = 0

    move_actions: int = 0
    attack_actions: int = 0
    train_actions: int = 0
    capture_actions: int = 0
    harvest_actions: int = 0
    end_turn_actions: int = 0

    total_distance_traveled: int = 0
    distinct_tiles_visited: int = 0
    actions_with_zero_progress: int = 0

    stars_spent_total: int = 0
    stars_received_total: int = 0


def run_diagnostic_game(seed: int, heuristic_player: int = 0) -> GameMetrics:
    """Corre una partida instrumentada y retorna metricas detalladas."""

    state = create_initial_state(seed=seed)
    metrics = GameMetrics(
        seed=seed,
        winner=None,
        final_turn=0,
        heuristic_player=heuristic_player,
    )

    if heuristic_player == 0:
        bot0 = HeuristicBot(player_id=0, seed=seed)
        bot1 = RandomBot(player_id=1, seed=seed + 1000)
    else:
        bot0 = RandomBot(player_id=0, seed=seed + 1000)
        bot1 = HeuristicBot(player_id=1, seed=seed)

    action_counter: Counter = Counter()
    prev_heuristic_unit_ids: set = set()
    prev_random_unit_ids: set = set()
    visited_tiles_by_heur_units: set = set()
    prev_unit_positions: dict = {}
    prev_stars = state.stars[heuristic_player]

    while not state.game_over:
        player = state.current_player
        bot = bot0 if player == 0 else bot1
        actions = legal_actions(state, player)
        if not actions:
            break

        prev_attacker_hp = None
        min_dist_before = None
        if player == heuristic_player:
            enemy_cities_before = [c for c in state.cities.values()
                                   if c.owner != heuristic_player]
            heur_units_before = [u for u in state.units.values()
                                 if u.owner == heuristic_player and u.is_alive]
            if enemy_cities_before and heur_units_before:
                min_dist_before = min(
                    u.position.chebyshev_distance(c.position)
                    for u in heur_units_before
                    for c in enemy_cities_before
                )

        action = bot.select_action(state, actions)

        if player == heuristic_player:
            action_counter[action.action_type.name] += 1

            atype = action.action_type
            if atype == ActionType.MOVE:
                metrics.move_actions += 1
            elif atype == ActionType.ATTACK:
                metrics.attack_actions += 1
            elif atype == ActionType.TRAIN:
                metrics.train_actions += 1
            elif atype == ActionType.CAPTURE:
                metrics.capture_actions += 1
            elif atype == ActionType.HARVEST:
                metrics.harvest_actions += 1
            elif atype == ActionType.END_TURN:
                metrics.end_turn_actions += 1

            if action.action_type == ActionType.END_TURN:
                fresh = sum(
                    1 for u in state.units.values()
                    if u.owner == heuristic_player and u.is_alive
                    and not u.has_moved
                    and not u.has_attacked
                )
                if fresh > 0:
                    metrics.ended_turn_with_fresh_units += 1

            if action.action_type == ActionType.ATTACK and action.unit_id in state.units:
                prev_attacker_hp = state.units[action.unit_id].hp

        new_state = apply_action(state, action)

        if player == heuristic_player:
            if (
                action.action_type == ActionType.ATTACK
                and prev_attacker_hp is not None
                and action.unit_id not in new_state.units
            ):
                metrics.suicidal_attacks += 1

            if action.action_type == ActionType.ATTACK and action.target is not None:
                defender_before = state.unit_at(action.target)
                defender_after = new_state.unit_at(action.target)
                if defender_before is not None and defender_after is None:
                    metrics.successful_kills += 1

            if action.action_type == ActionType.CAPTURE:
                metrics.heuristic_cities_captured += 1

            enemy_cities_after = [c for c in new_state.cities.values()
                                  if c.owner != heuristic_player]
            heur_units_after = [u for u in new_state.units.values()
                                if u.owner == heuristic_player and u.is_alive]
            min_dist_after = None
            if enemy_cities_after and heur_units_after:
                min_dist_after = min(
                    u.position.chebyshev_distance(c.position)
                    for u in heur_units_after
                    for c in enemy_cities_after
                )

            if (min_dist_before is not None and min_dist_after is not None
                    and min_dist_after >= min_dist_before
                    and action.action_type == ActionType.MOVE):
                metrics.actions_with_zero_progress += 1

            for u in new_state.units.values():
                if u.owner == heuristic_player and u.is_alive:
                    visited_tiles_by_heur_units.add(u.position)
                    if u.unit_id in prev_unit_positions:
                        prev_pos = prev_unit_positions[u.unit_id]
                        dist = prev_pos.chebyshev_distance(u.position)
                        metrics.total_distance_traveled += dist
                    prev_unit_positions[u.unit_id] = u.position

            new_stars = new_state.stars[heuristic_player]
            delta = new_stars - prev_stars
            if delta < 0:
                metrics.stars_spent_total += -delta
            elif delta > 0:
                metrics.stars_received_total += delta
            prev_stars = new_stars

        state = new_state

        current_heur_unit_ids = {
            uid for uid, u in state.units.items()
            if u.owner == heuristic_player and u.is_alive
        }
        current_rand_unit_ids = {
            uid for uid, u in state.units.items()
            if u.owner != heuristic_player and u.is_alive
        }

        if prev_heuristic_unit_ids:
            metrics.heuristic_units_lost += len(prev_heuristic_unit_ids - current_heur_unit_ids)
        if prev_random_unit_ids:
            metrics.random_units_lost += len(prev_random_unit_ids - current_rand_unit_ids)

        prev_heuristic_unit_ids = current_heur_unit_ids
        prev_random_unit_ids = current_rand_unit_ids

        heuristic_stars = state.stars[heuristic_player]
        if heuristic_stars > metrics.max_unspent_stars:
            metrics.max_unspent_stars = heuristic_stars

        enemy_cities = [c for c in state.cities.values() if c.owner != heuristic_player]
        heur_units = [u for u in state.units.values() if u.owner == heuristic_player and u.is_alive]
        if enemy_cities and heur_units:
            min_d = min(
                u.position.chebyshev_distance(c.position)
                for u in heur_units
                for c in enemy_cities
            )
            if metrics.min_dist_to_enemy_city is None or min_d < metrics.min_dist_to_enemy_city:
                metrics.min_dist_to_enemy_city = min_d
            if min_d <= 2 and metrics.turn_reached_enemy_radius is None:
                metrics.turn_reached_enemy_radius = state.turn

    final_check = check_game_over(state)
    metrics.winner = final_check[1]
    metrics.final_turn = state.turn
    metrics.actions_by_type = dict(action_counter)
    metrics.stars_at_end = state.stars[heuristic_player]
    metrics.heuristic_final_cities = sum(
        1 for c in state.cities.values() if c.owner == heuristic_player
    )
    heur_alive = [u for u in state.units.values() if u.owner == heuristic_player and u.is_alive]
    metrics.heuristic_final_hp = (
        sum(u.hp for u in heur_alive) / len(heur_alive) if heur_alive else 0.0
    )
    initial_cities = 1
    metrics.heuristic_cities_lost = max(
        0,
        initial_cities + metrics.heuristic_cities_captured - metrics.heuristic_final_cities,
    )
    metrics.distinct_tiles_visited = len(visited_tiles_by_heur_units)

    return metrics


def run_diagnostic_batch(n_seeds: int = 30) -> list[GameMetrics]:
    results = []
    for seed in range(n_seeds):
        m = run_diagnostic_game(seed=seed, heuristic_player=0)
        results.append(m)
    return results


def summarize(results: list[GameMetrics]) -> dict:
    wins = [m for m in results if m.winner == 0]
    losses = [m for m in results if m.winner == 1]
    draws = [m for m in results if m.winner is None]

    def avg(field_name: str, subset: list[GameMetrics]) -> float:
        vals = [getattr(m, field_name) for m in subset if getattr(m, field_name) is not None]
        return sum(vals) / len(vals) if vals else 0.0

    summary = {
        "n_total": len(results),
        "n_wins": len(wins),
        "n_losses": len(losses),
        "n_draws": len(draws),
        "win_rate": len(wins) / len(results) if results else 0.0,
    }

    for subset_name, subset in [("wins", wins), ("losses", losses)]:
        summary[subset_name] = {
            "avg_final_turn": avg("final_turn", subset),
            "avg_suicidal_attacks": avg("suicidal_attacks", subset),
            "avg_successful_kills": avg("successful_kills", subset),
            "avg_units_lost": avg("heuristic_units_lost", subset),
            "avg_enemy_units_killed": avg("random_units_lost", subset),
            "avg_max_unspent_stars": avg("max_unspent_stars", subset),
            "avg_stars_at_end": avg("stars_at_end", subset),
            "avg_min_dist_to_enemy_city": avg("min_dist_to_enemy_city", subset),
            "avg_turn_reached_enemy_radius": avg("turn_reached_enemy_radius", subset),
            "avg_cities_captured": avg("heuristic_cities_captured", subset),
            "avg_cities_lost": avg("heuristic_cities_lost", subset),
            "avg_idle_end_turns": avg("ended_turn_with_fresh_units", subset),
            "avg_move_actions": avg("move_actions", subset),
            "avg_attack_actions": avg("attack_actions", subset),
            "avg_train_actions": avg("train_actions", subset),
            "avg_capture_actions": avg("capture_actions", subset),
            "avg_harvest_actions": avg("harvest_actions", subset),
            "avg_end_turn_actions": avg("end_turn_actions", subset),
            "avg_total_distance_traveled": avg("total_distance_traveled", subset),
            "avg_distinct_tiles_visited": avg("distinct_tiles_visited", subset),
            "avg_actions_with_zero_progress": avg("actions_with_zero_progress", subset),
            "avg_stars_spent_total": avg("stars_spent_total", subset),
            "avg_stars_received_total": avg("stars_received_total", subset),
        }

    summary["loss_pattern_analysis"] = _analyze_loss_patterns(losses)
    return summary


def _analyze_loss_patterns(losses: list[GameMetrics]) -> dict:
    n = len(losses)
    if n == 0:
        return {"n_losses": 0}

    patterns = {
        "n_losses": n,
        "lost_with_unspent_stars": sum(1 for m in losses if m.max_unspent_stars >= 15),
        "lost_with_suicidal_attacks": sum(1 for m in losses if m.suicidal_attacks >= 2),
        "lost_never_reached_enemy": sum(
            1 for m in losses
            if m.turn_reached_enemy_radius is None
            or m.turn_reached_enemy_radius > 20
        ),
        "lost_with_idle_turns": sum(1 for m in losses if m.ended_turn_with_fresh_units >= 3),
        "lost_by_max_turns": sum(1 for m in losses if m.final_turn >= 29),
        "lost_lost_more_cities_than_captured": sum(
            1 for m in losses if m.heuristic_cities_lost > m.heuristic_cities_captured
        ),
        "lost_zero_kills": sum(1 for m in losses if m.successful_kills == 0),
    }

    pattern_counts = {k: v for k, v in patterns.items() if k != "n_losses"}
    sorted_patterns = sorted(pattern_counts.items(), key=lambda x: -x[1])
    patterns["dominant_pattern"] = sorted_patterns[0][0] if sorted_patterns else None
    patterns["dominant_pattern_frequency"] = sorted_patterns[0][1] / n if sorted_patterns else 0

    return patterns


def print_report(summary: dict) -> None:
    print()
    print("=" * 70)
    print("DIAGNOSTICO EMPIRICO HeuristicBot v2")
    print("=" * 70)
    print(f"Total: {summary['n_total']}  Wins: {summary['n_wins']}  "
          f"Losses: {summary['n_losses']}  Draws: {summary['n_draws']}")
    print(f"Win rate: {summary['win_rate']*100:.1f}%")
    print()

    print("Promedios en WINS vs LOSSES:")
    print(f"{'Metrica':<35} {'Wins':>10} {'Losses':>10}  delta (loss-win)")
    print("-" * 70)
    metrics_to_show = [
        "avg_final_turn",
        "avg_suicidal_attacks",
        "avg_successful_kills",
        "avg_units_lost",
        "avg_enemy_units_killed",
        "avg_max_unspent_stars",
        "avg_stars_at_end",
        "avg_min_dist_to_enemy_city",
        "avg_turn_reached_enemy_radius",
        "avg_cities_captured",
        "avg_cities_lost",
        "avg_idle_end_turns",
        "avg_move_actions",
        "avg_attack_actions",
        "avg_train_actions",
        "avg_capture_actions",
        "avg_total_distance_traveled",
        "avg_distinct_tiles_visited",
        "avg_actions_with_zero_progress",
        "avg_stars_spent_total",
    ]
    for m in metrics_to_show:
        w_val = summary["wins"][m]
        l_val = summary["losses"][m]
        delta = l_val - w_val
        print(f"{m:<35} {w_val:>10.2f} {l_val:>10.2f}  {delta:+.2f}")

    print()
    print("Patrones identificados en LOSSES:")
    print("-" * 70)
    patterns = summary["loss_pattern_analysis"]
    for k, v in patterns.items():
        if k.startswith("lost_"):
            pct = (v / patterns["n_losses"] * 100) if patterns["n_losses"] else 0
            print(f"  {k:<45} {v:>3}/{patterns['n_losses']:<3}  ({pct:.0f}%)")

    print()
    print(f"PATRON DOMINANTE: {patterns['dominant_pattern']}")
    print(f"Frecuencia: {patterns['dominant_pattern_frequency']*100:.0f}% de las perdidas")
    print("=" * 70)


def save_report(results: list[GameMetrics], summary: dict, path: str) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({
            "summary": summary,
            "games": [asdict(m) for m in results],
        }, f, indent=2)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=30, help="numero de partidas")
    parser.add_argument("--output", type=str, default="reports/diagnostic_v2.json")
    args = parser.parse_args()

    results = run_diagnostic_batch(n_seeds=args.n)
    summary = summarize(results)
    print_report(summary)
    save_report(results, summary, args.output)
    print(f"\nReporte guardado en: {args.output}")


if __name__ == "__main__":
    main()
