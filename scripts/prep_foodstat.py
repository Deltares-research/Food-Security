from pathlib import Path
import pandas as pd


def create_animal_yield_df(file_path: Path | str, output_file: Path | str) -> None:
    df = pd.read_csv(file_path)
    df = df[df["Element"] == "Yield/Carcass Weight"]
    df = df[["Area", "Element", "Item", "Unit", "Value"]]
    df.loc[df["Unit"] == "100 g/An", "Unit"] = 100
    df.loc[df["Unit"] == "0.1 g/An", "Unit"] = 0.1
    df["kg_per_animal"] = (df["Value"] * df["Unit"])/ 1000
    df["animal"] = df["Item"].apply(rename_item)
    df.to_csv(output_file)


def rename_item(item):
    animals = ["chicken", "goat", "sheep", "cattle", "duck", "pig", "horse", "buffalo"]
    for animal in animals:
        if animal in item.lower():
            return animal
    return item

if __name__ == "__main__":
    file_path = Path(r"C:\Users\jong\Projects\Food-Security-data\FOA_STAT_food_production.csv")
    output_file = Path(__file__).parent.parent / "data/animal_yield.csv" 
    create_animal_yield_df(file_path=file_path, output_file=output_file)

