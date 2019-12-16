#!/usr/pin/python
import pandas as pd
import numpy as np
import array
import os.path
import json
from ..utils import instance_path
from ..scrape import hae_dataa
from glob import glob
from contextlib import suppress

instancepath = instance_path() / "yle_scrape"
instancepath.mkdir(exist_ok=True)




def attach_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    attached scraped data to data frame
    """
    # load in parties and constituents data
    # if data is missing ask if scraping is wanted to be performed

    with open(os.path.join(instancepath, f"parties.json"), "r", encoding='utf-8') as json_file:
        parties = json.load(json_file)
    with open(os.path.join(instancepath, f"constituencies.json"), "r", encoding='utf-8') as json_file:
        constituencies = json.load(json_file)
    

    """    #tätä glob hommaa en saanu toimiin, käy for loopin sisäl vaan yhen kerran ja hakee vaan yhden tiedoston
    # load the scraped data to its own data frame
    df_scraped = pd.DataFrame(columns=['first_name', 'last_name', 'election_number', 'image', 'election_promise_1', 'party', 'constituency'])
    i = 1
    with suppress(KeyError,FileNotFoundError):
        for filename in glob(f"{instancepath}/candidate*.json"):
            print("jee")
            with open(filename, "r", encoding='utf-8') as json_file:
                candidate = json.load(json_file)
                party_name = None
                constituency_name = None
                for part in parties:
                    if part['id'] == candidate["party_id"]:
                        party_name = part['name_fi']

                for consti in constituencies:
                    if consti['id'] == candidate["constituency_id"]:
                        constituency_name = consti['name_fi']

                df_scraped = df_scraped.append({'first_name': candidate['first_name'], 
                    'last_name': candidate['last_name'], 
                    'election_number': candidate['election_number'], 
                    'image': candidate['image'], 
                    'election_promise_1': candidate['info']['election_promise_1'],
                    'party': party_name,
                    'constituency': constituency_name}, 
                    ignore_index = True)
        #except (FileNotFoundError, KeyError):
    """

    # load the scraped data to its own data frame
    df_scraped = pd.DataFrame(columns=['first_name', 'last_name', 'election_number', 'image', 'election_promise_1', 'party', 'constituency'])
    i = 1
    while i <= 3000: # files are named arfter candidate ids and ids range is between 1 and 3000
        with suppress(KeyError,FileNotFoundError):
            with open(os.path.join(instancepath, f"candidate" + str(i) + ".json"), "r", encoding='utf-8') as json_file:
                candidate = json.load(json_file)
                party_name = None
                constituency_name = None
                for part in parties:
                    if part['id'] == candidate["party_id"]:
                        party_name = part['name_fi']

                for consti in constituencies:
                    if consti['id'] == candidate["constituency_id"]:
                        constituency_name = consti['name_fi']

                df_scraped = df_scraped.append({
                    'first_name': candidate['first_name'].strip(), 
                    'last_name': candidate['last_name'].strip(), 
                    'election_number': candidate['election_number'], 
                    'image': candidate['image'], 
                    'election_promise_1': candidate['info']['election_promise_1'],
                    'party': party_name.strip(),
                    'constituency': constituency_name}, 
                    ignore_index = True)
        i += 1


    # loading in data of each individual constituent
    # the ids range from 1 to 14
    j = 1
    constituentArray = []
    constituentArray.append("")
    while j <= 14:
        try:
            with open(os.path.join(instancepath, f'constituent' + str(j) + '.json'), "r", encoding='utf-8') as json_file:
                constituentArray.append(json.load(json_file))
        except FileNotFoundError:
            constituentArray.append("")
        j += 1

    for i, row in df.iterrows():
        promise = row['Mitkä ovat kolme vaalilupaustasi? Vaalilupaus 1:']
        constituency = row['vaalipiiri']
        party = row['party']
        df = search_andsetvalues(promise, constituency, party, df, i, df_scraped)
    return df


def search_andsetvalues(promise, constituency, party, df: pd.DataFrame, i, df_scraped) -> pd.DataFrame:
    """
    search values from the scraped data and set values in the dataframe to those found in the scraped data
    """
    candidates = df_scraped.loc[(df_scraped['constituency'] == constituency) & (df_scraped['party'] == party)] #& 

    for j, row in candidates.iterrows():
        if compare_promises(row["election_promise_1"]["fi"], row["election_promise_1"]["se"], 
            row["election_promise_1"]["en"], promise):
            df.at[i,'name'] = row["first_name"] + " " + row["last_name"]
            df.at[i, 'number'] = str(row["election_number"]) 
            df.at[i,'image'] = "https://ehdokaskone.yle.webscale.fi/" + row['image']
    return df


def format_promise(promise):
    return promise.replace('"', '').replace("\n",'').replace("\\", '').replace("/",'').strip()


def compare_promises(fi, se, en, ref) -> bool:
    """
    compare promises from scraped data and dataframe, if the same promise is found return true
    """
    same = False
    if (fi == ref):
        return True
    if (fi != None):
        if (fi == ref) or (format_promise(fi) == format_promise(ref)):
            return True
    if (se == ref):
        return True
    if (en == ref):
        return True
    if (se != None):
        if (se == ref) or (format_promise(se) == format_promise(ref)):
            return True
    return same 


if __name__ == "__main__":
    print("combine.py main does nothing currently by itself")