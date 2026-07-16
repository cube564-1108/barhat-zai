#!/usr/bin/env python3
"""Apply BARHAT brand styles to florist-quality-dashboard.html"""

import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Read the generated dashboard
with open('florist-quality-dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace old styles with BARHAT brand styles
replacements = [
    # Old background gradient
    ('background: linear-gradient(135deg, #667eea 0%, #764ba2 100%)', 'background: var(--barkhat-wine)'),

    # KPI cards
    ('background: linear-gradient(135deg, #667eea 0%, #764ba2 100%)', 'background: var(--barkhat-gradient)'),

    # Header colors
    ('color: #667eea', 'color: var(--barkhat-wine)'),
    ('border-bottom: 3px solid #667eea', 'border-bottom: 3px solid var(--barkhat-pink)'),

    # Filter select
    ('border: 2px solid #667eea', 'border: 2px solid var(--barkhat-pink)'),

    # Buttons
    ('border: 2px solid #764ba2', 'border: 2px solid var(--barkhat-pink)'),
    ('color: #764ba2', 'color: var(--barkhat-pink-deep)'),
    ('background: #764ba2', 'background: var(--barkhat-gradient)'),

    # Section headers
    ('color: #333', 'color: var(--barkhat-wine)'),

    # Badge colors (keep same, just ensure compatibility)
]

for old, new in replacements:
    html = html.replace(old, new)

# Add brand CSS links after </title> if not present
brand_css = '''    <link rel="stylesheet" href="/brand/tokens.css">
    <link rel="stylesheet" href="/brand/brand.css">'''

if '<link rel="stylesheet" href="/brand/' not in html:
    html = html.replace('</title>', f'</title>\n{brand_css}')

# Update header to show BARHAT
html = html.replace(
    '<h1>Отчет по качеству сборки букетов</h1>',
    '<h1>Отчет по качеству сборки букетов</h1>\n            <p>Салон цветов «Бархат»</p>'
)

# Add update button in filters section
update_button = '''            <button id="updateBtn" style="background: var(--barkhat-gradient); color: var(--barkhat-white); border: none; border-radius: 10px; padding: 10px 20px; font-weight: 500; cursor: pointer; display: flex; align-items: center; gap: 8px;">
                <span>🔄</span>
                <span>Обновить данные</span>
            </button>'''

if 'id="updateBtn"' not in html:
    html = html.replace('</select>\n        </div>', f'</select>\n{update_button}\n        </div>')

# Add update button script at the end of <script>
update_script = '''
        // Update button functionality
        document.getElementById('updateBtn').addEventListener('click', async function() {
            const btn = this;
            btn.disabled = true;
            btn.style.opacity = '0.6';

            try {
                const response = await fetch('/api/update-quality', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                const data = await response.json();

                if (response.ok && data.success) {
                    btn.innerHTML = '<span>✅</span><span>Обновлено!</span>';
                    setTimeout(() => window.location.reload(), 1500);
                } else {
                    throw new Error(data.error || 'Ошибка обновления');
                }
            } catch (error) {
                btn.disabled = false;
                btn.style.opacity = '1';
                alert('Ошибка: ' + error.message);
            }
        });'''

# Insert before </script>
html = html.replace('</script>', f'{update_script}\n    </script>')

# Save as index.html
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("OK: index.html updated with BARHAT brand styles and salon cards")
