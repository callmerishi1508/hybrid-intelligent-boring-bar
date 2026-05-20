import pandas as pd
from pathlib import Path

paths = [
    Path('output/simscape_export_clean.csv'),
    Path('output/u_cnn_timeseries.csv'),
    Path('output/integrated_control.csv'),
]

dfs = []
for p in paths:
    df = pd.read_csv(p)
    df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
    df = df.sort_values('timestamp').reset_index(drop=True)
    dfs.append(df)

merged = dfs[0]
for df in dfs[1:]:
    merged = pd.merge_asof(
        merged,
        df,
        on='timestamp',
        direction='nearest',
        tolerance=1e-4,
        suffixes=('','_y'),
    )
    merged = merged.drop(columns=[c for c in merged.columns if c.endswith('_y') and c[:-2] in merged.columns])

print('merged cols', list(merged.columns))
print('u_cnn count', int(merged['u_cnn'].notna().sum()))
print('u_act count', int(merged['u_act'].notna().sum()))
print('sample with u_cnn non-null:')
print(merged.loc[merged['u_cnn'].notna(), ['timestamp','x_sensor','u_hinf','u_cnn','u_act']].head(5).to_string(index=False))
print('sample merged rows:')
print(merged[['timestamp','x_sensor','u_hinf','u_cnn','u_act']].head(10).to_string(index=False))
