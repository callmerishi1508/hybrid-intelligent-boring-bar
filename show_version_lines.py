import zipfile
import pathlib
import re
p = pathlib.Path(r'c:\Project 7\boring_bar.slx.zip')
with zipfile.ZipFile(p) as z:
    for name in z.namelist():
        if name.endswith('.xml'):
            data = z.read(name).decode('utf-8', errors='ignore')
            lines = data.splitlines()
            matches = [line for line in lines if 'R2026a' in line or '26.0.0' in line or '26001000' in line]
            if matches:
                print('---', name, '---')
                for line in matches:
                    print(line)
                print()
