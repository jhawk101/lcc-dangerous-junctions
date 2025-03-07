import logging

import pandas as pd
import yaml
from yaml import Loader

logging.basicConfig(
    format="%(asctime)s - line %(lineno)s - %(levelname)s:%(message)s",
    level=logging.INFO,
)


def replace_code_with_values(df, schema, table, field):
    df[field] = df[field].astype(str)

    return df.replace(
        {
            field: schema.loc[
                (schema["table"] == table) & (schema["field name"] == field),
                ["code/format", "label"],
            ]
            .set_index("code/format")
            .to_dict()["label"]
        }
    )


def main():
    params = yaml.load(open("params_dft.yaml", "r"), Loader=Loader)

    # ====================== SCHEMA ===================================== #
    remote_schema_path = params["base_dft_url"] + params["schema_file_name"] + ".xlsx"
    local_schema_path = f"data_dft/{params['schema_file_name']}.csv"

    try:
        schema = pd.read_csv(local_schema_path)
        logging.info("loading schema locally")
    except FileNotFoundError:
        logging.info("downloading schema to save locally")
        schema = pd.read_excel(remote_schema_path)
        schema.to_csv(local_schema_path, index=False)

    schema["label"] = schema["label"].str.lower()

    logging.info("schema loaded")
    logging.info(schema.head())
    # ====================== COLLISIONS ===================================== #
    remote_collision_path = params["base_dft_url"] + params["collision_file_name"]
    local_collision_path = params["local_data_path"] + params["collision_file_name"]

    try:
        collisions = pd.read_csv(local_collision_path, low_memory=False)
        logging.info("loading collisions locally")
    except FileNotFoundError:
        logging.info("downloading collisions")
        collisions = pd.read_csv(remote_collision_path)
        collisions.to_csv(
            local_collision_path, index=False
        )  # TODO change to parquet and partition

    collision_cols = params["collision_columns"]
    cleaned_collisions = (
        collisions.query(f"accident_year>={params['min_data_year']}")[collision_cols]
        .pipe(
            replace_code_with_values, schema, "Accident", "local_authority_ons_district"
        )
        .pipe(replace_code_with_values, schema, "Accident", "accident_severity")
        .pipe(replace_code_with_values, schema, "Accident", "junction_detail")
        .assign(
            date=lambda x: pd.to_datetime(x["date"], format="mixed", dayfirst=True),
            year=lambda x: x["date"].dt.year,
        )
    )

    logging.info("Collision example rows:")
    logging.info(cleaned_collisions.head())

    # ====================== CASUALTIES ===================================== #

    remote_casualty_path = params["base_dft_url"] + params["casualty_file_name"]
    local_casualty_path = params["local_data_path"] + params["casualty_file_name"]

    try:
        casualties = pd.read_csv(local_casualty_path, low_memory=False)

    except FileNotFoundError:
        casualties = pd.read_csv(remote_casualty_path)
        casualties.to_csv(local_casualty_path, index=False)

    casualty_cols = params["casualty_columns"]

    cleaned_casualties = (
        casualties.query(f"accident_year>={params['min_data_year']}")[casualty_cols]
        .pipe(replace_code_with_values, schema, "Casualty", "casualty_class")
        .pipe(replace_code_with_values, schema, "Casualty", "casualty_severity")
        .pipe(replace_code_with_values, schema, "Casualty", "casualty_type")
    )

    logging.info("Casualty example rows:")
    logging.info(cleaned_casualties.head())

    # output data
    cleaned_casualties.to_parquet("data_dft/casualties.pq", index=False)
    cleaned_collisions.to_parquet("data_dft/collisions.pq", index=False)


if __name__ == "__main__":
    main()
