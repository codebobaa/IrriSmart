import streamlit as st
import pandas as pd
import ee
import geemap.foliumap as geemap
import requests
from datetime import datetime, timedelta, date, time
import math
import numpy as np
import plotly.express as px
import matplotlib.pyplot as plt




st.set_page_config(layout="wide")




st.title("Welcome to IrriSmart")
st.subheader("Please enter the relevant information on the sidebar")
crop_type = st.sidebar.selectbox("Select Crop Type", ("sweet corn", "wheat", "potato", "pumpkin", "lettuce", "tomato", "berries", "cucumber", "onion"))
crop_doy = st.sidebar.text_input("Enter Days Since Planting")
location_name = st.sidebar.text_input("Enter the city of where your farm is located")
days_past = st.sidebar.slider("Days since last irrigation", 1, 5, 1)
acres = st.sidebar.text_input("How many acres is your farm?")
Analysis_types = ['Irrigation Plan', 'Weather Visualization', 'Weather Analysis']
Analysis = st.sidebar.radio("Select Type of Analysis", Analysis_types)

if acres == None:
    crop_type = "sweet corn"
    crop_doy = "5"
    location_name = "Chandler"
    days_past = '5'
    acres = '1'
    Analysis = "Irrigation Plan"


#Import Crop Coefficients
crop_coefficients_df = pd.read_csv("crop_coefs.csv", skiprows=1)
crop_coefficients_df.set_index("Crop", inplace=True)

#Import Crop Lengths
crop_lengths_lim_df = pd.read_csv("crop_lengths_lim.csv")
crop_lengths_lim_df.set_index("Crop", inplace = True)



#Weather Analysis
#Call API from Open Weather Map webpage
api_key = '896cbba33f2536fcb57efcb59484cc58'
url_current = "https://api.openweathermap.org/data/2.5/weather?q={}&appid={}"
url_past = "https://api.openweathermap.org/data/2.5/onecall/timemachine?lat={}&lon={}&dt={}&appid={}"

#Evapotranspiration Calculation
def hamon_et_calculation(t_max, t_min, daylight_hours):
    t_mean = (t_max + t_min)/2
    esat = 6.108 * math.exp((17.26939 * t_mean)/(t_mean + 237.3))
    rhosat = 216.7 * esat/(t_mean + 273.3)
    et0= 0.1651*(daylight_hours/12)*rhosat*1.1
    return et0

#Function to get the current weather data
def getweather(city):
    result = requests.get(url_current.format(city, api_key))
    if result:
        json = result.json()
        country = json['sys']['country']
        temp = (json['main']['temp'] - 273.15) * 1.8 + 32
        temp_feels = (json['main']['feels_like'] - 273.15) * 1.8 + 32
        icon = json['weather'][0]['icon']
        lon = json['coord']['lon']
        lat = json['coord']['lat']
        des = json['weather'][0]['description']
        res = [country, round(temp, 1), round(temp_feels, 1), lon, lat, icon, des ]
        return res, json
    else:
        print("error in search!")

#Function to get the historical weather data
def get_hist_data(lat, lon, start):
    res = requests.get(url_past.format(lat, lon, start, api_key))
    data = res.json()
    temp = []
    rain_total_daily = []
    for hour in data["hourly"]:
        t = hour["temp"]
        temp.append(t)
        if 'rain' in hour.keys():
            rain = hour["rain"]["1h"]
            rain_total_daily.append(rain)
    return data, temp, rain_total_daily

try:
    res, json = getweather(location_name)
    start_date_string = st.date_input('Current Date')
    date_df = []
    max_temp_df_c = []
    max_temp_df = []
    min_temp_df_c = []
    min_temp_df = []
    daily_rain_sum_df = []
    for i in range(int(days_past)):
        date_Str = start_date_string - timedelta(i)
        start_date = datetime.strptime(str(date_Str), "%Y-%m-%d")
        timestamp_1 = datetime.timestamp(start_date)
        his, temp, daily_rain = get_hist_data(res[4], res[3], int(timestamp_1))
        date_df.append(date_Str)
        max_temp_df_c.append((max(temp) - 273.5))
        max_temp_df.append((max(temp) - 273.5) * 1.8 + 32)
        min_temp_df_c.append((min(temp) - 273.5))
        min_temp_df.append((min(temp) - 273.5) * 1.8 + 32)
        daily_rain_sum_df.append(sum(daily_rain))
    df = pd.DataFrame()
    df["Date"] = date_df
    df["Max_temp (F)"] = max_temp_df
    df["Min_temp (F)"] = min_temp_df
    df["Rain (mm)"] = daily_rain_sum_df


    if Analysis == 'Weather Analysis':
        res, json = getweather(location_name)
        st.success('Current: ' + str(round(res[1], 2)))
        show_hist = st.expander(label = 'Weather Since Last Irrigation')
        with show_hist:
            date_df = []
            max_temp_df = []
            min_temp_df = []
            daily_rain_sum_df = []
            for i in range(int(days_past)):
                date_Str = start_date_string - timedelta(i)
                start_date = datetime.strptime(str(date_Str), "%Y-%m-%d")
                timestamp_1 = datetime.timestamp(start_date)
                his, temp, daily_rain = get_hist_data(res[4], res[3], int(timestamp_1))
                date_df.append(date_Str)
                max_temp_df.append((max(temp) - 273.5) * 1.8 + 32)
                min_temp_df.append((min(temp) - 273.5) * 1.8 + 32)
                daily_rain_sum_df.append(sum(daily_rain))
            df = pd.DataFrame()
            df["Date"] = date_df
            df["Max_temp (F)"] = max_temp_df
            df["Min_temp (F)"] = min_temp_df
            df["Rain (mm)"] = daily_rain_sum_df
            st.table(df)

    #Function for Interpolating Kc
    def get_crop_kc(crop, days):
        Ini_end = crop_lengths_lim_df.loc[crop]["L_ini"]
        Dev_end = (crop_lengths_lim_df.loc[crop]["L_ini"] + crop_lengths_lim_df.loc[crop]["L_dev"])
        Mid_end = Dev_end + crop_lengths_lim_df.loc[crop]["L_mid"]
        End_end = Mid_end + crop_lengths_lim_df.loc[crop]["L_end"]
        if days <= Ini_end:
            Kc = crop_coefficients_df.loc[crop]["Kc ini"]
        elif days <= Dev_end:
            x = [Ini_end, Dev_end]
            y = [crop_coefficients_df.loc[crop]["Kc ini"], crop_coefficients_df.loc[crop]["Kc mid"]]
            Kc = np.interp(days, x,y)
        elif days <= Mid_end:
            Kc= crop_coefficients_df.loc[crop]["Kc mid"]
        elif days <= End_end:
            x = [Mid_end, End_end]
            y = [crop_coefficients_df.loc[crop]["Kc mid"], crop_coefficients_df.loc[crop]["Kc end"]]
            Kc = np.interp(days, x, y)
        return Kc

    #Function for calculating how many gallons over an entire field
    def total_gallons(depth_mm, area_acre):
        depth_inch = depth_mm/25.4
        area_in_sq = area_acre*6272640
        volume_inch = depth_inch * area_in_sq
        volume_gallon = round(volume_inch/231)
        return volume_gallon



    if Analysis == 'Irrigation Plan':
        date_df = []
        et0_df = []
        Total_et = []
        sunlight_hours = round(((json['sys']['sunset'] - json['sys']['sunrise'])/3600), 1)
        for i in range(int(days_past)):
            date_Str = start_date_string - timedelta(i)
            date_df.append(date_Str)
            et0 = hamon_et_calculation(max_temp_df_c[i], min_temp_df_c[i], float(sunlight_hours))
            et0_df.append(et0)
            crop_coef = get_crop_kc(crop_type, float(crop_doy) - i)
            Et_c = et0 * crop_coef
            Total_et.append(Et_c)
        df = pd.DataFrame()
        df["Date"] = date_df
        df["Reference ET (mm)"] = et0_df
        Total_lost = round(sum(Total_et), 1)
        Total_gained = round(sum(daily_rain_sum_df), 1)
        st.table(df)
        #st.warning('Amount of Water Lost: ' + str(Total_lost) + ' mm')
        #st.info('Amount of Water Gained: ' + str(Total_gained) + ' mm')
        if Total_lost - Total_gained > 0:
            irrigation_amount = Total_lost - Total_gained
            volume_necessary = total_gallons(irrigation_amount, float(acres))
            col1, col2, col3 = st.columns(3)
            col1.metric("Water Lost Since Last Irrigation", str(total_gallons(Total_lost, float(acres))) + ' gallons')
            col2.metric("Water Gained Since Last Irrigation", str(total_gallons(Total_gained, float(acres))) + ' gallons')
            col3.metric("Irrigation Amount", str(volume_necessary) + ' gallons')
            #st.success('Amount of Irrigation Necessary: ' + str(volume_necessary) + 'gallons')
        elif Total_lost - Total_gained <= 0:
            col1, col2 = st.columns(2)
            col1.metric("Total Water Lost", str(total_gallons(Total_lost, float(acres))) + ' gallons')
            col2.metric("Total Water Gained", str(total_gallons(Total_gained, float(acres))) + ' gallons')
            st.success('No need for irrigation!')

    date_df = []
    et0_df = []
    Total_et = []
    sunlight_hours = round(((json['sys']['sunset'] - json['sys']['sunrise'])/3600), 1)
    for i in range(int(days_past)):
        date_Str = start_date_string - timedelta(i)
        date_df.append(date_Str)
        et0 = hamon_et_calculation(max_temp_df_c[i], min_temp_df_c[i], float(sunlight_hours))
        et0_df.append(et0)
        crop_coef = get_crop_kc(crop_type, float(crop_doy) - i)
        Et_c = et0 * crop_coef
        Total_et.append(Et_c)
    df_et = pd.DataFrame()
    df_et["Date"] = date_df
    df_et["ET0 (mm)"] = et0_df

    if Analysis == 'Weather Visualization':
        fig = px.line(df, x="Date", y=df.columns[1:-1], title="Min and Max Temperature Since Last Irrigation")
        fig.update_layout(yaxis_title = "Temperature (F)")
        st.plotly_chart(fig)
        fig_rain = px.line(df, x= "Date", y= "Rain (mm)", title = "Precipitation Since Last Irrigation")
        st.plotly_chart(fig_rain)
        fig_et = px.line(df_et, x= "Date", y = "ET0 (mm)", title = "Evapotranspiration Since Last Irrigation")
        st.plotly_chart(fig_et)



    #Home Page

    #st.subheader("Map")
    #Map = geemap.Map(center=[res[4],res[3]], zoom=10)
    # Add a basemap
    #Map.add_basemap("SATELLITE")


    # Retrieve Earth Engine dataset
    # dem = ee.Image("USGS/SRTMGL1_003")
    # Set visualization parameters
    vis_params = {
        "min": 0,
        "max": 4000,
        "palette": ["006633", "E5FFCC", "662A00", "D8D8D8", "F5F5F5"],
    }

    # Add the Earth Engine image to the map
    #Map.addLayer(dem, vis_params, "SRTM DEM", True, 0.5)
    # Add a colorbar to the map
    #Map.add_colorbar(vis_params["palette"], 0, 4000, caption="Elevation (m)")
    # Render the map using streamlit
    #Map.to_streamlit()



except:
    st.warning("Please enter valid information in the sidebar")







