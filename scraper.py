from bs4 import BeautifulSoup
import requests
import sqlite3
import pandas as pd
from multiprocessing import Pool
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

def scrap(uid):
    fields = "id,'NDC Description',NDC,NADAC_Per_Unit,Effective_Date,Pricing_Unit,Pharmacy_Type_Indicator,OTC,Explanation_Code,Classification_for_Rate_Setting,Corresponding_Generic_Drug_NADAC_Per_Unit,Corresponding_Generic_Drug_Effective_Date,'As of Date'"
    tdf = pd.DataFrame(columns=fields.split(','))

    print(f"Getting download link from {uid}")
    r = requests.get(f'https://data.medicaid.gov/api/1/metastore/schemas/dataset/items/1c5d0fc9-693a-534a-8240-4627d9362b0d?show-reference-ids=false')
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
        print("Downloading entries, currently at:", len(tdf.index))
        i += 10000
    return tdf

def main():
    chrome_options = webdriver.ChromeOptions()
    #chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(ChromeDriverManager().install(),chrome_options=chrome_options)
    wait = WebDriverWait(driver, 10)
    driver.get("https://www.medicaid.gov/medicaid/prescription-drugs/pharmacy-pricing/index.html")
    wait.until(EC.element_to_be_clickable((By.XPATH, "//select[@name='DataTables_Table_4_length']")))
    Select(driver.find_elements(By.XPATH, "//div[@class='dataTables_length']//select")[1]).select_by_value('-1')
    t = wait.until(EC.presence_of_element_located((By.XPATH, "//table[@class='medicaid-datatable medicaid-datatable-socrata dataTableId-87391 dataTable']")))
    html = t.get_attribute("outerHTML")


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


    with Pool() as pool:
        res = pool.imap_unordered(scrap,uids)
        for r in res:
            dfs.append(r)

    ttdf = pd.concat(dfs)
    ttdf.to_sql('NADAC', con, if_exists='replace', index=False)

if __name__ == '__main__':
    main()