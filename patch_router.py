import re

with open('E:/juhuo/judgment/router.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''        # P1改进：验证层 - 自我反驳（critical模式自动验证）
        if complexity == "critical":
            verifier = _get_verifier()
            verification = verifier.verify(_ret)
            _ret["meta"]["verification"] = verification
    except Exception:'''

new = '''        # P1改进：验证层 - 自我反驳（critical模式自动验证）
        if complexity == "critical":
            verifier = _get_verifier()
            verification = verifier.verify(_ret)
            _ret["meta"]["verification"] = verification
            
            # P0改进：因果推断 - 给判断提供推理底座
            inference_engine = CausalInferenceEngine()
            causal_infer = inference_engine.infer(
                situation=original_task,
                judgment_dimensions=must + important
            )
            _ret["causal_memory"]["causal_inference"] = {
                "best_explanation": causal_infer.best_explanation,
                "reasoning_chain": causal_infer.reasoning_chain,
                "confidence": causal_infer.confidence,
                "needs_more_data": causal_infer.needs_more_data,
                "hypotheses_count": len(causal_infer.hypotheses)
            }
    except Exception:'''

if old in content:
    content = content.replace(old, new)
    with open('E:/juhuo/judgment/router.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK - causal inference added')
else:
    print('Pattern not found')
