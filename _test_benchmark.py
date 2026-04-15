"""Quick test of RealRunner"""
from evolutions.benchmark import RealRunner, EvolutionMetrics

bm = EvolutionMetrics(runner=RealRunner())
r = bm.compare(
    task_id='test_judgment',
    task_text='做一个九九乘法表 Flutter App',
    skills_p1=[],
    skills_p2=['flutter-dev'],
)
print(f'Token savings: {r.token_savings_pct:.1%}')
print(f'Completion change: {r.completion_rate_change:+.1%}')
print(f'Speed change: {r.speed_change_pct:+.1%}')
print(f'Judgment: {r._judgment()}')
print(f'P1 tokens: {r.p1.tokens}, P2 tokens: {r.p2.tokens}')
print(f'P1 completion: {r.p1.completion_rate:.2f}, P2 completion: {r.p2.completion_rate:.2f}')
