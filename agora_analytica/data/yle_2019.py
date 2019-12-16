"""

YLE EDUSKUNTAVAALIT 2019
~~~~~~~~~~~~~~~~~~~~~~~~

Functions for processing data from Yle Eduskuntavaalit 2019.

"""

import logging
# `BytesIO` tarjoaa liiman, jolla voidaan virtuaalisena tiedostona antaa
# bittijono luettavaksi functiolle, joka odottaa tiedostokuvaajaa.
from io import BytesIO
# Vaalidata on zip tiedosto, se pitää purkaa jotenkin.
from zipfile import ZipFile

import numpy as np
# tarvitaan `pandas` kirjasto
import pandas as pd
# Käytetään `requests` kirjastoa noutamaan data.
import requests

import re
from collections import Counter

from .utils import _instance_path, generate_names
from . import DataSetInstance

from .interpolation.combine import attach_data
from .scrape import hae_dataa

from .. import config


logger = logging.getLogger(__name__)

DATASET_URL = "https://vaalit.beta.yle.fi/avoindata/avoin_data_eduskuntavaalit_2019.zip"
DATASET_NAME = "Avoin_data_eduskuntavaalit_2019_valintatiedot.csv"

# Dataset default path
DATASET_PATH = _instance_path(DATASET_NAME)

Config = config()

# column to use for dataframe index.
INDEX = "key"

class Yle2019E(DataSetInstance):

    # Columns in linear scale. Constructed as triples or tuples:
    # `start`, `stop`, `filtering rule`
    _linear_space = [
        ("Suomen pitää olla edelläkävijä ilmastonmuutoksen vastaisessa taistelussa, vaikka se aiheuttaisi suomalaisille kustannuksia.", "On oikein nähdä vaivaa sen eteen, ettei vahingossakaan loukkaa toista."),
        ("Uusimaa. Kaatolupia on myönnettävä nykyistä enemmän susikannan rajoittamiseksi.", "Uusimaa. Metro tulee jatkaa Helsingistä Sipooseen.", ("constituency", "Uudenmaan vaalipiiri")),
        ("Helsinki. Kun Helsinki sulkee hiilivoimaloita, voidaan korvaavaa energiaa tuottaa ydinvoimalla.", "Helsinki. Metro tulee jatkaa Helsingistä Sipooseen.", ("constituency", "Helsingin vaalipiiri")),
        ("Varsinais-Suomi. Kaatolupia on myönnettävä nykyistä enemmän susi-, merimetso- ja hyljekantojen rajoittamiseksi.", "Varsinais-Suomi. Saariston yhteysalusliikenteen jatkuvuuden turvaamiseksi liikenteen tulisi olla maksullista kesäasukkaille ja matkailijoille.", ("constituency", "Varsinais-Suomen vaalipiiri")),
        ("Satakunta. Satakuntaan tulisi rakentaa runsaasti lisää tuulivoimaloita.", "Satakunta. Porin lentokentän henkilöliikenteen tukeminen olisi rahan haaskausta.", ("constituency", "Satakunnan vaalipiiri")),
        ("Ahvenanmaa. Ahvenanmaan erivapauksia on rajoitettava.", "Ahvenanmaa. Ahvenanmaan demilitarisointi tulisi ottaa uudelleen pohdintaan Itämerellä kasvaneen sotilaallisen aktiivisuuden vuoksi.", ("constituency", "Ahvenanmaan maakunnan vaalipiiri")),
        ("Häme. Hämeeseen ei saa avata yhtään uutta kaivosta ennen kuin yhtiöiltä aletaan periä kaivosveroa.", "Häme. Tietulleja voidaan kerätä Hämeen teiden kunnossapidon parantamiseksi.", ("constituency", "Hämeen vaalipiiri")),
        ("Pirkanmaa. Tampereen ei pidä enää antaa täyttää järvien rantoja rakentamista varten.", "Pirkanmaa. Helsinki-Tampere-junayhteyttä on parannettava niin, että juna kulkee kaupunkien välin vain tunnissa.", ("constituency", "Pirkanmaan vaalipiiri")),
        ("Kaakkois-Suomi. Saimaan luontoarvoista voidaan tinkiä, jotta kaivosteollisuuteen syntyisi uusia työpaikkoja.", "Kaakkois-Suomi. Parikkalan rajanylityspaikka tulee avata kansainväliselle liikenteelle.", ("constituency", "Kaakkois-Suomen vaalipiiri")),
        ("Savo-Karjala. Jos koululaisen koulumatkan pituus on yli tunnin suuntaansa, on yhtenä päivänä viikossa oltava mahdollisuus etäkoulunkäyntiin.", "Savo-Karjala. Raitiotieliikenne on realistinen tapa parantaa julkista liikennettä Itä-Suomessa.", ("constituency", "Savo-Karjalan vaalipiiri")),
        ("Vaasa. Kaatolupia on myönnettävä nykyistä enemmän susi-, merimetso- ja hyljekantojen rajoittamiseksi.", "Vaasa. Maahanmuuttoa pitää lisätä, jotta maakuntien reunakunnissakin riittäisi asukkaita ja työvoimaa.", ("constituency", "Vaasan vaalipiiri")),
        ("Keski-Suomi. Jyväskylän kaupunginteatterin ja museoiden kunnostamiseen on seuraavalla hallituskaudella ohjattava merkittäviä valtionavustuksia.", "Keski-Suomi. Jyväskylän on saatava nykyistä enemmän valtiontukea joukkoliikenteensä järjestämiseen.", ("constituency", "Keski-Suomen vaalipiiri")),
        ("Oulun vaalipiiri. Valtion pitää vähentää selvästi omistusosuuttaan Sotkamon Talvivaarassa kaivostoimintaa harjoittavasta Terrafame-yhtiöstä.", "Oulun vaalipiiri. Oulusta on tällä vuosikymmenellä tullut entistä turvattomampi paikka elää.", ("constituency", "Oulun vaalipiiri")),
        ("Lappi. Lappiin ei saa avata yhtään uutta kaivosta ennen kuin yhtiöiltä aletaan periä kaivosveroa.", "Lappi. Jäämeren rata pitää rakentaa.", ("constituency", "Lapin vaalipiiri")),
    ]

    _text_space = [
        ("Suomen pitää olla edelläkävijä ilmastonmuutoksen vastaisessa taistelussa, vaikka se aiheuttaisi suomalaisille kustannuksia.1", "On oikein nähdä vaivaa sen eteen, ettei vahingossakaan loukkaa toista.1"),
        ("Mitkä ovat kolme vaalilupaustasi? Vaalilupaus 1:", "Mitkä ovat kolme vaalilupaustasi? Vaalilupaus 3:"),
        ("Miksi juuri sinut pitäisi valita eduskuntaan?", "Miksi juuri sinut pitäisi valita eduskuntaan?"),
        ("Uusimaa. Kaatolupia on myönnettävä nykyistä enemmän susikannan rajoittamiseksi.1","Uusimaa. Metro tulee jatkaa Helsingistä Sipooseen.1"),
        ("Helsinki. Kun Helsinki sulkee hiilivoimaloita, voidaan korvaavaa energiaa tuottaa ydinvoimalla.1","Helsinki. Metro tulee jatkaa Helsingistä Sipooseen.1"),
        ("Varsinais-Suomi. Kaatolupia on myönnettävä nykyistä enemmän susi-, merimetso- ja hyljekantojen rajoittamiseksi.1","Varsinais-Suomi. Saariston yhteysalusliikenteen jatkuvuuden turvaamiseksi liikenteen tulisi olla maksullista kesäasukkaille ja matkailijoille.1"),
        ("Satakunta. Satakuntaan tulisi rakentaa runsaasti lisää tuulivoimaloita.1","Satakunta. Porin lentokentän henkilöliikenteen tukeminen olisi rahan haaskausta.1"),
        ("Ahvenanmaa. llmastonmuutoksen hillitsemiseen tähtäävät toimet eivät saa vaikeuttaa Ahvenanmaan talouskasvua.1","Ahvenanmaa. Ahvenanmaan demilitarisointi tulisi ottaa uudelleen pohdintaan Itämerellä kasvaneen sotilaallisen aktiivisuuden vuoksi.1"),
        ("Häme. Hämeeseen ei saa avata yhtään uutta kaivosta ennen kuin yhtiöiltä aletaan periä kaivosveroa.1","Häme. Tietulleja voidaan kerätä Hämeen teiden kunnossapidon parantamiseksi.1"),
        ("Pirkanmaa. Tampereen ei pidä enää antaa täyttää järvien rantoja rakentamista varten.1","Pirkanmaa. Helsinki-Tampere-junayhteyttä on parannettava niin, että juna kulkee kaupunkien välin vain tunnissa.1"),
        ("Kaakkois-Suomi. Saimaan luontoarvoista voidaan tinkiä, jotta kaivosteollisuuteen syntyisi uusia työpaikkoja.1","Kaakkois-Suomi. Parikkalan rajanylityspaikka tulee avata kansainväliselle liikenteelle.1"),
        ("Savo-Karjala. Jos koululaisen koulumatkan pituus on yli tunnin suuntaansa, on yhtenä päivänä viikossa oltava mahdollisuus etäkoulunkäyntiin.1","Savo-Karjala. Raitiotieliikenne on realistinen tapa parantaa julkista liikennettä Itä-Suomessa.1"),
        ("Vaasa. Kaatolupia on myönnettävä nykyistä enemmän susi-, merimetso- ja hyljekantojen rajoittamiseksi.1","Vaasa. Maahanmuuttoa pitää lisätä, jotta maakuntien reunakunnissakin riittäisi asukkaita ja työvoimaa.1"),
        ("Keski-Suomi. Jyväskylän kaupunginteatterin ja museoiden kunnostamiseen on seuraavalla hallituskaudella ohjattava merkittäviä valtionavustuksia.1","Keski-Suomi. Jyväskylän on saatava nykyistä enemmän valtiontukea joukkoliikenteensä järjestämiseen.1"),
        ("Oulun vaalipiiri. Valtion pitää vähentää selvästi omistusosuuttaan Sotkamon Talvivaarassa kaivostoimintaa harjoittavasta Terrafame-yhtiöstä.1","Oulun vaalipiiri. Oulusta on tällä vuosikymmenellä tullut entistä turvattomampi paikka elää.1"),
        ("Lappi. Lappiin ei saa avata yhtään uutta kaivosta ennen kuin yhtiöiltä aletaan periä kaivosveroa.1","Lappi. Jäämeren rata pitää rakentaa.1"),
    ]

    def linear_answers(self):
        df = self.copy()._convert_linear_into_int()._collect_columns(self._linear_space)

        return df

    def text_answers(self):
        df = self._collect_columns(self._text_space)
        df.replace(np.nan, "", inplace=True)
        return df

    def _collect_columns(self, columns):
        answers = Yle2019E(index=self.index, columns=[])

        # Collect suitable columns, based of filtering rules.
        for cols in columns:
            matrix = self.loc[:, cols[0]:cols[1]]
            answers = answers.join(matrix)

        return answers

    def _convert_linear_into_int(self):
        """ Converts linear values into :type:`np.int`

        Responsible for converting correct, but skipped, "constituency" answers into an int `3`.
        """

        for cols in self._linear_space:
            if len(cols) == 3:
                f, t, i = cols

                matrix = self.loc[self[i[0]] == i[1], f:t]
                self.loc[self[i[0]] == i[1], f:t] = matrix.fillna(np.int(3)).astype('int')
            else:
                f, t = cols
                matrix = self.loc[:, f:t].fillna(np.int(3)).astype('int')
                self.loc[:, f:t] = matrix
        return self


def download_dataset(filepath=DATASET_PATH, url=DATASET_URL, **kwargs) -> pd.DataFrame:
    """
    Download dataset

    :param: file  Output filename
    """

    kwargs.setdefault("session", requests.Session())

    r = kwargs['session'].get(url)

    # Jos lataus epäonnistuu, epäonnistu nyt.
    # `raise_for_status()` tarkastaa onko webpalvelin palauttanut
    # tiedoston vai ei, ja onko se ladattu onnistuneesti.
    # Nimensä mukaan aiheuttaa keskeytyksen - raise - jos virhe havaittiin.
    r.raise_for_status()

    if r.headers['content-type'] != "application/zip":
        raise ConnectionError(f"Expected zip file, received {r.headers['content-type']}")

    with ZipFile(BytesIO(r.content)) as pakattu_tiedosto:
        # Avataan saatu data Bitteinä, tällöin meidän ei tarvitse tallettaa
        # zip tiedostoa tiedostojärjestelmään odottamaan.

        # Puretaan haluttu tiedosto, ja kääritään pandan dataframen ympärille.
        data = pd.read_csv(BytesIO(pakattu_tiedosto.read(DATASET_NAME)))

        data.to_csv(filepath, index_label=INDEX)
        logger.debug("File downloaded as: %s", filepath)

    # Scrape extra bits.
    if Config.getboolean("build", "allow_dirty", fallback=False):
        hae_dataa()

    return data

def delete_empty_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Delete rows that are "empty" (those who didn't answer any questions) 
    Done by checking if all the answers on a given row are either "-" or float type (nan value is float type)
    Also counts new indexes after deleting rows, so there isn't missing in-between index numbers
    """
    
    df2 = df.loc[:, 'Suomen pitää olla edelläkävijä ilmastonmuutoksen vastaisessa taistelussa, vaikka se aiheuttaisi suomalaisille kustannuksia.':'On oikein nähdä vaivaa sen eteen, ettei vahingossakaan loukkaa toista.'].join(df.loc[:, 'Uusimaa. Kaatolupia on myönnettävä nykyistä enemmän susikannan rajoittamiseksi.':])
    for i, row in df2.iterrows():
        isnan = True
        isempty = True
        j = 0
        lenght = len(row)
        while ((isnan or isempty) and (j < lenght)):
            isnan = isinstance(row[j], float)
            isempty = row[j] == "-"
            j += 1
        if (isnan or isempty):
            df = df.drop(i)

    # Make new indexes after deleting rows
    df.reset_index(drop=True, inplace=True)
    df.columns = df.columns.map(_clean_column)
    
    return df

def load_dataset(filename: str = DATASET_PATH) -> pd.DataFrame:
    """ Read dataset """
    
    # Warn if dataset has been previously opened
    key = f"{__name__}.{filename}"
    dataset_loaded = globals().setdefault(key, False)

    if dataset_loaded:
        logger.warning(f"Dataset {filename!r} opened multiple times.")
    else:
        globals()[key] = True

    df = pd.read_csv(filename)
    df = process_data(df)
    return df


def process_data(df: pd.DataFrame) -> Yle2019E:
    """
    Run processing functions for data.
    """
    logger.debug("Processing data... ")
    df = Yle2019E(df)

    df = delete_empty_rows(df)

    df.columns = df.columns.map(_clean_column)
    df = df.rename(columns={
        "puolue": "party",
        "vaalipiiri": "constituency"
    })


    # attach scraped data to dataframe
    if Config.getboolean("build", "allow_dirty", fallback=False):
        try:
            df = attach_data(df)
        except Exception as e:
            logger.exception(e)
            logger.warning("Could not extend dataset with scraped data.")

    # Replace with np.NaN, as Yle is using "-" to indicate skipped and no opinion
    # values
    df = df.replace("-", np.NaN)

    # Add fake data
    if "name" not in df.columns:
        logger.debug("Names are missing. Generating fake names.")
        names = pd.Series(generate_names(df.shape[0]), name="name")
        df = df.assign(name=names)

    if "number" not in df.columns:
        numbers = Counter()
        df["number"] = pd.Series(dtype=np.str)
        for i, r in df.iterrows():
            numbers[r['constituency']] += 1
            df.loc[i, 'number'] = str(numbers[r['constituency']])

    #deleting the leftover candidates we can't identify (only 2 at this point)
    df = df[df['number'] != str(None)]

    df = _convert_linear_into_int(df)
    return df


def _clean_column(x):
    """ Clean string. """
    # Remove line endings.
    x = x.replace("\n", "")
    # Strip extra spaces and commas
    x = re.sub(r"\.(\s*\.+)", r".", x)
    return _clean_string(x)


def _clean_string(x):
    if isinstance(x, (np.str, str)):
        x = re.sub(r'(\s)\s+', r'\1', x)
        x = x.strip()

    return x

def _convert_linear_into_int(df: Yle2019E) -> pd.DataFrame:
    """ Converts linear values into :type:`np.int` """

    for cols in df._linear_space:
        if len(cols) == 3:
            f, t, i = cols

            matrix = df.loc[df[i[0]] == i[1], f:t]
            df.loc[df[i[0]] == i[1], f:t] = matrix.fillna(np.int(3)).astype('int')
        else:
            f, t = cols
            matrix = df.loc[:, f:t].fillna(np.int(3)).astype('int')
            df.loc[:, f:t] = matrix
    return df



if __name__ == "__main__":
    print(f"Loading dataset from: {DATASET_PATH}")
    dataset = load_dataset()
    size = dataset.shape[0]
    print(f"Number of entries: {size}")
