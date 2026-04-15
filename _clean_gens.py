import os, shutil

# 清理所有 _gen_ / _make_ / _check_ / _read_ / _find_ 临时文件
count = 0
root = os.path.dirname(os.path.abspath(__file__))
for f in os.listdir(root):
    if f.startswith('_gen_') or f.startswith('_make_') or f.startswith('_check_') or f.startswith('_read_') or f.startswith('_find_'):
        path = os.path.join(root, f)
        if os.path.isfile(path):
            os.remove(path)
            print(f"DEL: {f}")
            count += 1
        elif os.path.isdir(path):
            shutil.rmtree(path)
            print(f"DEL dir: {f}")
            count += 1

# 清理 logo_preview 图片
for f in os.listdir(root):
    if f.startswith('logo_preview'):
        path = os.path.join(root, f)
        if os.path.isfile(path):
            os.remove(path)
            print(f"DEL img: {f}")
            count += 1

print(f"\nTotal cleaned: {count}")
