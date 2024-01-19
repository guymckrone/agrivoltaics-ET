import pytz, math, requests
import matplotlib.pyplot as plt

from skyfield.api import Topos, load
from skyfield import almanac
from timezonefinder import TimezoneFinder
from datetime import datetime, timedelta
from itertools import accumulate
from tqdm import tqdm

# Does not account for shadow overlapping panels or lower intensity shade caused by dispersion or indirect light bouncing off surroundings
# Makes the assumptions that ET changes lineraly with shade and that there was no shade previously on that day

# Timezone and Date Functions

def get_timezone(lat, lon):
    # Gets the timezone for a given latitude and longitude
    
    # Create a TimezoneFinder instance
    tz_finder = TimezoneFinder()

    # Find the time zone for the given longitude
    timezone_str = tz_finder.timezone_at(lat=lat, lng=lon)

    # Get the time zone offset for the current time (considering possible daylight saving time)
    now = datetime.now(pytz.timezone(timezone_str))
    timezone = now.utcoffset().total_seconds() / 3600

    return int(timezone)

def get_timezone_str(lat, lon):
    # Gets a timezone string for a given latitude and longitude. Necessary for certain functions to work

    tz_finder = TimezoneFinder()
    return tz_finder.timezone_at(lat=lat, lng=lon)

# Solar Calculation Functions

def solar_angles_skyfield(lat, lon, datetime):
    # Gets the solar azimuth and elevation angle from the skyfield python library (very accurate)

    # Load ephemeris
    ts = load.timescale()
    planets = load('de421.bsp')
    earth = planets['earth']
    sun = planets['sun']

    # Create a time object for the specified datetime
    t = ts.utc(datetime.year, datetime.month, datetime.day, datetime.hour, datetime.minute, datetime.second)

    # Create an observer location on Earth
    location = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)

    # Calculate the position of the sun at the given time from the observer's location
    astrometric = location.at(t).observe(sun).apparent()
    alt, az, _ = astrometric.altaz()

    # Solar Zenith Angle is the complement of the altitude
    solar_zenith_angle_deg = 90 - alt.degrees

    # Solar Elevation Angle is the altitude
    solar_elevation_angle_deg = alt.degrees

    # Solar Azimuth Angle
    solar_azimuth_deg = az.degrees

    return solar_elevation_angle_deg, solar_azimuth_deg

def atmospheric_refraction(solar_elevation_angle_deg): 
    # Used to adjust the solar position based on atmospheric refraction, this is very marginal but might as well be done for accuracy
    
    #Calculate Atmospheric Refraction
    if solar_elevation_angle_deg > 85:
        return 0
    elif solar_elevation_angle_deg > 5:
        return 58.1 / math.tan(math.radians(solar_elevation_angle_deg)) - 0.07 / math.pow(math.tan(math.radians(solar_elevation_angle_deg)), 3) + 0.000086 / math.pow(math.tan(math.radians(solar_elevation_angle_deg)), 5)
    elif solar_elevation_angle_deg > -0.575:
        return 1735 + solar_elevation_angle_deg * (-518.2 + solar_elevation_angle_deg * (103.4 + solar_elevation_angle_deg * (-12.79 + solar_elevation_angle_deg * 0.711)))
    else:
        return -20.772 / math.tan(math.radians(solar_elevation_angle_deg))
    
def solar_position_adj(solar_elevation_angle_deg): 
    # Uses the atmospheric refraction value to adjust the elevation angle of the sun, returns the elevation angle
    
    # Calculate Atmospheric Refraction angle
    atmos_refraction_deg = atmospheric_refraction(solar_elevation_angle_deg) / 3600

    return max(0.0000000001, solar_elevation_angle_deg + atmos_refraction_deg)

# Shade Calculation Functions

def shadow_dimensions(height, width, tilt, elevation_angle_deg, solar_azimuth, azimuth_blume): 
    # Calculates the shadow length and width while returning the area
    
    # Calculate the top and bottom height when tilted to the max and minimum amount
    height_bottom = width - (height / 2 * math.cos(math.radians(tilt)))
    height_top = width + (height / 2 * math.cos(math.radians(tilt)))

    # Calculate the length, width, and area of the Shadow
    length_shadow = (height_top / math.tan(math.radians(elevation_angle_deg))) - (height_bottom /math.tan(math.radians(elevation_angle_deg))) + (height * math.cos(math.radians(tilt)))
    #print("Length:", length_shadow)
    width_shadow = width * math.cos(math.radians(azimuth_blume - solar_azimuth))
    #print("Width:", width_shadow)

    return length_shadow * width_shadow

def shade_coverage(lat, lon, local_year, ground_area, height, width, tilt, local_hour, max_rotation, timezone, local_month, local_day, local_minute): 
    # Controller function for finding the shade coverage. Gets the solar elevation and azimuth angles, sends them to the shadow dimension function, 
    # and compares the shadow dimension to the area beneath each blume to determine the percent shade coverage

    # Convert local time to UTC
    utc_hour = (local_hour - timezone) % 24
    dt_utc = datetime(local_year, local_month, local_day, utc_hour, local_minute, 0)

    # Gets the solar elevation angle and the azimuth
    solarelevation, azimuth = solar_angles_skyfield(lat, lon, dt_utc)

    # Adjusts solar elevation angle for atmospheric refraction
    elevation = solar_position_adj(solarelevation)
    
    #Concert the Typical Azimuth to an Azimuth from South
    azimuth_S = 180 - azimuth

    # Calculate Azimuth Blume
    azimuth_blume = min(max(azimuth_S, -max_rotation), max_rotation)

    # Calculate Shadow Dimensions
    area_of_shadow = shadow_dimensions(height, width, tilt, elevation, azimuth_S, azimuth_blume)

    # Returns Percent Ground Coverage
    return min(1, (area_of_shadow / ground_area))

# Sunrise and Sunset Functions

def sunrise_sunset_times(lat, lon, year):
    # Gets the sunrise and sunset times based on a given latitude, longitude, and year. Returns an array which contains the sunrise and sunset at two week intervals.
    # Only iterates once every two weeks because this is by far the most time intensive function

    # Setting basic variables for skyfield library
    ts = load.timescale()
    planets = load('de421.bsp')
    location = Topos(latitude_degrees=lat, longitude_degrees=lon)

    # Setting the necessary variables for iteration
    start_date = datetime(year, 1, 1)
    end_date = datetime(year + 1, 1, 1)
    iteration_days = 14
    iteration_step = timedelta(days=iteration_days)
    total_days = round(((end_date - start_date).days) / iteration_days, 0)

    # Creating the array to store all the data
    sunrise_sunset_pairs = []

    # Initialize progress bar
    pbarss = tqdm(total=total_days, desc="Processing Sunrise and Sunset Times")

    # Iterates at two week intervals to get the sunrise and sunset stored in the above array
    while start_date < end_date:
        t0 = ts.utc(start_date.year, start_date.month, start_date.day, 4)
        t1 = ts.utc(start_date.year, start_date.month, start_date.day + 1, 4)

        times, events = almanac.find_discrete(t0, t1, almanac.sunrise_sunset(planets, location))
        
        # Differentiates between sunrise and sunset values given by skyfield and adds them to the array
        if len(times) >= 2:  # Expecting at least one sunrise and one sunset
            sunrise = times[0].astimezone(pytz.timezone(get_timezone_str(lat, lon)))
            sunset = times[1].astimezone(pytz.timezone(get_timezone_str(lat, lon)))
            sunrise_sunset_pairs.append((sunrise, sunset))

        # Update progress bar
        pbarss.update(1)
        start_date += iteration_step
    # Close progress bar
    pbarss.close()
    return sunrise_sunset_pairs

def find_closest_sunrise_sunset(sunrise_sunset_pairs, target_date, lat, lon):
    # Finds the closest sunrise and sunset values for a given day since there is only one sunrise and sunset value for every two weeks. 
    
    # Get the timezone string for the given latitude and longitude
    tz_str = get_timezone_str(lat, lon)
    tz = pytz.timezone(tz_str)

    # Make target_date offset-aware
    target_date_aware = tz.localize(target_date)

    # Find the pair with the minimum difference and returns it
    return min(sunrise_sunset_pairs, key=lambda pair: abs(target_date_aware - pair[0]))

# Daily Iteration Functions

def iterate_through_year(lat, lon, year, ground_area, height, width, tilt, max_rotation, timezone, sunrise_sunset_pairs):
    # Iterates for each day of the year to get the shade values for each day. Returns an array with the shade values for each day of the specified year

    # Creating the array for the daily shade values and the day values for the funciton to iterate properly
    shade_results = []
    start_date = datetime(year, 1, 1)
    end_date = datetime(year + 1, 1, 1)
    total_days = (end_date - start_date).days
    current_date = start_date

    # Initialize progress bar
    pbary = tqdm(total=total_days, desc="Processing Year")

    # Iterates once a day, running the iterate_sunrise_to_sunset function which gets the average shade value for each day
    while current_date < end_date:
        month = current_date.month
        day = current_date.day
        daily_shade = iterate_sunrise_to_sunset(sunrise_sunset_pairs, month, day, lat, lon, year, ground_area, height, width, tilt, max_rotation, timezone)

        # Storing both the date and the shade value
        shade_results.append({
            'time': current_date.strftime('%Y-%m-%d'),
            'shade': daily_shade
        })
        # Update progress bar
        pbary.update(1)

        # Iterate to next day
        current_date += timedelta(days=1)
    # Close progress bar
    pbary.close()
    return shade_results

def iterate_sunrise_to_sunset(sunrise_sunset_pairs, month, day, lat, lon, year, ground_area, height, width, tilt, max_rotation, timezone):
    
    # Sets this function's date variable to the current day being iterated
    target_date = datetime(year, month, day)

    # Find the closest sunrise and sunset values for the given day from the array holding values from every 2 weeks
    sunrise, sunset = find_closest_sunrise_sunset(sunrise_sunset_pairs, target_date, lat, lon)

    # Rounds the sunrise and sunset to the nearest minute for easier calculation
    sunrise_rounded = sunrise.replace(second=0, microsecond=0) + timedelta(minutes=1 if sunrise.second or sunrise.microsecond else 0)
    sunset_rounded = sunset.replace(second=0, microsecond=0)

    # Resetting values for variables used in iteration
    total_shade_coverage = 0
    count = 0

    # Sets iteration variable before iteration begins
    current_time = sunrise_rounded

    # Iterates continuously until after sunset to get the shade for each hour between sunrise and sunset
    while current_time <= sunset_rounded:
        minute = current_time.minute
        hour = current_time.hour
        shade_cover = shade_coverage(lat, lon, year, ground_area, height, width, tilt, hour, max_rotation, timezone, month, day, minute)
        #print("Shade Cover:", shade_cover)
        total_shade_coverage += shade_cover
        count += 1
        current_time += timedelta(minutes=60)  # Iterative Jump

    # Takes the average of all the shade values to get a daily value and returns it

    return total_shade_coverage / count if count else 0

# Evapotranspiration Data Functions

def get_et_data(lat, lon, api_key, formatted_date): 
    # Pulls ET data for specified year, returns a list with data and corresponding dates

    # Sets the url for the desired dataset
    url = "https://openet-api.org/raster/timeseries/point"

    # Sets all required variables for and API pull
    headers = {"Authorization": api_key}
    args = {
        "date_range": formatted_date, # Date must be formatted correctly for correct data pull, see adjusted_evapotranspiration function for how this is done
        "interval": "daily", #daily or monthly
        "geometry": [lon, lat],
        "model": "Ensemble",
        "variable": "ET",
        "reference_et": "gridMET",
        "units": "mm",
        "file_format": "JSON"
    }

    response = requests.post(url, headers=headers, json=args)
    if response.status_code == 200:
        return response.json()  # Adjust according to the actual format of response
    else:
        return None

def evapotranspiration(lat, lon, date): 
    # Controller function for the ET data

    # Sets the api key to be used when making a data pull
    api_key = "ts4mbq4UCbap9O2NkX4QAQhzOq25Eba5mFVtAFm3nIyc7lfglaKXFNqDEaiB"

    # Runs the function used for making the api pull
    et_data = get_et_data(lat, lon, api_key, date)

    # Lets you know if the API pull was successful, if it was it just returns the data
    if et_data:
        return et_data
    else:
        print("Failed to retrieve ET data.")

def adjusted_evapotranspiration(lat, lon, year, ground_area, height, width, tilt, max_rotation, timezone):
    # Gets the ET values and the Shade values and returns an array of the corresponding product of the ET shade values and shade values

    # Necessary variables to call certain functions
    start_date = datetime(year, 1, 1)
    formatted_date = [start_date.strftime("%Y-01-01"), start_date.strftime("%Y-12-31")]
    sunrise_sunset_pairs = sunrise_sunset_times(lat, lon, year)
    
    # Gets shade and ET values
    daily_shade = iterate_through_year(lat, lon, year, ground_area, height, width, tilt, max_rotation, timezone, sunrise_sunset_pairs)
    et_data = evapotranspiration(lat, lon, formatted_date)

    # Returns an array of the corresponding product of the ET shade values and shade values
    return list(map(lambda dm: dm[0]['et'] * (1- dm[1]['shade']), zip(et_data, daily_shade))), daily_shade, et_data

# Data Summation and Comparison Functions

def sum_et_data_between_dates(et_data, start_date, end_date):
    # Get sum of ET Specified Date Range, only necessary if additional calculations for irrigation are done (precipitation difference)

    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
    return sum(item['et'] for item in et_data if 'et' in item and start_date_obj <= datetime.strptime(item['time'], '%Y-%m-%d') <= end_date_obj)

def sum_adjusted_et_data_between_dates(adjusted_et_data, daily_shade, start_date, end_date):
    # Get sum of Adjusted ET for Specified Date Range, only necessary if additional calculations for irrigation are done (precipitation difference)

    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
    return sum(et for et, shade in zip(adjusted_et_data, daily_shade) if start_date_obj <= datetime.strptime(shade['time'], '%Y-%m-%d') <= end_date_obj)

# Plotting Function

def plot_values(adjusted_et_values, daily_shade, et_data):
    
    # Preparing the data for plotting
    dates = [item['time'] for item in daily_shade]
    shade_values = [item['shade'] for item in daily_shade]
    et_values = [item['et'] for item in et_data]
    adjusted_et_values = [item for item in adjusted_et_values]
    cumulative_et = list(accumulate([item['et'] for item in et_data if 'et' in item]))
    cumulative_adjusted_et = list(accumulate(adjusted_et_values))

    # Choosing plot format and data to plot
    plt.figure(figsize=(15, 6))
    plt.plot(dates, shade_values, label='Daily Shade', color='green')
    plt.plot(dates, et_values, label='Evapotranspiration (ET)', color='blue')
    plt.plot(dates, adjusted_et_values, label='Adjusted ET', color='red')

    # Customizing the plot
    plt.xlabel('Date')
    plt.ylabel('ET (mm / acre)')
    plt.title('Daily Shade, ET, and Adjusted ET Over Time')
    plt.xticks(dates[::30], rotation=45)  # Showing a tick every 30 days for clarity
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    
    # Choosing plot format and data to plot
    plt.figure(figsize=(15, 6))
    plt.plot(dates, cumulative_et, label='Cumulative ET', color='blue')
    plt.plot(dates, cumulative_adjusted_et, label='Cumulative Adjusted ET', color='red')

    # Customizing the plot
    plt.xlabel('Date')
    plt.ylabel('Cumulative ET (mm / acre / yr)')
    plt.title('Cumulative ET and Cumulative Adjusted ET Over Time')
    plt.xticks(dates[::30], rotation=45)  # Showing a tick every 30 days for clarity
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    # Show the plot
    plt.show()

# Water Savings Calculation Function

def water_saved(et_data, adjusted_et_values):
    # Gets the annual ET and adjusted ET values and takes the difference to return how much water would have been saved in the specified year (from ET)
    
    # Get the total annual ET
    et_annual = sum(item['et'] for item in et_data if 'et' in item)
    print("ET Before:", round(et_annual, 2))
    # Get the total annual adjusted ET
    adjusted_et_annual = sum(adjusted_et_values)
    print("ET After:", round(adjusted_et_annual, 2))

    # Returns the difference (how much less water evaporated or transpired)
    return et_annual - adjusted_et_annual

# Parameter Initialization and Main Function

def get_valid_year():
    while True:
        try:
            year = int(input("Enter year: "))
            if 2018 <= year <= 2022:
                return year
            else:
                print("Year must be between 2018 and 2022. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a valid year.")

def get_valid_latitude():
    while True:
        try:
            latitude = float(input("Enter latitude: "))
            if -90 <= latitude <= 90:
                return latitude
            else:
                print("Invalid latitude. Please enter a value between -90 and 90.")
        except ValueError:
            print("Invalid input. Please enter a valid number for latitude.")

def get_valid_longitude():
    while True:
        try:
            longitude = float(input("Enter longitude: "))
            if -180 <= longitude <= 180:
                return longitude
            else:
                print("Invalid longitude. Please enter a value between -180 and 180.")
        except ValueError:
            print("Invalid input. Please enter a valid number for longitude.")


def calculation_parameters(): 
    # Gets all the required user inputs for modular data pulls and calculations
    
    #Latitude, Longitude, and year
    #lat = float(42)
    #lon = float(-120)
    #year = 2022
    lat = float(get_valid_latitude())
    lon = float(get_valid_longitude())
    year = int(get_valid_year())
    
    #Site and Array Inputs
    #NS_spacing = input("Enter North-South Spacing: ") 
    #EW_spacing = input("Enter East-West Spacing: ") 
    
    NS_spacing = 36
    EW_spacing = 36
    ground_area = NS_spacing * EW_spacing #area around a single blume

    #Blume Variables
    height = 22.3
    width = 18.3
    tilt = 35
    max_rotation = 45
    #height = input("Enter blume height: ")
    #width = input("Enter blume width: ")
    #tilt = input("Enter angle of panels to horizontal: ")
    #max_rotation = input("Enter max rotation angle about vertical axis: ")
    
    #Gets timezone value from timezone function (not timezone string function)
    timezone = get_timezone(lat, lon)
    
    return lat, lon, year, ground_area, height, width, tilt, max_rotation, timezone

def main():
    
    # Get Calculation Parameters
    lat, lon, year, ground_area, height, width, tilt, max_rotation, timezone = calculation_parameters()

    # Get ET, Adjusted ET, and Daily Shade Values
    adjusted_et_values, daily_shade, et_data = adjusted_evapotranspiration(lat, lon, year, ground_area, height, width, tilt, max_rotation, timezone)

    # Get sum of ET and Adjusted ET for Specified Date Range, only necessary if additional calculations for irrigation are done (precipitation difference)
    et_sum_between_dates = sum_et_data_between_dates(et_data, '2022-01-01', '2022-12-31')
    adjusted_et_sum_between_dates = sum_adjusted_et_data_between_dates(adjusted_et_values, daily_shade, '2022-01-01', '2022-12-31')

    # Determine how much water was saved over the course of a year (for one acre)
    water = water_saved(et_data, adjusted_et_values)
    waterin = water / 25.4
    water = round(water, 2)
    waterin = round(waterin, 2)
    
    print("Water Saved: ", water, " mm/acre")
    print("Water Saved: ", waterin, " in/acre")
    # Create two plots to present data
    plot_values(adjusted_et_values, daily_shade, et_data)
    
if __name__ == "__main__":
    main()