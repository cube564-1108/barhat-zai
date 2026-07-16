#!/usr/bin/env python3
"""Update index.html with data from florist-quality-dashboard.html"""

import re
import sys

# Set stdout encoding to UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Read source file with data
with open('florist-quality-dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract allOrders
match = re.search(r'const allOrders = (\[.*?\]);', content, re.DOTALL)
if not match:
    print("ERROR: Cannot find allOrders")
    sys.exit(1)

all_orders_data = match.group(1)

# Read new index.html
with open('index.html', 'r', encoding='utf-8') as f:
    new_content = f.read()

# Replace ***DATA*** with real data
new_content = new_content.replace('***DATA***', all_orders_data)

# Save result
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("OK: index.html updated with data from florist-quality-dashboard.html")
print(f"Data size: {len(all_orders_data)} characters")
