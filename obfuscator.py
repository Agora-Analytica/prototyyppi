#!/usr/bin/python3
"""
OBFUSCATOR
==========

Script responsible for obfuscating data for GDPR compliance.
"""

import click
from agora_analytica import instance_path
from agora_analytica.data.utils import generate_names
from agora_analytica.data.interpolation.wikidata import finnish_politicians
import pandas as pd

# Extra attributes to append into image url. By default wikipedia uses 300px wide
# images, so it's good enought for us.
IMAGE_URL_APPEND = "?width=300px"

@click.command()
@click.argument('file', type=click.Path(file_okay=True, dir_okay=False, exists=True), default=instance_path() / "nodes.json")
def cli_obfuscate(file):
    """ Obfuscate contents of node FILE """

    with open(file, mode="r+") as fp:
        df = pd.read_json(fp, orient="records")

        # Check for image using name
        images = politician_pictures()
        for idx, row in df.iterrows():
            name = row['name'].lower().strip()
            img = images.get(name, None)
            df.loc[idx, "image"] = img + IMAGE_URL_APPEND if img else None

        # Generate fake names
        df = fake_names(df)
        fp.truncate(0)
        fp.seek(0)
        df.to_json(fp, orient="records")
    pass


def politician_pictures():
    """ Return dictionary of politicians with images in wikipedia """
    politicians = finnish_politicians()
    politicians_map = {}
    for entry in politicians:
        image = entry.get("image", [None]).pop()
        if not image: continue

        # Combine different names
        names = list(map(lambda x: x.lower().strip(), entry["itemLabel"] + entry.get("itemAltLabel", [])))
        politicians_map.update(dict(zip(names, [image] * len(names))))

    return politicians_map


def fake_names(df):
    names = generate_names(df.shape[0])
    df['name'] = names
    return df

if __name__ == "__main__":
    #print()
    cli_obfuscate()
