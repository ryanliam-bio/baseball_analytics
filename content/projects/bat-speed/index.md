---
title: "Bat Speed Analysis"
summary: "A deep dive into swing velocity data using Python."
date: 2025-06-30
tags: ["Python", "Statcast"]
math: true
image:
  caption: 'YoY Bat Speed/Length $\Delta$'
  focal_point: "Smart"
  preview_only: false
---

<a href="bat-speed-trials.ipynb" download="MLB_Bat_Speed_Analysis.ipynb" class="btn btn-primary">
  📥 Download Full Notebook
</a>

### Project Overview

import os 
import urllib.request
import matplotlib.pyplot as plt
from matplotlib.offsetbox import AnnotationBbox, OffsetImage

import csv
import pandas as pd

def read_csv(file_path):
    df = pd.read_csv(file_path)
    return df



swings25 = read_csv('2025 Bat Speed.csv')
#initially called df instead of speed25
swings25.name = swings25.name.str.split(', ').map(lambda x : ' '.join(x[::-1]))
#reverses lastname/firstname

swings24 = read_csv('2024 Bat Speed.csv')
swings24.name = swings24.name.str.split(', ').map(lambda x : ' '.join(x[::-1]))

print("Swing speed: ", swings25.loc[1]['avg_bat_speed'])

swings24.head

swings25['converted_speed'] = swings25['avg_bat_speed']*1.46667
#gives us bat speed in ft/sec
swings25['bat_accel'] = swings25['converted_speed']*swings25['converted_speed']/swings25['swing_length']


swings24['converted_speed'] = swings24['avg_bat_speed']*1.46667
#gives us bat speed in ft/sec
swings24['bat_accel'] = swings24['converted_speed']*swings24['converted_speed']/swings24['swing_length']

swings25.bat_accel

combined_swings = pd.merge(swings25, swings24, on='name')
#2024 and 2025 swing data
combined_swings['yoy_speed'] = combined_swings['avg_bat_speed_x']-combined_swings['avg_bat_speed_y']
combined_swings['yoy_length'] = combined_swings['swing_length_x']-combined_swings['swing_length_y']
combined_swings['yoy_accel'] = combined_swings['bat_accel_x']-combined_swings['bat_accel_y']

combined_swings.to_csv('combined bat tracking.csv', index=False)

#provides 2024/2025 data to play with

period1 = read_csv('3.27-4.7 Ind Swings.csv')
period2 = read_csv('4.8-4.20 Ind Swings.csv')
ind_swings = pd.concat([period1, period2], ignore_index=True)

ind_swings.player_name = ind_swings.player_name.str.split(', ').map(lambda x : ' '.join(x[::-1]))

ind_swings =ind_swings.rename(columns={'player_name':'name'})




grouped = ind_swings.groupby('name')
#this groups all swings together by name
max_speed = grouped['bat_speed'].max()
ninefive = grouped['bat_speed'].quantile(0.95)
ninetieth = grouped['bat_speed'].quantile(0.9)
eightfive = grouped['bat_speed'].quantile(0.85)
eightieth = grouped['bat_speed'].quantile(0.8)
sevenfive =grouped['bat_speed'].quantile(0.75)

twofive =grouped['bat_speed'].quantile(0.25)
twentieth = grouped['bat_speed'].quantile(0.20)
fifteenth = grouped['bat_speed'].quantile(0.15)
tenth = grouped['bat_speed'].quantile(0.1)
fifth = grouped['bat_speed'].quantile(0.05)






ind_swings = read_csv('6.14 7.14 ind swings.csv')
#this is every individual swing taken in the specified date range
ind_swings.player_name = ind_swings.player_name.str.split(', ').map(lambda x : ' '.join(x[::-1]))

ind_swings =ind_swings.rename(columns={'player_name':'name'})




grouped = ind_swings.groupby('name')
#this groups all swings together by name
max_speed = grouped['bat_speed'].max()
ninefive = grouped['bat_speed'].quantile(0.95)
ninetieth = grouped['bat_speed'].quantile(0.9)
eightfive = grouped['bat_speed'].quantile(0.85)
eightieth = grouped['bat_speed'].quantile(0.8)
sevenfive =grouped['bat_speed'].quantile(0.75)

twofive =grouped['bat_speed'].quantile(0.25)
twentieth = grouped['bat_speed'].quantile(0.20)
fifteenth = grouped['bat_speed'].quantile(0.15)
tenth = grouped['bat_speed'].quantile(0.1)
fifth = grouped['bat_speed'].quantile(0.05)


#Convert the Series to a DataFrame.
#max_swings = max_speed.reset_index().rename(columns={'index': 'player_name'})
#max_swings =max_swings.rename(columns={'player_name':'name'})
#initially I only used max speed, but in using all these other metrics it's much easier to rename the full ind_swings frame

max_speed

swing_stats = pd.DataFrame({'max_speed': max_speed,'fifth': fifth,'tenth': tenth, 'fifteenth': fifteenth,
                            'twentieth': twentieth,'twofive': twofive, 'sevenfive': sevenfive,'eightieth': eightieth,
                            'eightfive': eightfive, 'ninetieth': ninetieth, 'ninefive': ninefive})

swing_stats



# Merge the DataFrame with the original DataFrame
swing_percentiles = pd.merge(swings25, swing_stats, on="name", how="left")
swing_percentiles.to_csv('6.14 7.14 Ind Bat Tracking.csv', index=False)

plt.rcParams["figure.figsize"] = [10, 7]
plt.rcParams['figure.autolayout'] = True


x=combined_swings['yoy_length']
y = combined_swings['yoy_speed']


plt.xlim(-1,1)
plt.ylim(-8, 8)

# Create the scatter plot
plt.scatter(x, y)

# Add names to each point
for i, name in enumerate(combined_swings['name']):
    plt.annotate(name, (x[i], y[i]))

# Add labels and title (optional)
plt.xlabel(r'Swing Length $\Delta$')
plt.ylabel('Bat Speed$\Delta $')
plt.title('2024 to 2025 Swing Changes')


plt.show()



yoy = pd.merge(df, swings24, on='player_name')
yoy

plt.rcParams["figure.figsize"] = [10, 7]
plt.rcParams['figure.autolayout'] = True

y = yoy['bat_speed']
x=yoy['avg_bat_speed']

plt.xlim(63, 83)
plt.ylim(63, 83)

# Create the scatter plot
plt.scatter(x, y)

# Add names to each point
for i, name in enumerate(yoy['player_name']):
    plt.annotate(name, (x[i], y[i]),fontsize=8)

# Add labels and title (optional)
plt.xlabel('2024 Bat Speed')
plt.ylabel('2025 Bat Speed')
plt.title('2024 Regular Season vs 2025 Spring Training')

plt.plot([63,85],[63,85])

plt.rcParams['xtick.labelsize'] = 12 # Font size of the x-axis tick labels
plt.rcParams['ytick.labelsize'] = 12 # Font size of the y-axis tick labels
plt.rcParams['axes.labelsize'] = 15

plt.show()

