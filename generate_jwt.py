import jwt
import time

# 替換為你的 Ghost Admin API Key
GHOST_ADMIN_KEY = "685e7058b488070001c4db7d:60b446a0f43b5a5b504867af5dd75ab873afd7aaf469ae58d6e7154fce4016b1"  # 格式: xxxx:yyyyyyyy...

# 分割金鑰
id, secret = GHOST_ADMIN_KEY.split(':')

# 生成 JWT
iat = int(time.time())
header = {'alg': 'HS256', 'typ': 'JWT', 'kid': id}
payload = {
    'iat': iat,
    'exp': iat + 300,  # 5分鐘有效
    'aud': '/admin/'
}
token = jwt.encode(payload, bytes.fromhex(secret), algorithm='HS256', headers=header)

print(f"生成的 JWT: {token}")
print(f"使用方式: curl -H 'Authorization: Ghost {token}' ...")

