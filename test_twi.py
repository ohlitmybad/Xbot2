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


# Your credentials
API_KEY = 'cw0P0n0oJcpzb4iA2NQm0kWod'
API_KEY_SECRET = '2XwwsJokAPGhYPBTjqTzVwLBK3u7jxTI8oRWaqmWWEDYjbKTVs'
ACCESS_TOKEN = '1670542627257589761-23tNDvYcX2SUTt7ucclcDpbci5XdyW'
ACCESS_TOKEN_SECRET = '1MHEaYkipURtIRT7d1daNRAIkrTlIPdnrBOGxhOCp27FX'

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
        specific_lines = "\n".join(lines[136:141])
    
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
        self.driver.set_window_size(976, 630)
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.NAME, "eml"))
        ).send_keys("tombolivier@gmail.com")
        
        self.driver.find_element(By.NAME, "pwd").send_keys("password")
        self.driver.find_element(By.CSS_SELECTOR, ".SFmfllog:nth-child(3) button").click()
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "metric"))
        )

# Define position options
        position_options = ["Goalkeeper", "Centre-back", "Full-back", "Midfielder", "Winger", "Striker", "All positions"]

# Randomize selection of position
        selected_position = random.choice(position_options)

# Define metric options based on selected position
        if selected_position == "Goalkeeper":
         metric_options = [
        "Shots against per 90", "xG against per 90", 
        "Prevented goals per 90", "Save rate %", "Accurate passes %", 
        "Accurate progressive passes %", "Accurate short / medium passes %", 
        "Accurate long passes %", "Accurate passes to final third %", 
        "Progressive passes per 90", "Passes to final third per 90", "Passes per 90", 
        "Forward passes per 90", "Long passes per 90", "Short / medium passes per 90", 
        "Successful defensive actions per 90", "Defensive duels per 90", 
        "Aerial duels per 90"
    ]
        elif selected_position == "Centre-back":
            metric_options = [
        "Successful defensive actions per 90", "Defensive duels per 90", 
        "Aerial duels per 90", "Sliding tackles per 90", "PAdj Sliding tackles", 
        "Interceptions per 90", "PAdj Interceptions", "Dribbles per 90", 
        "Progressive runs per 90", "Passes per 90", "Forward passes per 90", 
        "Long passes per 90", "Key passes per 90", "Passes to final third per 90", 
        "Passes to penalty area per 90", "Through passes per 90", 
        "Progressive passes per 90", "Defensive duels won %", 
        "Aerial duels won %", "Accurate passes %", "Accurate forward passes %", 
        "Accurate progressive passes %", "Possession +/-"
    ]
        elif selected_position == "Full-back":
    # Define metrics for Full-back
            metric_options = [
       "Successful defensive actions per 90","Defensive duels per 90","Aerial duels per 90","Sliding tackles per 90","PAdj Sliding tackles","Interceptions per 90","PAdj Interceptions","Successful attacking actions per 90","xG per 90","Shots per 90","Crosses per 90","Dribbles per 90","Offensive duels per 90","Touches in box per 90","Progressive runs per 90","Accelerations per 90","Fouls suffered per 90","Passes per 90","Forward passes per 90","Long passes per 90","xA per 90","Shot assists per 90","Key passes per 90","Passes to final third per 90","Passes to penalty area per 90","Through passes per 90","Deep completions per 90","Progressive passes per 90","Defensive duels won %","Aerial duels won %","Accurate crosses %","Successful dribbles %","Offensive duels won %","Accurate passes %","Accurate forward passes %","Accurate progressive passes %","Possession +/-"
    ]
        elif selected_position == "Midfielder":
    # Define metrics for Midfielder
            metric_options = [
       "Successful defensive actions per 90","Defensive duels per 90","Aerial duels per 90","Sliding tackles per 90","PAdj Sliding tackles","Interceptions per 90","PAdj Interceptions","Successful attacking actions per 90","xG per 90","Shots per 90","Crosses per 90","Dribbles per 90","Offensive duels per 90","Touches in box per 90","Progressive runs per 90","Accelerations per 90","Fouls suffered per 90","Passes per 90","Forward passes per 90","Long passes per 90","xA per 90","Shot assists per 90","Key passes per 90","Passes to final third per 90","Passes to penalty area per 90","Through passes per 90","Deep completions per 90","Progressive passes per 90","Defensive duels won %","Aerial duels won %","Accurate passes %","Accurate forward passes %","Accurate progressive passes %","Successful dribbles %","Offensive duels won %","Possession +/-"
    ]
        elif selected_position == "Winger":
    # Define metrics for Winger
            metric_options = [
       "Possession +/-","Shots on target %","Goal conversion %","Accurate crosses %","Successful dribbles %","Offensive duels won %","Defensive duels won %","Aerial duels won %","Successful defensive actions per 90","Successful attacking actions per 90","xG per 90","Shots per 90","Crosses per 90","Dribbles per 90","Offensive duels per 90","Touches in box per 90","Progressive runs per 90","Accelerations per 90","Fouls suffered per 90","Passes per 90","xA per 90","Shot assists per 90","Key passes per 90","Passes to final third per 90","Passes to penalty area per 90","Through passes per 90","Deep completions per 90","Progressive passes per 90"
    ]
        elif selected_position == "Striker":
    # Define metrics for Striker
            metric_options = [
       "Successful defensive actions per 90","Aerial duels per 90","Successful attacking actions per 90","xG per 90","Shots per 90","Crosses per 90","Dribbles per 90","Offensive duels per 90","Touches in box per 90","Progressive runs per 90","Accelerations per 90","Fouls suffered per 90","xA per 90","Shot assists per 90","Key passes per 90","Passes to penalty area per 90","Through passes per 90","Deep completions per 90","Aerial duels won %","Shots on target %","Goal conversion %","Successful dribbles %","Offensive duels won %","Accurate passes %","Possession +/-"
    ]
        elif selected_position == "All positions":
            metric_options = [
       "Successful defensive actions per 90","Defensive duels per 90","Aerial duels per 90","Sliding tackles per 90","PAdj Sliding tackles","Interceptions per 90","PAdj Interceptions","Successful attacking actions per 90","xG per 90","Shots per 90","Crosses per 90","Dribbles per 90","Offensive duels per 90","Touches in box per 90","Progressive runs per 90","Accelerations per 90","Fouls suffered per 90","Passes per 90","Forward passes per 90","Long passes per 90","xA per 90","Shot assists per 90","Key passes per 90","Passes to final third per 90","Passes to penalty area per 90","Through passes per 90","Deep completions per 90","Progressive passes per 90","Defensive duels won %","Aerial duels won %","Shots on target %","Goal conversion %","Accurate crosses %","Successful dribbles %","Offensive duels won %","Accurate passes %","Accurate forward passes %","Accurate progressive passes %","Possession +/-"
    ]
            
        selected_metric = random.choice(metric_options)


        league_options = [
    "🇪🇺 Top 5 Leagues",
    "🇪🇺 Top 7 Leagues",
    "🌍 All Leagues", "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
    "🇪🇸 La Liga", "🇩🇪 Bundesliga", "🇮🇹 Serie A", "🇫🇷 Ligue 1",  # Medium weight
    "🌍 Outside Top 7", "🇵🇹 Liga Portugal", "🇳🇱 Eredivisie", # Low weight
    "🇧🇪 Belgium", "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scotland", "🇦🇹 Austria", "🇨🇭 Switzerland", "🇹🇷 Türkiye", "🇩🇰 Denmark", "🇸🇪 Sweden", "🇳🇴 Norway", "🇭🇷 Croatia", "🇷🇸 Serbia", "🇨🇿 Czech Republic", "🇵🇱 Poland", "🇺🇦 Ukraine", "🇷🇺 Russia", "🇬🇷 Greece", "🇯🇵 Japan", "🇰🇷 Korea", "🇸🇦 Saudi Arabia", "🇺🇸 United States",  "🇲🇽 Mexico", "🇧🇷 Brazil", "🇦🇷 Argentina", "🇺🇾 Uruguay", "🇨🇱 Chile", "🇨🇴 Colombia", "🇪🇨 Ecuador",  "🇵🇾 Paraguay", "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship", "🇪🇸 Spain Segunda", "🇮🇹 Serie B", "🇩🇪 2. Bundesliga", "🇫🇷 Ligue 2"  # Lowest weight
]

# Define weights for each league category
        weights = [
    0.25,
    0.20,
    0.09, 0.09,
    0.06, 0.05, 0.05, 0.04,
    0.03, 0.03, 0.03,  # Low weight
    0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025, 0.0025 
]

# Ensure weights match the length of league_options
        assert len(weights) == len(league_options), "Weights length must match the league options length"

# Randomly select a league based on the defined weights
        selected_league = random.choices(league_options, weights=weights, k=1)[0]

    

        # Define age options based on selected league
        if selected_league in ["🇪🇺 Top 7 Leagues", "🇪🇺 Top 5 Leagues", "🌍 All Leagues", "🌍 Outside Top 7"]:
            if selected_position == "All positions":
                age_options = ["Age", "U19", "U20", "U21", "U23", "U24"]
                selected_age = random.choice(age_options)

            elif selected_position != "Goalkeeper":
                age_options = ["Age", "U20", "U21", "U23", "U24"]
                selected_age = random.choice(age_options)

            elif selected_position in "Goalkeeper":
                age_options = ["Age", "U23", "U24"]
                selected_age = random.choice(age_options)
        else:
            selected_age = "Age"


        # Select metric
        dropdown = self.driver.find_element(By.ID, "metric")
        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f"//option[. = '{selected_metric}']"))
        ).click()

        # Select position
        dropdown = self.driver.find_element(By.ID, "position")
        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f"//option[. = '{selected_position}']"))
        ).click()

        # Select age
        dropdown = self.driver.find_element(By.ID, "age")
        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f"//option[. = '{selected_age}']"))
        ).click()

        # Select league
        dropdown = self.driver.find_element(By.ID, "league")
        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f"//option[. = '{selected_league}']"))
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
        selected_metric = selected_metric.replace(" per 90", "")
        selected_position = selected_position.replace("er", "ers")
        selected_position = selected_position.replace("ack", "acks")
        selected_age = selected_age.replace("Age", "")


        


        # Create the tweet text dynamically
        tweet_text = f"{selected_league} {selected_age} {selected_position} : {selected_metric}\n\n{specific_text}\n\n👉 datamb.football"
        tweet_text = tweet_text.replace("  ", " ")

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
        else:
            print("Failed to send tweet:", response.status_code, response.text)


if __name__ == "__main__":
    pytest.main()
