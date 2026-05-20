import zipfile
import pathlib
from shutil import copyfile

src_zip = pathlib.Path(r'c:\Project 7\boring_bar.slx.zip')
dst_slx = pathlib.Path(r'c:\Project 7\boring_bar_R2025b.slx')

if dst_slx.exists():
    dst_slx.unlink()

with zipfile.ZipFile(src_zip, 'r') as zin, zipfile.ZipFile(dst_slx, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
    for name in zin.namelist():
        data = zin.read(name)
        if name in {
            'metadata/coreProperties.xml',
            'metadata/mwcoreProperties.xml',
            'metadata/mwcorePropertiesReleaseInfo.xml',
            'simulink/configSet0.xml',
            'simulink/systems/system_root.xml',
            'simulink/systems/system_61.xml',
            'simulink/systems/system_66.xml',
            'simulink/systems/system_73.xml',
        }:
            text = data.decode('utf-8', errors='ignore')
            text = text.replace('R2026a', 'R2025b')
            text = text.replace('26.0.0', '25.2.0')
            text = text.replace('26001000.2', '25002000.2')
            text = text.replace('26001000.1', '25002000.1')
            zout.writestr(name, text.encode('utf-8'))
        else:
            zout.writestr(name, data)
print('Created', dst_slx)
