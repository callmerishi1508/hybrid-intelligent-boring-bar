import zipfile
import pathlib
import re
p = pathlib.Path(r'c:\Project 7\boring_bar.slx.zip')
with zipfile.ZipFile(p) as z:
    values = set()
    for name in z.namelist():
        if name.endswith('.xml'):
            text = z.read(name).decode('utf-8', errors='ignore')
            values.update(('Version', m) for m in re.findall(r'<P Name="Version" Class="char">([^<]+)</P>', text))
            values.update(('LibraryVersion', m) for m in re.findall(r'<P Name="LibraryVersion">([^<]+)</P>', text))
    for k, v in sorted(values):
        print(k, v)
