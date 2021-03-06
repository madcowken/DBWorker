import re
import pyodbc
import time
import numpy as np
from terminaltables import SingleTable

DB_FILE = r'N:\Data\DistributionSystem\DB_DistributionSystemInformation_Live_W7.mdb'

NORTH_DEMAND_DB = r'N:\Data\Demand\DB_Demand-North_ver2_Live_W7.mdb'

SOUTH_DEMAND_DB = r'N:\Data\Demand\DB_Demand-South_ver2_Live_W7.mdb'

TEMP_CONSTANT = {
  "0811": [-36, -30, -25, -20, -15, -10, -5, 0, 5, 10, 15, 20],
  "0341": [-40, -35, -30, -25, -20, -15, -10, -5, 0, 5, 10, 15],
  "0211": [-42, -35, -30, -25, -20, -15, -10, -5, 0, 5, 10, 15],
  "0411": [-41, -35, -30, -25, -20, -15, -10, -5, 0, 5, 10, 15],
  "0600": [-36, -30, -25, -20, -15, -10, -5, 0, 5, 10, 15, 20],
  "0700": [-37, -30, -25, -20, -15, -10, -5, 0, 5, 10, 15, 20],
  }

PHF_CONSTANT = {
  "0811": [1.15, 1.20, 1.24, 1.28, 1.32, 1.36, 1.40, 1.44, 1.48, 1.52, 1.56, 1.56],
  "0341": [1.10, 1.12, 1.15, 1.17, 1.20, 1.22, 1.25, 1.27, 1.30, 1.32, 1.35, 1.37],
  "0211": [1.07, 1.12, 1.16, 1.19, 1.23, 1.26, 1.30, 1.33, 1.37, 1.40, 1.44, 1.47],
  "0411": [1.06, 1.13, 1.18, 1.24, 1.29, 1.35, 1.40, 1.46, 1.51, 1.57, 1.62, 1.67],
  "0600": [1.12, 1.20, 1.26, 1.33, 1.39, 1.46, 1.52, 1.59, 1.65, 1.72, 1.78, 1.78],
  "0700": [1.08, 1.16, 1.21, 1.27, 1.32, 1.38, 1.43, 1.49, 1.54, 1.60, 1.65, 1.66],
  }

BP_CONSTANT = {
  "0811": 15.1,
  "0341": 14.3,
  "0211": 14.8,
  "0411": 14.3,
  "0600": 14.9,
  "0700": 15.7,
}

CALGARY_DS = "03-0032"

def print_info(DS, INTs, loads, temps, irri, HUC, customers):
  # DS, INTs, CLs, loads
  INTs = [[INT[0], INT[1] if INT[1] else 0, INT[2]] for INT in INTs]
  if sum([INT[1] for INT in INTs]) != 1.00 and len([INT[1] for INT in INTs]) > 1:
    table1 = [ ['Interconnection #', 'Split (%)', 'Weather Zone'] ] \
    + [[INT[0], "-", INT[2]] for INT in INTs] \
    + [ ["Total Splits:", "Check splits manually", ""] ]
    print(SingleTable(table1, title="Distribution System {0}".format(DS)).table)

  else:
    if len([INT[1] for INT in INTs]) == 1:
      INTs[0][1] = 1
    table1 = [ ['Interconnection #', 'Split (%)', 'Weather Zone'] ] \
    + [[INT[0], INT[1]*100, INT[2]] for INT in INTs] \
    + [ ["Total Splits:", sum([INT[1]*100 for INT in INTs]), ""] ]
    print(SingleTable(table1, title="Distribution System {0}".format(DS)).table)

  table2 = [ ['# of Irrigation Customers', '# of High Use Customers', 'Total # of Customers'] ] \
    + [ [irri, HUC, customers] ]
  print(SingleTable(table2, title="Number of Customers").table)

  table3 = [ ['Temperature', 'Load(GJ/d)'] ] \
  + zip(temps, np.round(loads, 2))
  print(SingleTable(table3, title="Loads at Different Temperatures").table)
  print('It took {0} seconds'.format(time.time()-start))

def ds_checker(value):
  return re.search(r'^[0-9]{2}-[0-9]{4}$', value)

def intt_checker(value):
  return re.search(r'^[0-9]{5}$', value)

def connectDB(db_file):
  odbc_conn = 'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)}; DBQ=%s' % (db_file)
  return pyodbc.connect(odbc_conn)

def find_all_int(conn, DS):
  query = """
    SELECT 
      INT.[Interconnection#],
      INT.[Split],
      INT.[WeatherZone]
    FROM
      (tblInterconnections AS [INT] LEFT JOIN tblOperatingSystem AS OS 
        ON INT.AssignedOperatingSystem = OS.[OS Unique ID])
    WHERE OS.[DS #] = ? and INT.[Status] = ?;
  """

  cursor = conn.cursor()
  cursor.execute(query, [DS, "Active"])
  INTs = cursor.fetchall()
  cursor.close()
  return INTs

def find_ds_by_int(conn, INT):
  query = """
    SELECT 
      OS.[DS #],
      DS.[System Configuration]
    FROM 
      (tblInterconnections AS [INT]
    INNER JOIN tblOperatingSystem AS [OS]
      ON INT.AssignedOperatingSystem = OS.[OS Unique ID])
    INNER JOIN tblDistributionSystems AS [DS]
      ON OS.[DS #] = DS.[DS Unique ID]
    WHERE
      INT.[Interconnection#] = ?;
  """

  cursor = conn.cursor()
  cursor.execute(query, INT)
  row = cursor.fetchone()
  cursor.close()

  if row:
    # ds, config
    return row[0], row[1]
  return None, None

def retrieve_ds(conn, ds):
  query = """
    SELECT 
      assign.[Svc Pt #],
      assign.DS,
      demand.[Base Factor],
      demand.[Heat Factor],
      demand.[HUC 3-Year Peak Demand],
      demand.[FactorQualityCode],
      cat.[Rate Code]
    FROM 
      ((tblSvcPtAssignment AS assign INNER JOIN tblSvcPtDemand AS demand 
        ON assign.[Svc Pt #] = demand.[Svc Pt #])
          INNER JOIN tblSvcPtCategory as cat 
            ON assign.[Svc Pt #] = cat.[Svc Pt #])
      INNER JOIN tblSvcPtInfo as info 
        ON assign.[Svc Pt #] = info.[Svc Pt #]
    WHERE assign.DS = ? and info.[Svc Pt Active] = ?;
  """
  cursor = conn.cursor()

  cursor.execute(query, [ds, -1])
  df = cursor.fetchall()
  cursor.close()
  del cursor
  conn.close()
  return df  

def check_rate(cl):
  abnormal = [customer
    for customer in cl
      if customer["Rate"] not in ['LOW', 'MID', 'HIGH', None, 'IRRI']
  ]
  normal = [customer
    for customer in cl 
      if customer not in abnormal
  ]
  return normal, abnormal

def check_irri(cl):
  irri = [customer
    for customer in cl
          if customer['Rate'] in ['IRRI']
  ]
  normal = [customer
    for customer in cl
      if customer not in irri
  ]
  return normal, irri

def check_huc(cl):
  bad_FQC_customers = [customer
    for customer in cl 
      if customer["Rate"] == "HIGH" and 
        customer["FQC"] not in ["0", "1", "20"] 
  ]
  normal = [customer
    for customer in cl
      if customer not in bad_FQC_customers
  ]
  
  HUC = [customer
    for customer in cl
          if customer['Rate'] in ['HIGH']
         ]
          
  return normal, bad_FQC_customers, HUC

class DSNotFound(Exception):
  pass
class INTNotFound(Exception):
  pass

def make_float(CLs, key):
  for CL in CLs:
    CL[key] = float(CL[key])

def ds_path(db_conn, db_north, db_south, DS):
  if DS is CALGARY_DS:
    print "Warning this will take a while"

  INTs = find_all_int(db_conn, DS)

  if len(INTs) == 0:
    raise DSNotFound()

  if DS.startswith("01"):
    # North
    DFs = retrieve_ds(db_north, DS)
    
  else:
    # South
    DFs = retrieve_ds(db_south, DS)

  headers = ["Service Pt #", "DS", "Base Factor [GJ/d]", "Heat Factor [GJ/d]", "HUC 3-Year Peak Demand", "FQC", "Rate"]
  CLs = [dict(zip(headers, df)) for df in DFs]
  
  CLs, ab = check_rate(CLs)
  CLs, b_fqc, HUC = check_huc(CLs)
  CLs, irri = check_irri(CLs)
  
  make_float(CLs, 'Base Factor [GJ/d]')
  make_float(CLs, 'Heat Factor [GJ/d]')
  
  bf = sum([CL['Base Factor [GJ/d]'] for CL in CLs])
  hf = sum([CL['Heat Factor [GJ/d]'] for CL in CLs])

  bp = np.array(BP_CONSTANT[INTs[0][2]])
  PHFs = np.array(PHF_CONSTANT[INTs[0][2]])
  temps = np.array(TEMP_CONSTANT[INTs[0][2]])
  
  dd = bp - temps
  dd[dd < 0] = 0

  loads = np.array([bf+hf*day for day in dd])
  loads = loads*PHFs
  
  if len(irri) > 0:
    IRRI = raw_input("""
Do you want to include irrigation customers in the load calculation? [y/n]
""")
    while True:
      if IRRI.lower() == 'y':
        loads += 10*len(irri)
        CLs += irri
        break
      if IRRI.lower() == 'n':
        irri = []
        break
      IRRI = raw_input('''Stop being a Raymond, try again with 'y'
for yes and 'n' for no:
''')

  if len(b_fqc) > 0:
    fqc = raw_input("""
Do you want to include the 3-year peak of bad FQC customers in the load calculation? [y/n]
If yes, the three year peak will be added to the load at EACH temperature.
Otherwise, these customers will be excluded and can be manually added later.
""")
    while True:
      if fqc.lower() == "y":
        loads += sum([customer["HUC 3-Year Peak Demand"] for customer in b_fqc])
        CLs += b_fqc
        break
      if fqc.lower() == "n":
        break
      fqc = raw_input('''Stop being a Raymond, try again with 'y'
for yes and 'n' for no:
''')

  print_info(DS, INTs, loads, temps, len(irri), len(HUC), len(CLs))

def int_path(db_conn, db_north, db_south, INT):  
  DS, _ = find_ds_by_int(db_conn, INT)
  
  if not DS:
    raise INTNotFound()

  ds_path(db_conn, db_north, db_south, DS)

if __name__ == "__main__":
  print "Hello, \nThank you for using the load temperature program!"
  reloop = True
  
  while reloop:
    db_conn = connectDB(DB_FILE)
    db_north = connectDB(NORTH_DEMAND_DB)
    db_south = connectDB(SOUTH_DEMAND_DB)
    option = str(raw_input("Enter your DS (XX-XXXX) or INT (XXXXX):"))

    start = time.time()

    DS = ds_checker(option)
    INT = intt_checker(option)

    if not DS and not INT:
      print "Invalid DS or INT"
      continue

    try: 

      if DS:
        print('Please wait...')
        DS = DS.group(0)
        ds_path(db_conn, db_north, db_south, DS)
      elif INT:
        print('Please wait...')
        INT = INT.group(0)
        int_path(db_conn, db_north, db_south, INT)

    except DSNotFound:
      print "This Distribution system exists or it doesn't have an active station."
      print "try again"
      continue

    except INTNotFound:
      print "Interconnection number is incorrect"
      print "try again"
      continue

    redo = raw_input('''Would you like to look at a different DS or INT? [y/n]
''')
    while True:
      if redo.lower() == 'y':
        break
      if redo.lower() == 'n':
        reloop = False
        break
      redo = raw_input('''Stop being a Raymond, try again with 'y'
for yes and 'n' for no:
''') 

