#!/usr/bin/env python3

import logging
import os.path
import importlib
from io import BytesIO
from time import gmtime, strftime
from pathlib import Path
from zipfile import ZipFile
import re

from agora_analytica import (
    instance_path,
    config
)

from agora_analytica.analytics import measure_distances
from agora_analytica.analytics.text import TextTopics
from agora_analytica.data.interpolation.wikidata import finnish_parties
from agora_analytica.utils import clamp

import numpy as np

import click
from flask.json import dumps as jsonify

import urllib.request

logger = logging.getLogger(__name__)

debug = False

settings = config()


def _write(file, data, target=instance_path()):
    """ Helper to write data into json file """

    with open(os.path.join(target, f"{file}.json"), 'w') as f:
        f.write(jsonify(data, indent=(4 if debug else 0)))


@click.group()
@click.option("--debug/--no-debug", default=debug, help="Show debug output")
@click.option("--config", default=instance_path() / "app.cfg", help="Config file")
def cli(debug, config):
    globals()['debug'] = debug
    logging.basicConfig(level=(logging.DEBUG if debug else logging.INFO))
    settings.read(config)


@cli.command()
@click.option("--target", type=click.Path(file_okay=False),
                          default=(instance_path() / "..").resolve(),
                          show_default=True)
@click.option("--url", default=os.environ.get("INSTANCE_URL", None),
                       show_default=True)
def deploy(target: Path, url: str, force=False):
    """
    Retrieve new instance data and extract it.

    Performs simple "If-Modified-Since" check if existing instance data is found,
    and updates only if necessary.
    
    Instance file pointed in :param:`url` should be zip file, with all instance data
    inside `instance/` folder.

    :param target: Target folder where to extract instance data.
    :param url: Url where instance data is downloaded from. 

    """
    if url is None:
        raise click.BadParameter("Please set instance asset url in INSTANCE_URL enviroment variable")
    elif not re.match(r'^\w+://.*', url):
        url = f"http://{url}"

    if not isinstance(target, Path):
        target = Path(target)

    req = urllib.request.Request(url)

    # Check for existing instance deployment.
    _instance_path = target.joinpath("instance")
    if _instance_path.exists() and not force:
        logger.info("Instance path exists in folder %s, checking for update", _instance_path)
        m_time = _instance_path.stat().st_mtime
        req.add_header("If-Modified-Since", strftime("%a, %d %b %Y %I:%M:%S %Z", gmtime(m_time)))

    logger.debug("Retrieving instance folder from %s", url)
    try:
        with urllib.request.urlopen(req) as f:
            with ZipFile(BytesIO(f.read())) as instance_zip:
                instance_zip.extractall(target)
                logger.info("Instance data extracted.")
    except urllib.error.HTTPError as e:
        if e.code == 304:
            logger.info("Instance data not changed. Skipping update.")
        else:
            raise e


@cli.command()
@click.option("--target", type=click.Path(file_okay=False))
@click.option("--dataset-name", default="yle_2019", show_default=True)
def download(target, dataset_name):
    """
    Download dataset
    """

    dataset = importlib.import_module(f".{dataset_name}", "agora_analytica.data")

    dataset.download_dataset(target) if target else dataset.download_dataset()
    click.echo(f"Dataset downloaded")


@cli.command()
@click.option("--target", type=click.Path(file_okay=False),
                          default=instance_path(),
                          show_default=True)
@click.option("--method", type=click.Choice(['linear', 'dummy',  'multiselect']),
                          help="Distance approximation method.",
                          default="linear", multiple=True)
@click.option("--dataset-name", default="yle_2019", show_default=True)
@click.option("--limit", default=50)
@click.option("--number-of-topics", type=int,
                                    help="Number of topics for text analysis. Defaults to approximation",
                                    default=settings.get('build', 'number_of_topics', fallback=-1))
def build(target, method: list, dataset_name, limit: int, number_of_topics):
    """
    Build page.

    :param target: Target file
    :param method: List of methods to use.
    :param limit: Limit processing into N candidates.
    """

    click.echo("Loading dataset ... ", nl=False)

    dataset = importlib.import_module(f".{dataset_name}", "agora_analytica.data")
    df = dataset.load_dataset()

    if limit < 2:
        raise click.BadParameter("Build should include more than 2 candidates.", param_hint="--limit")

    preferred_list_file = settings.get("build", "preferred_candidates", fallback=None)

    if preferred_list_file:
        with open(preferred_list_file) as fp:
            # Fetch all preferred candidates by row, skipping ones beginning with `#`
            preferred_candidates = filter(lambda x: x != "" and x[0] != "#", map(str.strip, fp.readlines()))
        # Slice preferred candidates
        preferred_filter = df["name"].isin(preferred_candidates)
        preferred = df[preferred_filter]

        # Fill to a required ammount with sampled data
        df = preferred.append(df[~preferred_filter].sample(clamp(df.shape[0] - preferred.shape[0], limit - preferred.shape[0], 0)))
        del preferred, preferred_filter

    # sample to a correct size
    df = df.sample(min(limit, df.shape[0]))
    click.echo("[DONE]")

    click.echo("Calculating distances ... ", nl=False)
    distances = measure_distances(df, methods=method)
    click.echo("[DONE]")

    click.echo("Analyzing text ... ", nl=False)

    if number_of_topics == -1:
        # Using squareroot seems to provide pretty good default
        number_of_topics = settings.getint("build", "number_of_topics", fallback=np.sqrt(limit))
    number_of_topics = int(number_of_topics)
    settings.set("build", "number_of_topics", str(number_of_topics))

    click.echo(f"Topics: {number_of_topics} ", nl=False)

    texts_df = df.text_answers().sort_index()
    visualization = settings.getboolean('build', 'generate_visualization', fallback=debug)

    topics = TextTopics(texts_df, number_topics=number_of_topics, generate_visualization=visualization)
    words = {}

    n = texts_df.shape[0]

    talkinpoints = {}

    for a in range(n):
        a_idx = texts_df.index[a]
        for b in range(a + 1, n):
            b_idx = texts_df.index[b]
            r = topics.compare_rows(texts_df, a_idx, b_idx)
            if r:
                words[(a_idx, b_idx)] = r[0][1]
                words[(b_idx, a_idx)] = r[1][1]

        talkinpoints[a_idx] = topics.find_talkingpoint(texts_df.loc[a_idx])

    click.echo("[DONE]")

    click.echo("Generating structures ... ", nl=False)
    data_nodes = [{
        "id": int(idx),
        "name": row.get("name"),
        "party": row.get("party"),
        "image": row.get("image", None),
        "constituency": row.get("constituency"),
        "number": int(row.get("number", -1)),
        "talkinpoint": talkinpoints.get(int(idx), None)
    } for idx, row in df.replace(np.NaN, None).iterrows()]

    data_links = [{
        "source": int(i),
        "source_term": words.get((i, l), None),
        "distance": float(d),
        "target_term": words.get((l, i), None),
        "target": int(l)
    } for i, d, l in distances.values]
    click.echo("[DONE]")

    # Build static pages
    _build_pages(target / "pages")

    click.echo("Writing data ... ", nl=False)
    _write("nodes", data_nodes, target)
    _write("links", data_links, target)
    cfg = instance_path() / "app.cfg"
    with cfg.open('w') as f:
        settings.write(f, space_around_delimiters=True)
    click.echo("[DONE]")

@cli.command()
@click.option("--target", type=click.Path(file_okay=False),
                          default=instance_path() / "pages",
                          show_default=True)
def build_pages(target):
    """
    Build static pages.
    """
    click.echo("Writing pages ... ", nl=False)
    _build_pages(target)
    click.echo("[DONE]")
    return


def _build_pages(target):
    target.mkdir(exist_ok=True)
    # Generate about page from README.md
    from markdown import markdownFromFile
    markdownFromFile(input="README.md", output=str(target / "about.html"))


@cli.command()
@click.option("--target", type=click.Path(file_okay=False),
                          default=instance_path(),
                          show_default=True)
@click.option("--dataset-name", default="yle_2019", show_default=True)
def build_parties(target, dataset_name):
    """
    Build party data
    """
    from agora_analytica.data.interpolation.nearest import party_distances
    from colorsys import rgb_to_hls, hls_to_rgb

    dataset = importlib.import_module(f".{dataset_name}", "agora_analytica.data")

    df = dataset.load_dataset()
    answers = df.linear_answers()

    distance_matrix = party_distances(df, answers)

    parties = df["party"].unique()
    party_data = finnish_parties()

    r = []

    for party in parties:
        data = {}

        data = party_data.party(party)
        if data:
            logger.debug(f"Found party {data['itemLabel'][0]!r} for {party!r}")
        else:
            logger.debug(f"Did not found {party}")
            data = {
                "itemLabel": [party]
            }

        if "sRGB_color_hex_triplet" not in data:
            # If color is missing, generate one by looking nearest
            # two parties and calculating color between them.

            # TODO Take note of distances
            # Collect two colors
            colors = []
            for near_party, distance in distance_matrix[party]:
                if len(colors) >= 2:
                    continue
                _p = party_data.party(near_party)
                if _p and "sRGB_color_hex_triplet" in _p:
                    logger.debug("Found nearby party %s for color approximation", _p['itemLabel'])
                    colors.append(_p['sRGB_color_hex_triplet'][0])

            # Convert colors into hues
            hues = np.array([
                rgb_to_hls(*_hex_to_rgb(colors[0])),
                rgb_to_hls(*_hex_to_rgb(colors[1]))
            ])

            # Calculate mean for HLS, and convert back to hex
            data['sRGB_color_hex_triplet'] = [
                "%0.2X%0.2X%0.2X" % tuple(map(int, hls_to_rgb(*hues.mean(axis=0))))
            ]

        r.append(data)

    _write("parties", r, target)


def _hex_to_rgb(hex):
    return tuple(int(hex[i:i+2], 16) for i in (0, 2, 4))


if __name__ == "__main__":
    cli()
