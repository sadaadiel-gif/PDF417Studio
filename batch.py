import pandas as pd
from barcode import generate_barcode

def process_csv(file_path):
    df = pd.read_csv(file_path)

    for _, row in df.iterrows():
        img = generate_barcode(row["aamva"], columns=5, scale=3)
        img.save(f"output/{row['filename']}.png")