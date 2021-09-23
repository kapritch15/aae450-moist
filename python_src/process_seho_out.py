from branca import colormap
import numpy as np
import pandas as pd
import folium
from folium.plugins import HeatMap
import branca
from shapely.geometry import Polygon
import geopandas as gpd
import h5py
import matplotlib.pyplot as plt

from os import walk
from os.path import join
from tqdm import tqdm

from typing import List

## File which is used to process Seho's output


def get_all_files_dir(path_to_dir: str) -> List[str]:
    '''
        Gets all the file names in a directory

        Inputs:
            path_to_dir (str): full path to directory
    '''
    # file_names = [join(path_to_dir,f) for f in listdir(path_to_dir) if isfile(join(path_to_dir, f))]
    
    file_names = []
    for (dirpath, dirnames, filenames) in walk(path_to_dir):
        temp = [join(dirpath, f) for f in filenames]
        file_names.extend(temp)

    # Remove .gitignore files
    for name in file_names:
        if 'gitignore' in name:
            file_names.remove(name)

    return file_names

def get_files_pd(file_names: List[str]) -> pd.DataFrame:
    '''
        Gets the files and returns a single Pandas Dataframe
        
        Inputs:
            file_names (List): list of all the full filenames
    '''
    column_names   = ['JulianDay', 
                      'LatRx', 'LonRx', 'AltRx',
                      'TxID', 'LatTx', 'LonTx', 'AltTx',
                      'LatSp', 'LonSp', 'AltSp',
                      'LandMask', 'idk']
    unused_columns = ['LatRx', 'LonRx', 'AltRx',
                      'TxID', 'LatTx', 'LonTx', 'AltTx', 'idk']
    list_dfs = []

    for file_name in file_names:
        data = pd.read_csv(file_name, sep=" ", header=None)
        data.columns = column_names
        data = data.drop(columns=unused_columns)

        list_dfs = list_dfs + [data]

    df = pd.concat(list_dfs)

    # Remove water samples (land=1, water=0)
    df = df[df.LandMask == 1]

    return df

def get_landmask(land_mask_dir):
    land_mask_path = land_mask_dir+'Land_Mask_1km_EASE2_grid_150101_v004.h5'
    lat_path       = land_mask_dir+'EZ2Lat_M01_002_vec.float32'
    lon_path       = land_mask_dir+'EZ2Lon_M01_002_vec.float32'
    land_mask = []
    lat       = []
    lon       = []

    print('Getting land mask and latitude and longitude values...')
    with h5py.File(land_mask_path, 'r') as f:
        group_key = list(f.keys())[1]

        # Get the data
        land_mask = np.asarray(list(f[group_key]['mask']))

    lat = np.fromfile(lat_path, dtype=np.float32)
    lon = np.fromfile(lon_path, dtype=np.float32)

    latlon = np.array(np.meshgrid(lat,lon)).T.reshape(-1,2)

    return land_mask, latlon

def get_land_latlon(land_mask_dir):
    '''
    Don't run this. It currently breaks my computer
    '''
    land_mask, latlon  = get_landmask(land_mask_dir)
    latlon_mask = pd.DataFrame(data=latlon, columns=['lat', 'lon'])
    latlon_mask['land_mask'] = land_mask.reshape(-1,1).astype(np.uint8)

    print(latlon_mask.dtypes)

    n = 200000
    list_df = [latlon_mask[i:i+n] for i in range(0,latlon_mask.shape[0],n)]

    for df in tqdm(list_df):
        df = df[df['land_mask'] > 0]
        # print(df.head())
    
    latlon_mask = pd.concat(list_df)
    print(latlon_mask)

def get_specular_heatmap(specular_df):
    ''''
        Heatmap of the specular points
    '''
    # Group the measurements into buckets
    # Round lat and long and then use groupby to throw them all in similar buckets
    specular_df['approx_LatSp'] = round(specular_df['LatSp'], 1)
    specular_df['approx_LonSp'] = round(specular_df['LonSp'], 1)

    test = specular_df.groupby(['approx_LatSp', 'approx_LonSp']).size()
    indeces = test.index.tolist()
    df = pd.DataFrame(indeces, columns=['latitude', 'longitude'])
    df['countSp'] = test.values.astype('float')

    max_amt = float(df.countSp.max())
    print(max_amt)

    # Generate Polygons
    df['geometry'] = df.apply(lambda row: Polygon([(row.longitude-0.05, row.latitude-0.05), 
                                                   (row.longitude+0.05, row.latitude-0.05),
                                                   (row.longitude+0.05, row.latitude+0.05),
                                                   (row.longitude-0.05, row.latitude+0.05)]), axis=1)
    print(df.head())
    # Heat map
    hmap = folium.Map(location=[42.5, -80], zoom_start=7, )
    hm_wide = HeatMap(list(zip(df.latitude.values, df.longitude.values, df.countSp.values)),
                      gradient={0.0: '#00ae53', 0.2: '#86dc76', 0.4: '#daf8aa',
                                0.6: '#ffe6a4', 0.8: '#ff9a61', 1.0: '#ee0028'},
                                )
    hmap.add_child(hm_wide)

    colormap = branca.colormap.StepColormap(
               colors=['#00ae53', '#86dc76', '#daf8aa',
                       '#ffe6a4', '#ff9a61', '#ee0028'],
               vmin=0,
               vmax=25,
               index=[0, 4, 8, 12, 16, 20])
    # colormap = colormap.to_step(index=[0,2, 4, 6, 8, 10, 12])
    colormap.caption='Number of Specular Points'
    colormap.add_to(hmap)
    # colormap_dept = branca.colormap.StepColormap(
    #     colors=['#00ae53', '#86dc76', '#daf8aa',
    #         '#ffe6a4', '#ff9a61', '#ee0028'],
    #     vmin=0,
    #     vmax=max_amt,
    #     index=[0, 2, 4, 6, 8, 10, 12])
    
    # style_func = lambda x: {
    #     'fillColor': colormap_dept(x['countSp']),
    #     'color': '',
    #     'weight': 0.0001,
    #     'fillOpacity': 0.1
    # }

    # folium.GeoJson(
    #     df,
    #     style_function=style_func,
    # ).add_to(hmap)

    hmap.save('test.html')

def get_revisit_info(specular_df):
    '''
        Returns array with the revisit info
    '''
    # Round lat and long and then use groupby to throw them all in similar buckets
    specular_df['approx_LatSp'] = round(specular_df['LatSp'],1)
    specular_df['approx_LonSp'] = round(specular_df['LonSp'],1)

    # Calculate time difference
    specular_df.sort_values(by=['approx_LatSp', 'approx_LonSp', 'JulianDay'], inplace=True)
    specular_df['revisit'] = specular_df['JulianDay'].diff()

    # Correct for borders
    specular_df['revisit'].mask(specular_df.approx_LatSp != specular_df.approx_LatSp.shift(1), other=np.nan, inplace=True)
    specular_df['revisit'].mask(specular_df.approx_LonSp != specular_df.approx_LonSp.shift(1), other=np.nan, inplace=True)

    # Get max revisit and store in new DF
    indeces = specular_df.groupby(['approx_LatSp', 'approx_LonSp'])['revisit'].transform(max) == specular_df['revisit']

    max_rev_area_df = specular_df[indeces]

    # Get rid of extra columns
    # Any revisit that is less than 1 hour is removed. Typically this occurs because of a lack of samples (due to low sim time)
    extra_cols = ['JulianDay', 'LatSp', 'LonSp', 'AltSp', 'LandMask']
    max_rev_area_df['revisit'].mask(max_rev_area_df['revisit'] < 0.04, other=np.nan, inplace=True)
    max_rev_area_df.drop(extra_cols, inplace=True, axis=1)

    return max_rev_area_df

def plot_revisit_heatmap(max_rev_area_df):
    # Remove NaNs
    max_rev_area_df = max_rev_area_df[max_rev_area_df['revisit'].notnull()]

    # Heat map
    hmap = folium.Map(location=[42.5, -80], zoom_start=7, )
    hm_wide = HeatMap(list(zip(max_rev_area_df.approx_LatSp.values, max_rev_area_df.approx_LonSp.values, max_rev_area_df.revisit.values)),
                      gradient={0.0: '#00ae53', 0.2: '#86dc76', 0.4: '#daf8aa',
                                0.6: '#ffe6a4', 0.8: '#ff9a61', 1.0: '#ee0028'})
    hmap.add_child(hm_wide)

    max_amt = max(max_rev_area_df.revisit.values)

    print(max_amt)

    colormap = branca.colormap.StepColormap(
               colors=['#00ae53', '#86dc76', '#daf8aa',
                       '#ffe6a4', '#ff9a61', '#ee0028'],
               vmin=0,
               vmax=max_amt,
               index=[0, 2, 4, 6, 8, 10])
    colormap.caption='Revisit Time'
    colormap.add_to(hmap)

    hmap.save('test_revisit_10day.html')

def plot_revisit_map_2(max_rev_area_df):
    # First reduce the resolution of the polymap to avoid murdering my computer
    # Round lat and long and then use groupby to throw them all in similar buckets
    max_rev_area_df['approx_LatSp'] = round(max_rev_area_df['approx_LatSp'])
    max_rev_area_df['approx_LonSp'] = round(max_rev_area_df['approx_LonSp'])

    # Get max revisit and store in new DF
    indeces = max_rev_area_df.groupby(['approx_LatSp', 'approx_LonSp'])['revisit'].transform(max) == max_rev_area_df['revisit']

    max_rev_area_df = max_rev_area_df[indeces]

    # Now generate the map
    map = folium.Map(location=[42.5, -80], zoom_start=7, )

    # Remove NaNs
    max_rev_area_df = max_rev_area_df[max_rev_area_df['revisit'].notnull()]
    # Generate Polygons
    max_rev_area_df['geometry'] = max_rev_area_df.apply(lambda row: Polygon([(row.approx_LonSp-0.5, row.approx_LatSp-0.5), 
                                                                             (row.approx_LonSp+0.5, row.approx_LatSp-0.5),
                                                                             (row.approx_LonSp+0.5, row.approx_LatSp+0.5),
                                                                             (row.approx_LonSp-0.5, row.approx_LatSp+0.5)]), axis=1)
    max_amt = max(max_rev_area_df.revisit.values)
    print(max_amt)
    print(max_rev_area_df)
    # colormap_dept = branca.colormap.StepColormap(
    #     colors=['#0A2F51', '#0E4D64', '#137177', '#188977', '#1D9A6C',
    #             '#39A96B', '#56B870', '#74C67A', '#99D492', '#BFE1B0', '#DEEDCF'],
    #     vmin=0,
    #     vmax=max_amt,
    #     index=[0,1,2,3,4,5,6,7,8,9,10])
    colormap_dept = branca.colormap.LinearColormap(colors=['green','yellow', 'red'], vmin=0, vmax=max_amt)

    print('revisit 0: ', colormap_dept(0))
    print('revisit 1: ', colormap_dept(1))
    print('revisit 2: ', colormap_dept(2))
    print('revisit 3: ', colormap_dept(3))
    print('revisit 4: ', colormap_dept(4))
    print('revisit 4.5: ', colormap_dept(4.5))

    for _, r in tqdm(max_rev_area_df.iterrows(), total=max_rev_area_df.shape[0]):
        # print(r['revisit'])
        style_func = lambda x, revisit=r['revisit']: {
            'fillColor': colormap_dept(revisit),
            'color': '',
            'weight': 1.0,
            'fillOpacity': 0.5
        }
        # print(style_func(r['revisit']))
        sim_geo = gpd.GeoSeries(r['geometry'])
        geo_j = sim_geo.to_json()
        geo_j = folium.GeoJson(data=geo_j, style_function=style_func, overlay=True, control=True)
        geo_j.add_to(map)
        # break
    
    # Add legend
    colormap_dept.caption='Revisit Time'
    colormap_dept.add_to(map)
    # map.add_child(folium.LayerControl())

    # Save it
    map.save('revisit_polymap_10day_test.html')

    # return max_rev_area_df

def plot_revisit_stats(max_rev_area_df):
    '''
        Get relevant revisit statistics
    '''
    # Remove NaNs
    max_rev_area_df = max_rev_area_df[max_rev_area_df['revisit'].notnull()]

    # Plot over all areas
    print('Creating histogram')
    print(max_rev_area_df)
    ax = max_rev_area_df['revisit'].plot.hist(bins=50, alpha=0.5)
    ax.plot()
    plt.xlabel('Maximum Revisit Time (days)')
    plt.title('Frequency Distribution of Maximum Revisit Time')
    plt.show()


if __name__ == "__main__":
    # This path assumes all files in the folder are for this test. It does remove .gitignore files though
    path_to_output='/home/polfr/Documents/dummy_data/09_17_2021/Unzipped/'
    file_names = get_all_files_dir(path_to_output)
    specular_df = get_files_pd(file_names)
    max_rev_area_df = get_revisit_info(specular_df)
    plot_revisit_map_2(max_rev_area_df)
    # plot_revisit_stats(test)