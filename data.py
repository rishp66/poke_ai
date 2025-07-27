import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
from pokemontcgsdk import Card
from pokemontcgsdk import Set
from pokemontcgsdk import Type
from pokemontcgsdk import Supertype
from pokemontcgsdk import Subtype
from pokemontcgsdk import Rarity
from pokemontcgsdk import RestClient
from PIL import Image
import json
import time
import re

# Set page config
st.set_page_config(
    page_title="Pokemon TCG Sets Explorer",
    page_icon="🃏",
    layout="wide"
)

# App title and description
st.title("Pokemon TCG Sets Explorer")
st.markdown("This app displays data and for Pokemon TCG sets with an AI assistant to help you find cards and sets.")

# Function to get API key from environment variable
def get_api_key_poke():
    api_key = st.secrets.get('POKEMONTCG_IO_API_KEY')
    if not api_key:
        st.error("Pokémon TCG API key is not set. Please set the POKEMONTCG_IO_API_KEY environment variable.")
    return api_key

# Function to get API key for chatbot
def get_api_key_chatbot():
    api_key = st.secrets.get('CHATBOT_API_KEY')
    if not api_key:
        st.error("Chatbot API key is not set. Please set the CHATBOT_API_KEY environment variable.")
    return api_key

# Configure the Pokemon TCG SDK with API key
def configure_pokemon_tcg_api():
    api_key = get_api_key_poke()
    if api_key:
        RestClient.configure(api_key)
        return True
    return False

# Function to safely fetch sets with error handling and retry logic
def fetch_sets_safely(max_retries=3, delay=2):
    """Fetch Pokemon TCG sets with error handling and retry logic"""
    
    for attempt in range(max_retries):
        try:
            st.info(f"Fetching Pokemon TCG sets... (Attempt {attempt + 1}/{max_retries})")
            
            # Add a small delay between attempts
            if attempt > 0:
                time.sleep(delay * attempt)
            
            # Fetch sets with pagination to avoid overwhelming the API
            all_sets_data = []
            page = 1
            page_size = 50  # Smaller page size to reduce load
            
            while True:
                try:
                    # Use pagination parameters
                    sets_response = Set.where(page=page, pageSize=page_size)
                    
                    if not sets_response:
                        break
                        
                    all_sets_data.extend(sets_response)
                    
                    # If we got less than page_size items, we've reached the end
                    if len(sets_response) < page_size:
                        break
                        
                    page += 1
                    
                    # Add a small delay between pages to be respectful to the API
                    time.sleep(0.5)
                    
                except Exception as page_error:
                    st.warning(f"Error fetching page {page}: {str(page_error)}")
                    break
            
            if all_sets_data:
                st.success(f"Successfully fetched {len(all_sets_data)} sets!")
                return pd.DataFrame(all_sets_data)
            else:
                raise Exception("No sets data received")
                
        except Exception as e:
            error_msg = str(e)
            st.warning(f"Attempt {attempt + 1} failed: {error_msg}")
            
            if attempt == max_retries - 1:
                st.error("Failed to fetch sets after all retry attempts.")
                st.error("Possible solutions:")
                st.error("1. Check your internet connection")
                st.error("2. Verify your Pokemon TCG API key is valid")
                st.error("3. The API might be temporarily unavailable - try again later")
                st.error("4. You might have exceeded the API rate limit")
                return None
            else:
                st.info(f"Retrying in {delay * (attempt + 1)} seconds...")
                time.sleep(delay * (attempt + 1))
    
    return None

# Function to safely fetch cards with error handling
def fetch_cards_safely(set_name, max_retries=3):
    """Fetch cards for a specific set with error handling"""
    
    for attempt in range(max_retries):
        try:
            st.info(f"Fetching cards for {set_name}... (Attempt {attempt + 1}/{max_retries})")
            
            if attempt > 0:
                time.sleep(2 * attempt)
            
            # Fetch cards with pagination
            all_cards_data = []
            page = 1
            page_size = 100
            
            while True:
                try:
                    cards_response = Card.where(q=f'set.name:"{set_name}"', page=page, pageSize=page_size)
                    
                    if not cards_response:
                        break
                        
                    all_cards_data.extend(cards_response)
                    
                    if len(cards_response) < page_size:
                        break
                        
                    page += 1
                    time.sleep(0.3)  # Small delay between pages
                    
                except Exception as page_error:
                    st.warning(f"Error fetching cards page {page}: {str(page_error)}")
                    break
            
            if all_cards_data:
                st.success(f"Successfully fetched {len(all_cards_data)} cards!")
                return pd.DataFrame(all_cards_data)
            else:
                st.warning(f"No cards found for set: {set_name}")
                return pd.DataFrame()
                
        except Exception as e:
            st.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            
            if attempt == max_retries - 1:
                st.error(f"Failed to fetch cards for {set_name} after all retry attempts.")
                return pd.DataFrame()
            else:
                time.sleep(2 * (attempt + 1))
    
    return pd.DataFrame()

# CSS for styling the selectable image grid
st.markdown("""
<style>
    .image-container {
        border: 2px solid transparent;
        border-radius: 10px;
        padding: 5px;
        transition: all 0.3s;
        text-align: center;
        margin-bottom: 10px;
        background-color: white;
    }
    .image-container:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.1);
    }
    .selected-container {
        border: 2px solid #4CAF50;
        box-shadow: 0 0 15px rgba(76, 175, 80, 0.5);
    }
    .set-name {
        font-weight: bold;
        margin-top: 8px;
        font-size: 0.9em;
    }
    .set-code {
        color: #666;
        font-size: 0.8em;
    }
    .stButton button {
        width: 100%;
        background-color: #4CAF50;
        color: white;
        border: none;
        border-radius: 5px;
        padding: 5px;
        margin-top: 5px;
    }
    .card-container {
        margin-bottom: 20px;
        transition: transform 0.3s;
    }
    .card-container:hover {
        transform: translateY(-5px);
    }
    .price-info {
        font-size: 0.9em;
        margin-top: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Functions for data conversion
def image_conversion_set(dataframe):
    if 'logo' in dataframe.columns and 'symbol' in dataframe.columns:
        return dataframe
    # Extract the logo and symbol URLs into separate columns
    dataframe['logo'] = dataframe['images'].apply(lambda x: x.get('logo') if isinstance(x, dict) else None)
    dataframe['symbol'] = dataframe['images'].apply(lambda x: x.get('symbol') if isinstance(x, dict) else None)
    # Drop the original 'images' column
    dataframe = dataframe.drop(columns=['images'])
    return dataframe

# Function to select a set from a grid
def select_set(sets_data):
    # Create a session state to track the selected set
    if 'selected_set' not in st.session_state:
        st.session_state.selected_set = None
    
    # Create a grid layout
    num_columns = 4  # Adjust this for your desired grid width
    
    # Display sets in grid
    for i in range(0, len(sets_data), num_columns):
        # Create a row of columns
        cols = st.columns(num_columns)
        
        # Fill the row with set data
        for j in range(num_columns):
            if i + j < len(sets_data):
                set_data = sets_data.iloc[i + j]
                
                with cols[j]:
                    # Check if this set is selected
                    is_selected = st.session_state.selected_set == set_data['name']
                    selected_class = "selected-container" if is_selected else ""
                    
                    # Container with conditional class for selection highlight
                    logo_url = set_data.get('logo', 'https://via.placeholder.com/150x150?text=No+Logo')
                    st.markdown(f"""
                    <div class="image-container {selected_class}">
                        <img src="{logo_url}" style="max-height: 120px; width: auto; max-width: 100%;">
                        <div class="set-name">{set_data['name']}</div>
                        <div class="set-code">{set_data['id']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Add select button
                    if st.button(f"Select", key=f"set_{set_data['id']}"):
                        st.session_state.selected_set = set_data['name']
                        st.rerun()
    
    # Return the selected set name
    return st.session_state.selected_set

# Function to display cards from the selected set
def display_cards(set_name, cards_data):
    st.header(f"Cards from {set_name}")
    
    if cards_data.empty:
        st.warning("No cards found for this set.")
        return
    
    # Create a grid layout for cards
    num_columns = 4  # Adjust for grid width
    
    # Initialize session state for selected card if not exists
    if 'selected_card' not in st.session_state:
        st.session_state.selected_card = None
    
    # Display cards in grid using DataFrame indexing
    for i in range(0, len(cards_data), num_columns):
        # Create a row of columns
        cols = st.columns(num_columns)
        
        # Fill the row with card data
        for j in range(num_columns):
            idx = i + j
            if idx < len(cards_data):
                # Get card at index using iloc
                card = cards_data.iloc[idx]
                
                with cols[j]:
                    with st.container():
                        # Display card image
                        if isinstance(card['images'], dict) and 'small' in card['images']:
                            st.image(card['images']['small'], use_column_width=True)
                        else:
                            st.image("https://via.placeholder.com/150x209?text=No+Image", use_column_width=True)
                        
                        # Display card name & artist
                        st.markdown(f"**{card['name']}**")
                        
                        # Display price information if available
                        if isinstance(card.get('tcgplayer'), dict) and 'prices' in card['tcgplayer']:
                            prices = card['tcgplayer']['prices']
    
                            # Display prices in a clean format with larger text
                            price_html = "<div class='price-info' style='font-size: 16px;'>"
    
                            if isinstance(prices, dict):
                                if 'holofoil' in prices and isinstance(prices['holofoil'], dict) and 'market' in prices['holofoil']:
                                    price_html += f"<p style='margin: 4px 0;'><b>Holofoil:</b> <span style='font-size: 18px; font-weight: bold;'>${prices['holofoil']['market']:.2f}</span></p>"
        
                                if 'reverseHolofoil' in prices and isinstance(prices['reverseHolofoil'], dict) and 'market' in prices['reverseHolofoil']:
                                    price_html += f"<p style='margin: 4px 0;'><b>Reverse Holo:</b> <span style='font-size: 18px; font-weight: bold;'>${prices['reverseHolofoil']['market']:.2f}</span></p>"
        
                                if 'normal' in prices and isinstance(prices['normal'], dict) and 'market' in prices['normal']:
                                    price_html += f"<p style='margin: 4px 0;'><b>Normal:</b> <span style='font-size: 18px; font-weight: bold;'>${prices['normal']['market']:.2f}</span></p>"
    
                            price_html += "</div>"
                            st.markdown(price_html, unsafe_allow_html=True)
                        else:
                            # Make the unavailable price text larger too
                            st.markdown("<p style='font-size: 16px; font-style: italic;'>Price data unavailable</p>", unsafe_allow_html=True)

# Loading Pokémon TCG API
def handle_set_selection(selected_set):
    # Create anchor for scrolling
    st.markdown('<div id="cards-section"></div>', unsafe_allow_html=True)
    
    # Show loading state
    with st.spinner(f"Loading cards from {selected_set}..."):
        # Fetch cards safely
        cards_data = fetch_cards_safely(selected_set)
        
        if not cards_data.empty:
            # Display the cards
            display_cards(selected_set, cards_data)
        else:
            st.error(f"Failed to load cards for {selected_set}")

def ai_chat(prompt):
    API_KEY = get_api_key_chatbot()

    formatted_prompt = f"""
    Based on the following request: "{prompt}"
    
    Please analyze what the user is asking for and categorize it into one of these request types:
    - pokemon: If the user is asking about cards for a specific Pokemon
    - set: If the user is asking to see all cards in a specific set
    - total_cost: If the user is asking about the total cost of a set
    - top_cards: If the user is asking about the most expensive cards in a set
    
    Respond ONLY with a JSON object in this format:
    {{
      "request_type": "one of [pokemon, set, total_cost, top_cards]",
      "search_term": "the name of the Pokemon or set"
    }}
    
    Do not include any explanation, just return the JSON object.
    """

    # Check if the API key is set
    if not API_KEY:
        st.error("Chatbot API key is not set. Please set the CHATBOT_API_KEY environment variable.")
        return "API key not found."
    
    MODEL = "meta-llama/llama-4-maverick:free"

    try:
        # Make the API request
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            data=json.dumps({
                "model": MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": formatted_prompt
                    }
                ]
            }),
            timeout=60  # Add timeout to prevent hanging
        )
        
        # Check if the request was successful
        if response.status_code == 200:
            response_data = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        else:
            return f"Error: {response.status_code}, {response.text}"

        # Parse the response
        json_match = re.search(r'({[\s\S]*})', response_data)
        
        if json_match:
            query_interpretation = json.loads(json_match.group(1))
            
            # Validate that the required fields are present
            if "request_type" not in query_interpretation or "search_term" not in query_interpretation:
                return "None of the allowed request types were found. Please try again."
                
            # Validate that request_type is one of the allowed values
            allowed_types = ["pokemon", "set", "total_cost", "top_cards"]
            if query_interpretation["request_type"] not in allowed_types:
                return "None of the allowed request types were found. Please try again."
                
            return query_interpretation
        else:
            return "None of the allowed request types were found. Please try again."
    
    except Exception as e:
        return f"An error occurred: {str(e)}"

def parse_output(ai_content):
    if isinstance(ai_content, str):
        st.error(ai_content)
        return
        
    request_type = ai_content["request_type"]
    search_term = ai_content["search_term"]
    
    if request_type == "pokemon":
        try:
            pokemon_cards = fetch_cards_safely_by_query(f'name:"{search_term}"')
            if not pokemon_cards.empty:
                display_cards(f"Response: {search_term}", pokemon_cards)
            else:
                st.error(f"No cards found for Pokemon: {search_term}")
        except Exception as e:
            st.error(f"Error fetching Pokemon cards: {str(e)}")
            
    elif request_type == "set":
        try:
            set_cards = fetch_cards_safely_by_query(f'set.name:"{search_term}"')
            if not set_cards.empty:
                display_cards(f"Response: {search_term}", set_cards)
            else:
                st.error(f"No cards found for set: {search_term}")
        except Exception as e:
            st.error(f"Error fetching set cards: {str(e)}")
            
    elif request_type == "total_cost":
        try:
            set_cards = fetch_cards_safely_by_query(f'set.name:"{search_term}"')
            if set_cards.empty:
                st.error(f"No cards found for set: {search_term}")
                return
            total_cost = set_cards['tcgplayer'].apply(lambda x: extract_card_price(x)).sum()
            st.success(f"The total cost of the set '{search_term}' is: ${total_cost:.2f}")
        except Exception as e:
            st.error(f"Error calculating total cost: {str(e)}")
            
    elif request_type == "top_cards":
        try:
            set_cards = fetch_cards_safely_by_query(f'set.name:"{search_term}"')
            if set_cards.empty:
                st.error(f"No cards found for set: {search_term}")
                return
            # Sort by market price and get top 10
            set_cards['price'] = set_cards['tcgplayer'].apply(lambda x: extract_card_price(x))
            top_cards = set_cards.sort_values(by='price', ascending=False).head(10)
            display_cards(f"Top 10 most expensive cards in {search_term}", top_cards)
        except Exception as e:
            st.error(f"Error fetching top cards: {str(e)}")

def fetch_cards_safely_by_query(query, max_retries=3):
    """Fetch cards by query with error handling"""
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                time.sleep(2 * attempt)
            
            # Fetch cards with pagination
            all_cards_data = []
            page = 1
            page_size = 100
            
            while True:
                try:
                    cards_response = Card.where(q=query, page=page, pageSize=page_size)
                    
                    if not cards_response:
                        break
                        
                    all_cards_data.extend(cards_response)
                    
                    if len(cards_response) < page_size:
                        break
                        
                    page += 1
                    time.sleep(0.3)  # Small delay between pages
                    
                except Exception as page_error:
                    st.warning(f"Error fetching cards page {page}: {str(page_error)}")
                    break
            
            if all_cards_data:
                return pd.DataFrame(all_cards_data)
            else:
                return pd.DataFrame()
                
        except Exception as e:
            st.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            
            if attempt == max_retries - 1:
                st.error(f"Failed to fetch cards after all retry attempts.")
                return pd.DataFrame()
            else:
                time.sleep(2 * (attempt + 1))
    
    return pd.DataFrame()

def extract_card_price(card_price):
    if isinstance(card_price, str):
        try:
            card_price = json.loads(card_price)
        except json.JSONDecodeError:
            return 0.0
    
    try:
        # Parse the embedded json
        if isinstance(card_price, dict) and 'prices' in card_price:
            prices = card_price['prices']
            
            # Check for different price categories
            if 'holofoil' in prices and prices['holofoil'] and 'market' in prices['holofoil']:
                return float(prices['holofoil']['market'])
            elif 'normal' in prices and prices['normal'] and 'market' in prices['normal']:
                return float(prices['normal']['market'])
            elif 'reverseHolofoil' in prices and prices['reverseHolofoil'] and 'market' in prices['reverseHolofoil']:
                return float(prices['reverseHolofoil']['market'])
            else:
                # Try for any other category that has value
                for price_type in prices:
                    if isinstance(prices[price_type], dict) and 'market' in prices[price_type]:
                        return float(prices[price_type]['market'])
    except Exception as e:
        st.error(f"Error extracting price: {str(e)}")
    
    return 0.0

# Main app function
def main():
    # Configure the Pokemon TCG API
    if not configure_pokemon_tcg_api():
        st.error("Cannot proceed without Pokemon TCG API key. Please configure your API key.")
        return
    
    st.warning("Please select a set to view its cards. Scroll to the bottom once you select a set.")
    st.info("Please use the tab switcher below to switch between Set Display and PokeAI!")

    # Initialize session state for sets data
    if 'sets_data' not in st.session_state:
        st.session_state.sets_data = None
    
    # Create tabs for navigation
    tab1, tab2 = st.tabs(["Sets", "PokeAI"])
    
    with tab1:
        # Load sets data if not already loaded
        if st.session_state.sets_data is None:
            with st.spinner("Loading Pokemon TCG sets..."):
                all_sets = fetch_sets_safely()
                
                if all_sets is not None:
                    all_sets = all_sets[::-1]  # Reverse the order for display
                    sets_data = all_sets[["id", "name", "images"]]
                    
                    # Apply image conversion
                    imaged_set = image_conversion_set(sets_data)
                    st.session_state.sets_data = imaged_set
                else:
                    st.error("Failed to load sets data. Please refresh the page to try again.")
                    return
        
        # Display the set selection grid if data is loaded
        if st.session_state.sets_data is not None:
            selected_set = select_set(st.session_state.sets_data)
            
            # Show set details if a set is selected
            if selected_set:
                # Display the cards
                handle_set_selection(selected_set)
    
    with tab2:
        st.markdown("""
        # PokeAI: Your Pokemon TCG Assistant
        
        Ask any of the following:
        - "What is the total cost of [Set]?"
        - "What are the top 10 most expensive card in [Set]?"
        - "What are all the cards in [Set]?"
        - "What are all the cards for [Pokemon]?"
        """)
        user_message = st.text_area("Your message:", height=100)

        if st.button("Send"):
            if not user_message:
                st.error("Please enter a message.")
            else:
                with st.spinner("Getting response..."):
                    ai_response = ai_chat(user_message)
                    st.markdown("### Response:")
                    parse_output(ai_response)
    
    # Add a footer
    st.markdown("---")
    st.markdown("Powered by Pokémon TCG API")

# Run the app
if __name__ == "__main__":
    main()