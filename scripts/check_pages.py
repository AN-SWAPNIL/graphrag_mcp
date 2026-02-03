import re
p='d:/Term Files/Thesis/adnan_sir/Codes/FSM_Generator/files/core_spec.md'
with open(p, 'r', encoding='utf-8') as f:
    s=f.read()
nums=[int(m.group(1)) for m in re.finditer(r'Page\s+(\d+)', s)]
count=len(nums)
unique=sorted(set(nums))
missing=[n for n in range(1, max(unique)+1) if n not in unique]
print('total_occurrences:', count)
print('unique_pages_found:', len(unique), 'max_page:', max(unique))
print('missing_pages_count:', len(missing))
print('missing_pages:', missing)
# Also find positions (line numbers) where page footer is missing by checking expected pattern per page
# Print first 20 occurrences of duplicates or anomalies
from collections import Counter
c=Counter(nums)
dups=[p for p,k in c.items() if k>1]
print('duplicates_count:', len(dups))
if len(dups):
    print('some duplicated page numbers (first 20):', dups[:20])
# print context around missing pages
for mpage in missing[:50]:
    # try to find where the missing page should be by searching for the text 'Page <mpage-1>' and 'Page <mpage+1>' and print snippet
    a=re.search(r'(.{0,200}\bPage\s+%d.{0,200})'%(mpage-1), s)
    b=re.search(r'(.{0,200}\bPage\s+%d.{0,200})'%(mpage+1), s)
    print('\n--- around missing page', mpage)
    if a: print('before:', a.group(0)[:200])
    if b: print('after :', b.group(0)[:200])
