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
    dataframe['logo'] = dataframe['images'].apply(lambda x: x.get('logo'))
    dataframe['symbol'] = dataframe['images'].apply(lambda x: x.get('symbol'))
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
                    st.markdown(f"""
                    <div class="image-container {selected_class}">
                        <img src="{set_data['logo']}" style="max-height: 120px; width: auto; max-width: 100%;">
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
                        if isinstance(card['tcgplayer'], dict) and 'prices' in card['tcgplayer']:
                            prices = card['tcgplayer']['prices']
    
                        # Display prices in a clean format with larger text
                            price_html = "<div class='price-info' style='font-size: 16px;'>"  # Increased base font size
    
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
def handle_set_selection(selected_set, cards_data):
    # Create anchor for scrolling
    st.markdown('<div id="cards-section"></div>', unsafe_allow_html=True)
    
    # Show loading state
    with st.spinner(f"Loading cards from {selected_set}..."):
        # You can add a progress bar with predetermined steps
        progress_bar = st.progress(0)
        total_steps = 5
        
        # Step 1: Data preparation
        progress_bar.progress(1/total_steps)
        time.sleep(0.5)  # Small delay for visual effect
        
        # Step 2: Filtering and sorting
        progress_bar.progress(2/total_steps)
        time.sleep(0.5)  # Small delay for visual effect
        
        # Step 3: Preparing display
        progress_bar.progress(3/total_steps)
        time.sleep(0.5)  # Small delay for visual effect
        
        # Step 4: Final preparation
        progress_bar.progress(4/total_steps)
        time.sleep(0.5)  # Small delay for visual effect

        # Step 5: Complete the progress
        progress_bar.progress(5/total_steps)
        time.sleep(0.5)  # Small delay for visual effect
        
        # Complete the progress
        progress_bar.empty()  # Remove the progress bar
        
        # Display the cards
        display_cards(selected_set, cards_data)
    
    # Auto-scroll to the cards section
    # st.markdown('''
    # <script>
    #     document.addEventListener('DOMContentLoaded', function() {
    #         const element = document.getElementById('cards-section');
    #         element.scrollIntoView({ behavior: 'smooth' });
    #     });
    # </script>
    # ''', unsafe_allow_html=True)

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
    request_type = ai_content["request_type"]
    search_term = ai_content["search_term"]
    if request_type == "pokemon":
        pokemon_cards = pd.DataFrame(Card.where(q=f'name:"{search_term}"'))
        display_cards(f"Response: {search_term}", pokemon_cards)
    elif request_type == "set":
        set_cards = pd.DataFrame(Card.where(q=f'set.name:"{search_term}"'))
        display_cards(f"Response: {search_term}", set_cards)
    elif request_type == "total_cost":
        set_cards = pd.DataFrame(Card.where(q=f'set.name:"{search_term}"'))
        if set_cards.empty:
            st.error(f"No cards found for set: {search_term}")
            return
        total_cost = set_cards['tcgplayer'].apply(lambda x: extract_card_price(x)).sum()
        st.success(f"The total cost of the set '{search_term}' is: ${total_cost:.2f}")
    elif request_type == "top_cards":
        set_cards = pd.DataFrame(Card.where(q=f'set.name:"{search_term}"'))
        if set_cards.empty:
            st.error(f"No cards found for set: {search_term}")
            return
        # Sort by market price and get top 10
        set_cards['price'] = set_cards['tcgplayer'].apply(lambda x: extract_card_price(x))
        top_cards = set_cards.sort_values(by='price', ascending=False).head(10)
        display_cards(f"Top 10 most expensive cards in {search_term}", top_cards)


def extract_card_price(card_price):
    if isinstance(card_price, str):
        try:
            card_price = json.loads(card_price)
        except json.JSONDecodeError:
            return "Invalid price data"
    
    try:
        # Parse the embedded json
        if 'prices' in card_price:
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
    

# Main app function
def main():
    st.warning("Please select a set to view its cards. Scroll to the bottom once you select a set.")
    st.info("Please use the tab switcher below to switch between Set Display and PokeAI!")

    # Get data from API
    all_sets = pd.DataFrame(Set.all())
    all_sets = all_sets[::-1] # Reverse the order for display
    sets_data = all_sets[["id", "name", "images"]]
    
    # Apply image conversion
    imaged_set = image_conversion_set(sets_data)
    
    # Create tabs for navigation
    tab1, tab2 = st.tabs(["Sets", "PokeAI"])
    
    with tab1:
        # Display the set selection grid
        selected_set = select_set(imaged_set)
        
        # Show set details if a set is selected
        if selected_set:
            cards_data = pd.DataFrame(Card.where(q=f'set.name:"{selected_set}"'))
            
            # Display the cards
            handle_set_selection(selected_set, cards_data)
        else:
            pass
    
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
                    st.write(parse_output(ai_response))
    # Add a footer
    st.markdown("---")
    st.markdown("Powered by Pokémon TCG API")

# Run the app
if __name__ == "__main__":
    main()


