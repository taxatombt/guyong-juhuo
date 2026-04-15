import os
size = os.path.getsize('logo.svg')
print('size:', size)
with open('logo.svg', 'rb') as f:
    data = f.read(300)
print(data[:200])
