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

# Set page config
st.set_page_config(
    page_title="Pokemon TCG Sets Explorer",
    page_icon="🃏",
    layout="wide"
)

# App title and description
st.title("Pokemon TCG Sets Explorer")
st.markdown("This app displays logos and symbols for Pokemon TCG sets")

# Function to get API key from environment variable
def get_api_key():
    api_key = os.environ.get('POKEMONTCG_IO_API_KEY')
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
    num_columns = 4  # Adjust for desired grid width
    
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
    st.markdown('''
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const element = document.getElementById('cards-section');
            element.scrollIntoView({ behavior: 'smooth' });
        });
    </script>
    ''', unsafe_allow_html=True)

# Main app function
def main():
    st.warning("Please select a set to view its cards. Scroll to the bottom once you select a set.")
    st.info("Please use the tab switcher below to switch between Set Display and PokeAI! PokeAI is currently under development.")

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
        st.info("PokeAI cards feature coming soon!")
    # Add a footer
    st.markdown("---")
    st.markdown("Powered by Pokémon TCG API")

# Run the app
if __name__ == "__main__":
    main()