import sys
sys.path.insert(0, 'E:/juhuo')

from judgment import check10d
r = check10d('今天吃火锅还是烧烤')
print('check10d返回的keys:', list(r.keys()))
answers = r.get('answers', {})
print('\n已有answers:', {k:v for k,v in answers.items() if v})
print('\nquestions game_theory:', r.get('questions',{}).get('game_theory',[])[:2])
