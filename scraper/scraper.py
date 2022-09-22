from bs4 import BeautifulSoup
import requests
import sqlite3
import pandas as pd
from multiprocessing import Pool

def scrap(uid):
    fields = "id,'NDC Description',NDC,NADAC_Per_Unit,Effective_Date,Pricing_Unit,Pharmacy_Type_Indicator,OTC,Explanation_Code,Classification_for_Rate_Setting,Corresponding_Generic_Drug_NADAC_Per_Unit,Corresponding_Generic_Drug_Effective_Date,'As of Date'"
    tdf = pd.DataFrame(columns=fields.split(','))

    r = requests.get(f'https://data.medicaid.gov/api/1/metastore/schemas/dataset/items/{uid}?show-reference-ids=false')
    did = r.json()["distribution"][0]["identifier"]

    max = requests.get(f'https://data.medicaid.gov/api/1/datastore/sql?query=%5BSELECT%20COUNT%28%2A%29%20FROM%20{did}%5D').json()[0]['expression']
    print(f"This database has {max} entries")
    i = 0

    while i < int(max):

        r = requests.get(f'https://data.medicaid.gov/api/1/datastore/query/{did}?offset={i}&count=true&results=true&schema=true&keys=true&format=csv&rowIds=false')
        open(f"{uid}.csv", 'wb').write(r.content)
    

        df = pd.read_csv(f"{uid}.csv")
        df["id"] = uid
        cols = df.columns.tolist()
        cols = cols[-1:] + cols[:-1]
        df = df[cols]
        df.columns = fields.split(',')
        tdf = pd.concat([tdf, df])
        i += 10000
    return tdf

def main():
    with open("table.txt",'r') as f:
        html = f.read()
    con = sqlite3.connect("scraper.db")
    con.row_factory = lambda cursor, row: row[0]
    cur = con.cursor()

    fields = "id,'NDC Description',NDC,NADAC_Per_Unit,Effective_Date,Pricing_Unit,Pharmacy_Type_Indicator,OTC,Explanation_Code,Classification_for_Rate_Setting,Corresponding_Generic_Drug_NADAC_Per_Unit,Corresponding_Generic_Drug_Effective_Date,'As of Date'"

    cur.execute(f"CREATE TABLE IF NOT EXISTS NADAC ({fields})")
    cur.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
    index = cur.fetchone()

    if index == None:
        print("Creating an INDEX")
        cur.execute("CREATE INDEX id ON NADAC (id)")


    soup = BeautifulSoup(html, features='lxml')
    aas = soup.find_all("a")
    uids = []
    for a in aas:
        uids.append(a['href'].split('/')[4])

    uids = set(uids)
    dfs = []

    print("Starting now")
    with Pool() as pool:
        res = pool.imap_unordered(scrap,uids)
        for r in res:
            dfs.append(r)

    print("Finished scraping, saving to database")
    ttdf = pd.concat(dfs)
    ttdf.to_sql('NADAC', con, if_exists='replace', index=False)

if __name__ == '__main__':
    main()