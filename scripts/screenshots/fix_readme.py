import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'e:\Luna\README.md', encoding='utf-8') as f:
    text = f.read()

# Build search strings from codepoints — no literal curly quotes that could get mangled
# Confirmed via: print codepoints for chars 2-5 of lines 181, 188
vision_bad = chr(0x00F0) + chr(0x0178) + chr(0x2018) + chr(0x0081)  # -> 👁
jwt_bad    = chr(0x00F0) + chr(0x0178) + chr(0x201D) + chr(0x0090)  # -> 🔐

fixes = [
    (vision_bad, '\U0001F441'),
    (jwt_bad,    '\U0001F510'),
]

for bad, good in fixes:
    count = text.count(bad)
    print(f'  {count}x -> {good}')
    text = text.replace(bad, good)

with open(r'e:\Luna\README.md', 'w', encoding='utf-8') as f:
    f.write(text)
print('Done')
