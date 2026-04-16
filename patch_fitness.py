def _trigger_fitness(chain_id,task_text,correct,changes):
    try:
        from judgment.fitness_baseline import FitnessBaseline
        FitnessBaseline().record(chain_id,task_text,correct,changes)
    except Exception as e:_log.debug(f"fitness trigger skip: {e}")
    # P1改进: fitness_evolution反馈循环
    try:
        from judgment.fitness_evolution import record_judgment_outcome
        # 从changes获取dimensions
        dims = list(changes.keys()) if changes else []
        weights = {dim: changes[dim].get("belief_after", 0.5) for dim in dims} if changes else {}
        if dims:
            record_judgment_outcome(
                chain_id=chain_id,
                task_text=task_text or "",
                dimensions=dims,
                weights=weights,
                correct=correct,
            )
    except Exception as e2:_log.debug(f"fitness_evolution trigger skip: {e2}")
