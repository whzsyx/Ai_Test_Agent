import os

def count_lines(filepath):
    code = blanks = comments = 0
    in_block = False
    ext = os.path.splitext(filepath)[1].lower()
    single_comment = ''
    ml_start = ''
    ml_end = ''

    if ext in ('.py',):
        single_comment = '#'
        ml_start = '"""'
        ml_end = '"""'
    elif ext in ('.js', '.ts', '.vue', '.jsx', '.tsx', '.css', '.scss', '.less'):
        single_comment = '//'
        ml_start = '/*'
        ml_end = '*/'
    elif ext in ('.html',):
        ml_start = '<!--'
        ml_end = '-->'
    elif ext in ('.java', '.c', '.cpp', '.h', '.hpp'):
        single_comment = '//'
        ml_start = '/*'
        ml_end = '*/'
    elif ext in ('.sql',):
        single_comment = '--'
    elif ext in ('.yaml', '.yml', '.toml'):
        single_comment = '#'
    elif ext in ('.json', '.xml', '.md', '.txt', '.cfg', '.ini', '.gitignore', '.env', '.env.example'):
        return 0, 0, 0, 'skip'

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except:
        return 0, 0, 0, 'error'

    for line in lines:
        stripped = line.strip()
        if not stripped:
            blanks += 1
            continue

        if in_block:
            comments += 1
            if ml_end and ml_end in stripped:
                in_block = False
            continue

        if ml_start and ml_end and ml_start in stripped and ml_end in stripped:
            if stripped.startswith(ml_start) and stripped.endswith(ml_end):
                comments += 1
                continue

        if ml_start and ml_start in stripped:
            comments += 1
            in_block = True
            if ml_end and ml_end in stripped:
                in_block = False
            continue

        if single_comment and stripped.startswith(single_comment):
            comments += 1
            continue

        code += 1
    return code, blanks, comments, 'ok'

dirs = [
    r'G:\Code\Python\Python_selenium_test_Agent\Ai_Test_Agent\Enterprise_AI_QA_Agent\Agent_Server\src',
    r'G:\Code\Python\Python_selenium_test_Agent\Ai_Test_Agent\Enterprise_AI_QA_Agent\agent_web\src'
]

total_code = 0
for d in dirs:
    dir_code = 0
    dir_blanks = 0
    dir_comments = 0
    file_count = 0
    for root, dirs_, files in os.walk(d):
        skip_dirs = {'node_modules', '__pycache__', '.git', 'dist', '.vite', '.pytest_cache', '__pycache__'}
        parts = root.replace('\\', '/').split('/')
        if any(s in parts for s in skip_dirs):
            continue
        for f in files:
            fp = os.path.join(root, f)
            c, b, cm, status = count_lines(fp)
            if status == 'skip':
                continue
            dir_code += c
            dir_blanks += b
            dir_comments += cm
            if c > 0:
                file_count += 1
    name = os.path.basename(os.path.dirname(d)) + '/' + os.path.basename(d)
    print(f'--- {name} ---')
    print(f'  文件数:  {file_count}')
    print(f'  代码行:  {dir_code}')
    print(f'  空行:    {dir_blanks}')
    print(f'  注释行:  {dir_comments}')
    print()
    total_code += dir_code

print(f'{"="*30}')
print(f'总计有效代码行: {total_code}')
