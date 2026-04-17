import ast, sys

for f in ['services/news_fetcher_service.py', 'main.py']:
    try:
        ast.parse(open(f, encoding='utf-8').read())
        print(f'SYNTAX OK  {f}')
    except Exception as e:
        print(f'SYNTAX ERROR {f}: {str(e)}')
        sys.exit(1)
