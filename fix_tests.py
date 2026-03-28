import re

with open('e:/codes/AgentTrader/tests/unit/application/test_kline_sync_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('market="sh"', 'market=ExchangeKind.SSE')
content = content.replace('market="sz"', 'market=ExchangeKind.SZSE')
content = content.replace('market="sse"', 'market=ExchangeKind.SSE')
content = content.replace('market="szse"', 'market=ExchangeKind.SZSE')
content = content.replace('"sse"', 'ExchangeKind.SSE')
content = content.replace('"szse"', 'ExchangeKind.SZSE')

with open('e:/codes/AgentTrader/tests/unit/application/test_kline_sync_service.py', 'w', encoding='utf-8') as f:
    f.write(content)
