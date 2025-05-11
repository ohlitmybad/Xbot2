import time
import random
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
from requests_oauthlib import OAuth1
from selenium.webdriver.chrome.options import Options
import os
import re


API_KEY = '9VG6eYAmiPw8mvRVUuN23BSee'
API_KEY_SECRET = 'O2r4p5hyCZ7ZYjsVK73RAnReH7GnZQKahswukRbOOSfUoLevGp'
ACCESS_TOKEN = '1389871650125094913-tHVJvdSksSHn89CCTQhgxfNpF1QENW'
ACCESS_TOKEN_SECRET = 'LWrKGzeokBFq7IxbA18gFsyE4bAGgeJYc6gTNDTIUJoV2'

class TestUntitled:
    def setup_method(self, method):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        self.driver = webdriver.Chrome(options=chrome_options)

    def teardown_method(self):
        self.driver.quit()
        
    def capture_first_five_lines(self):
        body_element = self.driver.find_element(By.TAG_NAME, "body")
        body_text = body_element.text
    # Split the text into lines and capture the first 5 lines
        lines = body_text.splitlines()
        specific_lines = "\n".join(lines[200:205])
    
    # Replace the specified text
        replacements = {
        "1. ": "🥇 ",
        "2. ": "🥈 ",
        "3. ": "🥉 ",
        "4. ": "🏅 ",
        "5. ": "🏅 ",
        ") ": ") — "
    }
    
        for old, new in replacements.items():
            specific_lines = specific_lines.replace(old, new)

        return specific_lines

    
    def test_untitled(self):
        self.driver.get("https://datamb.football/proindex/")
        time.sleep(1)
        self.driver.set_window_size(976, 772)
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.NAME, "eml"))
        ).send_keys("tombolivier@gmail.com")
        
        self.driver.find_element(By.NAME, "pwd").send_keys("password1")
        self.driver.find_element(By.CSS_SELECTOR, ".SFfrm button").click()
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "metric"))
        )

# Define position options
        position_options = ["Goalkeeper", "Centre-back", "Full-back", "Midfielder", "Winger", "Striker", "All positions"]

        weights2 = [0.03, 0.09, 0.09, 0.21, 0.18, 0.17, 0.23]  # Adjust the weights as needed

        selected_position = random.choices(position_options, weights=weights2, k=1)[0]

# Define metric options based on selected position
        if selected_position == "Goalkeeper":
         metric_options = [
        "Shots conceded per 90", "xG conceded per 90", 
        "Prevented goals per 90", "Save percentage %", "Pass completion %", 
        "Progressive pass accuracy %", "Short pass completion %", 
        "Accurate long passes %", "Pass completion (to final third) %", 
        "Progressive passes per 90", "Passes to final third per 90", "Passes per 90", 
        "Long passes per 90", "Short passes per 90", 
        "Possessions won per 90", 
        "Aerial duels per 90", "Saves per 90"
    ]
        elif selected_position == "Centre-back":
            metric_options = [
    "Passes completed per 90", "Long passes completed per 90", "Accurate passes to final third per 90", "Through passes completed per 90", "Progressive passes completed per 90", "Progressive passes (PAdj)", "Forward pass ratio", "Possessions won - lost per 90", "Possession +/-", "Progressive actions per 90", "Progressive action rate" 

    ]
        elif selected_position == "Full-back":
    # Define metrics for Full-back
            metric_options = [
 "xA per 100 passes", "Chance creation ratio",  "xG+xA per 90", "Assists - xA per 90", "Passes completed per 90", "Accurate passes to final third per 90", "Through passes completed per 90", "Progressive passes completed per 90", "Progressive passes (PAdj)", "Forward pass ratio", "Successful dribbles per 90", "Dribbles per 100 touches", "Ball-carrying frequency", "Duels won %", "Duels won per 90", "Possessions won - lost per 90", "Possession +/-", "Progressive actions per 90", "Progressive action rate"
    ]
        elif selected_position == "Midfielder":
    # Define metrics for Midfielder
            metric_options = [
"Goals - xG per 90", "xG per 100 touches", "Goals per 100 touches", "npxG per 90", "xA per 100 passes", "Chance creation ratio",  "NPG+A per 90", "xG+xA per 90", "npxG+xA per 90", "Assists - xA per 90", "Pre-assists per 90", "Passes completed per 90", "Long passes completed per 90", "Accurate passes to final third per 90", "Through passes completed per 90", "Progressive passes completed per 90", "Progressive passes (PAdj)", "Forward pass ratio", "Dribbles per 100 touches", "Ball-carrying frequency", "Duels won %", "Duels won per 90", "Possessions won - lost per 90", "Possession +/-", "Progressive actions per 90", "Progressive action rate"
    ]
        elif selected_position == "Winger":
    # Define metrics for Winger
            metric_options = [
"xG/Shot", "Goals - xG per 90", "xG per 100 touches", "Shot frequency", "Goals per 100 touches", "npxG per 90", "npxG/Shot", "xA per 100 passes", "Chance creation ratio",  "NPG+A per 90", "xG+xA per 90", "npxG+xA per 90", "Assists - xA per 90", "Progressive passes (PAdj)", "Successful dribbles per 90", "Dribbles per 100 touches", "Ball-carrying frequency", "Duels won %", "Duels won per 90", "Progressive actions per 90", "Progressive action rate"
    ]
        elif selected_position == "Striker":
    # Define metrics for Striker
            metric_options = [
"xG/Shot", "Goals - xG per 90", "xG per 100 touches", "Shot frequency", "Goals per 100 touches", "npxG per 90", "npxG/Shot", "xA per 100 passes", "Chance creation ratio",  "NPG+A per 90", "xG+xA per 90", "npxG+xA per 90", "Dribbles per 100 touches"    ]
        elif selected_position == "All positions":
            metric_options = [
"xG/Shot", "Goals - xG per 90", "xG per 100 touches", "Shot frequency", "Goals per 100 touches", "npxG per 90", "npxG/Shot","xA per 100 passes", "Chance creation ratio",  "NPG+A per 90", "xG+xA per 90", "npxG+xA per 90", "Assists - xA per 90", "Pre-assists per 90","Passes completed per 90", "Long passes completed per 90", "Accurate passes to final third per 90", "Through passes completed per 90", "Progressive passes completed per 90", "Progressive passes (PAdj)","Forward pass ratio", "Successful dribbles per 90", "Dribbles per 100 touches", "Ball-carrying frequency", "Duels won %", "Duels won per 90", "Possessions won - lost per 90", "Possession +/-", "Progressive actions per 90", "Progressive action rate"
    ]
            
        selected_metric = random.choice(metric_options)


        league_options = [
    "🇪🇺 Top 5 Leagues",
    "🇪🇺 Top 7 Leagues",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
    "🇪🇸 La Liga",
    "🇩🇪 Bundesliga", 
    "🇮🇹 Serie A"
]

# Define weights for each league category
        weights = [
    0.44,
    0.33,
    0.12,
    0.06, 
    0.02,
    0.03        
]

# Ensure weights match the length of league_options
        assert len(weights) == len(league_options), "Weights length must match the league options length"

# Randomly select a league based on the defined weights
        selected_league = random.choices(league_options, weights=weights, k=1)[0]

    

        # Define age options based on selected league
        if selected_league in ["🇪🇺 Top 7 Leagues", "🇪🇺 Top 5 Leagues", "🌍 All Leagues", "🌍 Outside Top 7"]:
            if selected_position == "All positions":
                age_options = ["Age", "U19", "U21", "U23"]
                selected_age = random.choice(age_options)

            elif selected_position != "Goalkeeper":
                age_options = ["Age", "U21", "U23"]
                selected_age = random.choice(age_options)

            elif selected_position in "Goalkeeper":
                age_options = ["Age", "U23"]
                selected_age = random.choice(age_options)
        else:
            selected_age = "Age"


        # Select metric
        dropdown = self.driver.find_element(By.ID, "metric")
        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f"//option[. = 'Minutes played']"))).click()

        # Select position
        dropdown = self.driver.find_element(By.ID, "position")
        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f"//option[. = '{selected_position}']"))
        ).click()

        dropdown = self.driver.find_element(By.ID, "metric")
        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f"//option[. = '{selected_metric}']"))
        ).click()


        # Select league
        dropdown = self.driver.find_element(By.ID, "league")
        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f"//option[. = '{selected_league}']"))
        ).click()

                # Select age
        dropdown = self.driver.find_element(By.ID, "age")
        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f"//option[. = '{selected_age}']"))
        ).click()

        # Wait for the label to be visible and scroll into view
        label = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, 'label[for="toggleMetrics"]'))
        )
        self.driver.execute_script("arguments[0].scrollIntoView(true);", label)

        # Use JavaScript to click the label
        try:
            self.driver.execute_script("arguments[0].click();", label)
        except Exception as e:
            raise e
        
        self.driver.execute_script("""
    document.documentElement.style.overflow = 'hidden';  // Hide horizontal and vertical scroll bars
    document.body.style.overflow = 'hidden';  // Hide scroll bars on body
    var resultContainer = document.querySelector('.result-container');
    if (resultContainer) {
        resultContainer.style.overflow = 'hidden';  // Hide scroll bars on result-container div
    }
""")

      
        # Save screenshot
        self.driver.save_screenshot('screenshot.png')
        specific_text = self.capture_first_five_lines()

        # Upload the screenshot to Twitter
        upload_url = "https://upload.twitter.com/1.1/media/upload.json"
        auth = OAuth1(API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
        
        with open('screenshot.png', 'rb') as image_file:
            files = {'media': image_file}
            response = requests.post(upload_url, files=files, auth=auth)
        
        if response.status_code != 200:
            print("Failed to upload media:", response.status_code, response.text)
            return
        
        media_id = response.json()['media_id_string']

        # Add alt text to the uploaded image
        alt_text = "This is an automated tweet 🤖\n\nPosition, league, age and metrics were chosen randomly in the 2024/25 dataset.\n\nPlayer age and team refer to their age and team during the season.\n\nPositions are determined via the player's average heat map.\n\nSubscribe to DataMB Pro for more leagues and tools!"  # Add your alt text here
        metadata_url = "https://upload.twitter.com/1.1/media/metadata/create.json"
        metadata_payload = {
    "media_id": media_id,
    "alt_text": {"text": alt_text}
}
        metadata_response = requests.post(metadata_url, json=metadata_payload, auth=auth)

        if metadata_response.status_code != 200:
            print("Failed to create metadata:", metadata_response.status_code, metadata_response.text)
            return
        
        selected_metric = selected_metric.replace(" per 90", "")
        selected_position = selected_position.replace("er", "ers")
        selected_position = selected_position.replace("ack", "acks")
        selected_position = selected_position.replace("All positions", "Players")
        selected_age = selected_age.replace("Age", "")


        


        # Create the tweet text dynamically
        tweet_text = f"{selected_league} {selected_age} {selected_position} : {selected_metric}\n\n{specific_text}\n\n📊 datamb.football"
        tweet_text = tweet_text.replace("  ", " ")
        tweet_text = tweet_text.replace(" Wanderers", "")
        tweet_text = tweet_text.replace("Borussia ", "")
        tweet_text = tweet_text.replace("Deportivo ", "")
        tweet_text = tweet_text.replace("Manchester", "Man")
        tweet_text = tweet_text.replace(" Hotspur", "")
        tweet_text = tweet_text.replace("West Ham United", "West Ham")
        tweet_text = tweet_text.replace("Celta de", "Celta")
        tweet_text = tweet_text.replace("Olympique Lyonnais", "Lyon")
        tweet_text = tweet_text.replace("Olympique Marseille", "Marseille")
        tweet_text = tweet_text.replace("Fortuna ", "")
        tweet_text = tweet_text.replace("Eintracht ", "")
        tweet_text = tweet_text.replace("Newcastle United", "Newcastle")
        tweet_text = tweet_text.replace("🇧🇪 Belgium", "🇧🇪 Belgium Pro League")
        tweet_text = tweet_text.replace("🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scotland", "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scottish Premiership")
        tweet_text = tweet_text.replace("🇦🇹 Austria", "🇦🇹 Austrian Bundesliga")
        tweet_text = tweet_text.replace("🇨🇭 Switzerland", "🇨🇭 Swiss Super League")
        tweet_text = tweet_text.replace("🇹🇷 Türkiye", "🇹🇷 Süper Lig")
        tweet_text = tweet_text.replace("🇩🇰 Denmark", "🇩🇰 Superliga")
        tweet_text = tweet_text.replace("🇸🇪 Sweden", "🇸🇪 Allsvenskan")
        tweet_text = tweet_text.replace("🇳🇴 Norway", "🇳🇴 Eliteserien")
        tweet_text = tweet_text.replace("🇭🇷 Croatia", "🇭🇷 Croatia HNL")
        tweet_text = tweet_text.replace("🇷🇸 Serbia", "🇷🇸 SuperLiga")
        tweet_text = tweet_text.replace("🇨🇿 Czech Republic", "🇨🇿 Czech First League")
        tweet_text = tweet_text.replace("🇵🇱 Poland", "🇵🇱 Ekstraklasa")
        tweet_text = tweet_text.replace("🇺🇦 Ukraine", "🇺🇦 Premier League")
        tweet_text = tweet_text.replace("🇷🇺 Russia", "🇷🇺 Premier League")
        tweet_text = tweet_text.replace("🇬🇷 Greece", "🇬🇷 Super League")
        tweet_text = tweet_text.replace("🇯🇵 Japan", "🇯🇵 J1 League")
        tweet_text = tweet_text.replace("🇰🇷 Korea", "🇰🇷 K League 1")
        tweet_text = tweet_text.replace("🇸🇦 Saudi Arabia", "🇸🇦 Saudi Pro League")
        tweet_text = tweet_text.replace("🇺🇸 United States", "🇺🇸 MLS")
        tweet_text = tweet_text.replace("🇲🇽 Mexico", "🇲🇽 Liga MX")
        tweet_text = tweet_text.replace("🇧🇷 Brazil", "🇧🇷 Série A")
        tweet_text = tweet_text.replace("🇦🇷 Argentina", "🇦🇷 Primera División")
        tweet_text = tweet_text.replace("🇺🇾 Uruguay", "🇺🇾 Primera División")
        tweet_text = tweet_text.replace("🇨🇱 Chile", "🇨🇱 Primera División")
        tweet_text = tweet_text.replace("🇨🇴 Colombia", "🇨🇴 Primera A")
        tweet_text = tweet_text.replace("🇪🇨 Ecuador", "🇪🇨 Serie A")
        tweet_text = tweet_text.replace("🇵🇾 Paraguay", "🇵🇾 Primera División")
        tweet_text = tweet_text.replace("Short / medium", "Short")
        tweet_text = tweet_text.replace("short / medium", "short")
        tweet_text = tweet_text.replace("7 Leagues", "7 League")
        tweet_text = tweet_text.replace("5 Leagues", "5 League")
        tweet_text = tweet_text.replace("Wingers", "Wingers & Att Mid")
        

        time.sleep(150*60)

        # Create the tweet with the media attached
        tweet_url = "https://api.twitter.com/2/tweets"
        payload = {
            "text": tweet_text,
            "media": {
                "media_ids": [media_id]
            }
        }
        
        response = requests.post(tweet_url, json=payload, auth=auth)
        
        if response.status_code == 201:
            print("Tweet successfully sent!")
            first_tweet_id = response.json()['data']['id']
            
            # Create the follow-up tweet
            follow_up_text = "Compare Top 7 League players, or subscribe for more leagues, metrics, and tools ⤵️ datamb.football"
            follow_up_payload = {
                "text": follow_up_text,
                "reply": {
                    "in_reply_to_tweet_id": first_tweet_id
                }
            }

            
            # Send the follow-up tweet
            follow_up_response = requests.post(tweet_url, json=follow_up_payload, auth=auth)
            
            if follow_up_response.status_code == 201:
                print("Follow-up tweet successfully sent!")
            else:
                print("Failed to send follow-up tweet:", follow_up_response.status_code, follow_up_response.text)

        else:
            print("Failed to send tweet:", response.status_code, response.text)

        


if __name__ == "__main__":
    pytest.main()
