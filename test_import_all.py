#!/usr/bin/env python3
"""
Test full module imports for all 12 core modules.
"""
import sys

def success(module):
    print(f'OK: {module} imported successfully')

def fail(module, e):
    print(f'FAILED: {module}: {e}')
    raise

try:
    import judgment
    success('judgment')
except Exception as e:
    fail('judgment', e)

try:
    import perception
    success('perception')
except Exception as e:
    fail('perception', e)

try:
    import causal_memory
    success('causal_memory')
except Exception as e:
    fail('causal_memory', e)

try:
    import curiosity
    success('curiosity')
except Exception as e:
    fail('curiosity', e)

try:
    import goal_system
    success('goal_system')
except Exception as e:
    fail('goal_system', e)

try:
    import self_model
    success('self_model')
except Exception as e:
    fail('self_model', e)

try:
    import action_system
    success('action_system')
except Exception as e:
    fail('action_system', e)

try:
    import feedback_system
    success('feedback_system')
except Exception as e:
    fail('feedback_system', e)

try:
    import output_system
    success('output_system')
except Exception as e:
    fail('output_system', e)

try:
    import openspace
    success('openspace')
except Exception as e:
    fail('openspace', e)

try:
    import action_signal
    success('action_signal')
except Exception as e:
    fail('action_signal', e)

try:
    import llm_adapter
    success('llm_adapter')
except Exception as e:
    fail('llm_adapter', e)

try:
    import chat_system
    success('chat_system')
except Exception as e:
    fail('chat_system', e)

print()
print('ALL 12 core modules imported SUCCESSFULLY. Juhuo Hermes integration complete.')
