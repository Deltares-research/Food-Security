# -*- coding: utf-8 -*-

"""

"Reads and writes SOBEK HIS files.
Martijn Visser, Deltares, 2014-06

changelog:
2016/09/07: Erwin Meijers:
* Changed bytes to strings (times, locs, params for Python3)
* replaced xrange by range

case egypt: hermawan
"""

import configparser
from datetime import datetime, timedelta
from os.path import getsize
import os
from pathlib import Path
from struct import pack, unpack

import numpy as np
import pandas as pd
import xarray as xr

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)


def _update_long(lst, config, section):
    if section in config:
        # subtract 1 to get a 0 based index for the location
        long_map = {int(k) - 1: v for (k, v) in config[section].items()}
        for i, long_name in long_map.items():
            lst[i] = long_name
    return lst


def read(hisfile, hia=True):
    global locs, params
    """
    Read a hisfile to a xarray.Dataset

    If hia is True, it will use the long location names from the .hia sidecar file
    if it exists.
    """
    filesize = getsize(hisfile)
    if filesize == 0:
        raise ValueError(f"HIS file is empty: {hisfile}")
    with open(hisfile, "rb") as f:
        header = f.read(120).decode("utf-8")
        timeinfo = f.read(40).decode("utf-8")
        datestr = timeinfo[4:14].replace(" ", "0") + timeinfo[14:23]
        startdate = datetime.strptime(datestr, "%Y.%m.%d %H:%M:%S")
        try:
            dt = int(timeinfo[30:-2])  # assumes unit is seconds
        except ValueError:
            # in some RIBASIM his files the s is one place earlier
            dt = int(timeinfo[30:-3])
        noout, noseg = unpack("ii", f.read(8))
        notim = int(
            ((filesize - 168 - noout * 20 - noseg * 24) / (4 * (noout * noseg + 1)))
        )
        params = [(f.read(20).rstrip()).decode("utf-8") for _ in range(noout)]
        locnrs, locs = [], []
        for i in range(noseg):
            locnrs.append(unpack("i", f.read(4))[0])
            locs.append((f.read(20).rstrip()).decode("utf-8"))
        dates = []
        data = np.zeros((noout, notim, noseg), np.float32)
        for t in range(notim):
            ts = unpack("i", f.read(4))[0]
            date = startdate + timedelta(seconds=ts * dt)
            dates.append(date)
            for s in range(noseg):
                data[:, t, s] = np.fromfile(f, np.float32, noout)
    if hia:
        
        # if there is a hia file next to the his, use the long locations
        hia_path = Path(hisfile).with_suffix(".hia")
        if hia_path.is_file():
            #config = configparser.SafeConfigParser(interpolation=None)
            config = configparser.ConfigParser(interpolation=None)
            config.read(hia_path)
            locs = _update_long(locs, config, "Long Locations")
            params = _update_long(params, config, "Long Parameters")

    ds = xr.Dataset(
        {
            param: (["time", "station"], data[i, ...])
            for (i, param) in enumerate(params)
        },
        coords={
            "time": dates,
            "station": locs,
        },
        attrs=dict(header=header, scu=dt, t0=startdate),
    )
    return ds


def write(hisfile, ds):
    """Writes an xarray.Dataset with extra attributes to a hisfile."""
    with open(hisfile, "wb") as f:
        header = ds.attrs["header"]
        scu = ds.attrs["scu"]
        t0 = ds.attrs["t0"]
        f.write(header.ljust(120)[:120].encode("ascii"))  # enforce length
        t0str = t0.strftime("%Y.%m.%d %H:%M:%S")
        timeinfo = "T0: {}  (scu={:8d}s)".format(t0str, scu)
        f.write(timeinfo.encode("ascii"))
        noout = len(ds)
        notim, noseg = ds.time.size, ds.station.size
        f.write(pack("ii", noout, noseg))
        params = np.array(list(ds.keys()), dtype="S20")
        params = np.char.ljust(params, 20)
        params.tofile(f)
        locs = np.array(ds.station, dtype="S20")
        locs = np.char.ljust(locs, 20)
        for locnr, loc in enumerate(locs):
            f.write(pack("i", locnr))
            f.write(loc)
        da = ds.to_array()
        assert da.dims != ("variable", "time", "station")
        data = da.values.astype(np.float32)
        for t, date in enumerate(ds.time.values):
            date = pd.Timestamp(date).to_pydatetime()
            ts = int((date - t0).total_seconds() / scu)
            f.write(pack("i", ts))
            for s in range(noseg):
                data[:, t, s].tofile(f)
        countmsg = "hisfile written is not the correct length"
        assert f.tell() == 160 + 8 + 20 * noout + (4 + 20) * noseg + notim * (
            4 + noout * noseg * 4
        ), countmsg


def toBCM(ds, list_var):
    """
    Calculates the sum over the time axis of an HIS-xarray.Dataset (as returned by his.read) and converts the values from (m3/s) to BCM.
    Variables with units other than m3/s are removed.
    """
    # remove data vars that don't make sense to convert from m3/s to BCM
    #var_names = [x for x in ds.keys() if 'm3/s' in x]
    var_names = list_var
    ds = ds[var_names]

    # get last time step of time-axis
    time_last = pd.DatetimeIndex([ds.time[-1].values])[0]
    # guestimate what the next time step should be
    if time_last.day == 1 or time_last.day == 10:
        time_tail = time_last + np.timedelta64(10, 'D')
    if time_last.day == 21:
        time_tail = time_last + pd.offsets.MonthBegin(1)
    # calculate duration of each time step
    time_delta = ((
        np.append(ds.time[1:].values, np.datetime64(time_tail))-
        ds.time.values
        )/(1E9)).astype(int) #in seconds
    # assign time delta coordinate
    ds = ds.assign_coords({'time_delta': ('time', time_delta)}) 
    
    # calculate m3/s to bcm
    #ds_bcm = (ds*ds.time_delta).sum(dim='time') / 1E9
    ds_bcm = (ds*ds.time_delta) / 1E9

    # add units
    for i in var_names:
        ds_bcm[i].attrs['units'] = 'BCM'

    # done
    return ds_bcm

#READ RIBASIM CASES============================================================
model   = r'D:\Egypt JCAR A4i\data update August 2024\JCARWQ.Rbd' 
cmt_file = 'caselist.cmt'

d = {}
with open(os.path.join(model, cmt_file) ) as f:
    for line in f:
        (key, val) = line.split(" ", 1)
        d[int(key)] = val
        
#for now assume keys are case id

#READ RIBASIM PARAMETERS (RELEVANT TO INDICATOR)===============================
#read for example shortage monthly, assume location is all
#to_open = [indicator id match with database, his file name, parameter name, desired units]
to_open = [
    #0. HAD release
    ['0','varinfl.his',['- Downstream flow (m3/s)'],'BCM'],
    #1. Water demand (bcm)
    ['1a', 'pwsupply.his', ['Gross demand incl.losses from network (m3/s)'], 'BCM'],#dri&irri
    ['1b', 'advirrig.his', ['Demand from network (m3/s)'], 'BCM'], #irrigation
    #['1c', 'fishpond.his', ['Demand (m3/s)'], 'BCM'], #fisheries
    #2. Shortage in agriculture bcm and %
    ['2a', 'advirrig.his', ['Shortage (m3/s)'], 'BCM'],
    ['2b', 'advirrig.his', ['Number (%) of time steps with shortage'], 'countdecadal'],
    #3. Release to sea
    ['3', 'terminal.his', ['End flow (m3/s)'], 'BCM'],
    #4. Reuse of agricultural drainage (bcm)
    ['4', 'advirrig.his', ['- Return flow to SW incl gw exfilt. (m3/s)'], 'BCM'],
    #5. Reuse from shallow groundwater for agriculture (bcm)
    #['5', 'gwresrvr.his', ['+ Return flow from users prev.ts (Mcm)'], 'BCM'],
    ['5', 'advirrig.his ', ['+ Allocated GW (m3/s)'], 'BCM'],
    #loss of productivity (rice in tonnes) #RIBASIM
    ['7a', 'cltagpro.his', ['Potent.field level production [kg]'], 'kg'],
    ['7b', 'cltagpro.his', ['Actual field level production [kg]'], 'kg'], 
    #loss of productivity (wheat in tonnes) #RIBASIM
    ['8a', 'cltagpro.his', ['Potent.field level production [kg]'], 'kg'],
    ['8b', 'cltagpro.his', ['Actual field level production [kg]'], 'kg'],
    #Water return for agriculture #ASME, per governorates
    #provided by WUR
    ]

database = pd.DataFrame()
#loop over indicator
for i in range(len(to_open)):
    print (to_open[i][0])
    #loop over case
    for rib_case in d.keys():
        path = os.path.join(model, str(rib_case))
        file_name = to_open[i][1]
        full_path = os.path.join(path, file_name) 
        data = read(full_path, hia=True)
        
        if isinstance(to_open[i][2][0], int):
            param_name = list(data.data_vars.keys())[to_open[i][2][0]] #get interger to_open[i][2], get the first value in a list
        else:
            param_name = to_open[i][2][0]
        
        if "BCM" in to_open[i][3]:
            data_store = toBCM(data, [param_name])
        else:
            data_store = data.copy()

        data_df = data_store[param_name].to_dataframe()
    
        data_df = data_df.reset_index()
        data_df['case_id']       = ' '.join(d.get (rib_case).split()[:1]).replace ('"', '')    
        data_df['indicator_id']  = to_open[i][0]
        data_df.rename(columns={'station': 'geo', param_name : 'value'}, inplace=True)
        
        columns = ['time', 'geo', 'value', 'case_id', 'indicator_id']
        data_df = data_df[columns]
        
        #append
        database = database.append(data_df, ignore_index=True)
        
database.to_csv('database.csv')

#CONNECT RIBASIM LOCATION WITH DATABASE MAP LOCATION============================
# URL of the Google Sheets document in XLSX format, connect to google spreadsheet
url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vThJkRIVbYPU3abyXYXuVimR8aUBQq-DNZWtkzCEu6PZNAsDOcykEG89UKFc34hPuAwHCHUFRW_MXlu/pub?output=xlsx"

# Read the Google Sheets document into a Pandas DataFrame
location_lookup = pd.read_excel(url, sheet_name='ribasim_dashboard_locs')
location_lookup['indicator_id'] = location_lookup['indicator_id'].astype(str)

# Trasnform locations to desired database locations
database_loc = pd.merge(database, location_lookup, left_on=['geo', 'indicator_id'], right_on=['ribasim_locs','indicator_id'], how='inner')
database_loc = database_loc[['time', 'dashboard_locs', 'value', 'case_id', 'indicator_id']]
database_loc.rename(columns={'dashboard_locs': 'geo'}, inplace=True)

# Define custom aggregation function, shortagetime should be average - rest should be sum per CU
def custom_aggregation(group):
    if (group['indicator_id'] == '2b').any():
        return group['value'][group['indicator_id'] == '2b'].mean()
    else:
        return group['value'].sum()

# Group by 'time', 'case_id', and 'indicator_id', and apply custom aggregation function
database_loc_agg = database_loc.groupby(['time', 'case_id', 'indicator_id', 'geo']).apply(custom_aggregation).reset_index()
database_loc_agg.rename(columns={0: 'value'}, inplace=True)

database_loc_agg['value'] = database_loc_agg['value'].apply(lambda x: 0 if -0.000001 < x < 0.000001 else x)

database_loc_agg.to_csv('database_loc_agg.csv')


#AGGREGATE PARAMETERS TO INDICATORS, WHEN NECESSARY============================
def compute_combined_indicator(df, indicator_id_a, indicator_id_b, operation='add', new_indicator_id='1000'):
    global df_res
    # Filter rows with indicator_id "1a" and "1b"
    df_1a = df[df['indicator_id'] == indicator_id_a]
    df_1b = df[df['indicator_id'] == indicator_id_b]

    # Merge dataframes and calculate the difference or sum based on the operation
    merged_df = pd.merge(df_1a, df_1b, on=['time', 'case_id', 'geo'], suffixes=('_1a', '_1b'))
    if operation == 'subtract':
        merged_df['value'] = merged_df['value_1a'] - merged_df['value_1b']
    elif operation == 'add':
        merged_df['value'] = merged_df['value_1a'] + merged_df['value_1b']
    else:
        raise ValueError("Invalid operation. Choose either 'subtract' or 'add'.")
        
    merged_df.drop(columns=['indicator_id_1a', 'indicator_id_1b', 'value_1a', 'value_1b'], inplace=True)
    merged_df['indicator_id'] = new_indicator_id
    
    #append
    df_res = pd.concat([df, merged_df], ignore_index=True)
    return df_res

#CALCULATE FINAL INDICATORS VALUES
database_loc_agg_combine = database_loc_agg.copy()  
#1. Water demand (bcm) = 1a + 1b
database_loc_agg_combine = compute_combined_indicator(database_loc_agg_combine, '1a', '1b', operation='add', new_indicator_id='1') #sum agr+pws
#database_loc_agg_combine = compute_combined_indicator(database_loc_agg_combine, '1a', '1c', operation='add', new_indicator_id='1') #sum agr+pws+fisheries

#loss of productivity (rice in tonnes) #RIBASIM 7a - 7b
database_loc_agg_combine = (compute_combined_indicator(database_loc_agg_combine, '7a', '7b', operation='subtract', new_indicator_id='7'))
#loss of productivity (wheat in tonnes) #RIBASIM #RIBASIM 8a - 8b
database_loc_agg_combine = (compute_combined_indicator(database_loc_agg_combine, '8a', '8b', operation='subtract', new_indicator_id='8'))
#to million tonnes
database_loc_agg_combine.loc[database_loc_agg_combine['indicator_id'].isin(['7', '8']), 'value'] /= 1000000000

#rename indicator to match dashboard id
database_loc_agg_combine['indicator_id'] = database_loc_agg_combine['indicator_id'].replace('2b', '6')
database_loc_agg_combine['indicator_id'] = database_loc_agg_combine['indicator_id'].replace('2a', '2')

database_loc_agg_combine.to_csv('database_loc_agg_combine.csv')
        
#CALCULATE CU TO GOV with weighted area average=======================================================================
# URL of the Google Sheets document in XLSX format, connect to google spreadsheet
url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vThJkRIVbYPU3abyXYXuVimR8aUBQq-DNZWtkzCEu6PZNAsDOcykEG89UKFc34hPuAwHCHUFRW_MXlu/pub?output=xlsx"

# Read the Google Sheets document into a Pandas DataFrame
pct_cu_in_gov = pd.read_excel(url, sheet_name='cu_gov')
df1 = pct_cu_in_gov.rename(columns={'Unnamed: 0': 'CU_ID'})
df1 = df1.replace(0, np.nan)

#database in comman unit
df2 = database_loc_agg_combine.copy().rename(columns={'geo': 'CU_ID'})
df2['indicator_id'] = df2['indicator_id'].astype(str)

# Group by 'time', 'case_id', and 'indicator_id'
df2_grouped = df2.groupby(['time', 'case_id', 'indicator_id'])

# Iterate over each group
for (time, case_id, indicator_id), group in df2_grouped:
    #print(f"Group for time: {time}, case_id: {case_id}, indicator_id: {indicator_id}")
    # Merge DataFrames on 'CU_ID'
    df_merged = pd.merge(df1, group, on='CU_ID', how='outer')
    # Set 'CU_ID' as index, make sure they are at same order to multiply each values and each %cugov
    df_merged.set_index('CU_ID', inplace=True)
    if indicator_id == '6':
        df_res = (df_merged.iloc[:, :-4] * df_merged['value'].values.reshape(-1, 1)).mean(axis=0)
    else:
        df_res = (df_merged.iloc[:, :-4] * df_merged['value'].values.reshape(-1, 1)).sum(axis=0)
    df_gov = df_res.reset_index()
    df_gov['time']        = time
    df_gov['case_id']     = case_id
    df_gov['indicator_id'] = indicator_id
    df_gov = df_gov.rename(columns={'index': 'geo',0: 'value'})
    df_gov['geo'] = 'GOV_' + df_gov['geo'].astype(str)
    
    # Reorder df2 columns to match df1
    df_gov = df_gov[database_loc_agg_combine.columns]
    
    #combine all data
    database_loc_agg_combine = pd.concat([database_loc_agg_combine, df_gov], ignore_index=True)
    
#get==============================================
database_loc_agg_combine_id = database_loc_agg_combine[database_loc_agg_combine['indicator_id'].apply(lambda x: str(x).isdigit())]
database_loc_agg_combine_id.to_csv('database_loc_agg_combine_inclgov.csv')


#remove non relevant indicator like 2a 2b
