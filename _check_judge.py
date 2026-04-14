import sys
sys.path.insert(0, 'E:/juhuo')

from judgment import JudgmentSystem
js = JudgmentSystem()
print("JudgmentSystem:", type(js))
print("router:", type(js.router))
print("dimensions:", list(js.dimensions.keys()) if hasattr(js, 'dimensions') else "N/A")

# 尝试实际调用judge
try:
    result = js.judge("今天吃火锅还是烧烤？")
    print("\njudge调用成功:")
    print(result)
except Exception as e:
    print(f"\njudge调用失败: {e}")
    # 看看router的实现
    import inspect
    print("\nrouter.judge源码:")
    print(inspect.getsource(js.router.judge)[:500])
