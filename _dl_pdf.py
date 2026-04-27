import urllib.request, ssl, os

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Try different URLs
urls = [
    "https://raw.githubusercontent.com/alchaincyf/hermes-agent-orange-book/main/Hermes-Agent-%E4%BB%8E%E5%85%A5%E9%97%A8%E5%88%B0%E7%B2%BE%E9%80%9A-v260407.pdf",
    "https://github.com/alchaincyf/hermes-agent-orange-book/raw/main/Hermes-Agent-%E4%BB%8E%E5%85%A5%E9%97%A8%E5%88%B0%E7%B2%BE%E9%80%9A-v260407.pdf",
]

os.makedirs("E:/juhuo/skills/hermes-orange-book", exist_ok=True)
out = "E:/juhuo/skills/hermes-orange-book/Hermes-Agent-从入门到精通-v260407.pdf"

for url in urls:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            data = r.read()
        if data[:4] == b'%PDF':
            open(out, "wb").write(data)
            print("OK: {} bytes -> {}".format(len(data), out))
        else:
            print("Not a PDF ({}): {}".format(data[:50], url))
        break
    except Exception as e:
        print("Error {}: {}".format(type(e).__name__, e))
