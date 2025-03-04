import yaml
import pandas as pd

from sklearn.neighbors import BallTree
from yaml import Loader


def get_nearest_junction(row, tree):
    """
    Find nearest junction to crash / collision. Return distance and the index for junction
    """
    crash_coordinate = row[["latitude", "longitude"]].values
    result = tree.query([crash_coordinate])

    distance = result[0][0][0]  # result is weirdly nested
    index = result[1][0][0]
    return distance, index


def main():
    # read in data params
    params = yaml.load(open("params_dft.yaml", "r"), Loader=Loader)

    tolerance = params["tolerance"]
    distance_threshold = params["distance_to_junction_threshold"]

    # read in data
    collisions = (
        pd.read_parquet("data_dft/pedestrian-and-cyclist-collisions.pq")
        .rename(columns={"accident_index": "collision_index"})
        .dropna(subset=["latitude", "longitude"])
    )

    junctions = pd.read_parquet(f"data_dft/junctions-tolerance={tolerance}.parquet")

    # Find nearest junction to each collision
    # Use BallTree algorithm.
    # Havesine distance since these are coordinates.

    print("Finding nearest junction to each collision")
    tree = BallTree(
        junctions[["latitude_junction", "longitude_junction"]], metric="haversine"
    )

    collisions[["distance_to_junction", "junction_index"]] = collisions.apply(
        lambda row: get_nearest_junction(row, tree), axis=1, result_type="expand"
    )

    # join to get junction ids
    collisions = collisions.merge(
        junctions[["junction_index", "junction_id"]], how="left", on="junction_index"
    )

    # filter to those within certain distance
    collisions = collisions[collisions["distance_to_junction"] <= distance_threshold]

    collisions.to_csv(f"data_dft/collisions-tolerance={tolerance}.csv", index=False)
    collisions.to_parquet(
        f"data_dft/collisions-tolerance={tolerance}.parquet", engine="pyarrow"
    )


if __name__ == "__main__":
    main()
