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
import concurrent.futures
import threading
import asyncio
from typing import Optional, Dict, List

# Set page config
st.set_page_config(
    page_title="Pokemon TCG Sets Explorer",
    page_icon="🃏",
    layout="wide"
)

# App title and description
st.title("Pokemon TCG Sets Explorer")
st.markdown("This app displays data for Pokemon TCG sets with an AI assistant to help you find cards and sets.")

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
        try:
            RestClient.configure(api_key)
            return True
        except Exception as e:
            st.error(f"Failed to configure Pokemon TCG API: {str(e)}")
            return False
    return False

# Function to handle API errors and convert bytes to string if needed
def handle_api_error(error):
    """Handle API errors and ensure proper string conversion"""
    try:
        error_str = str(error)
        if hasattr(error, 'args') and error.args:
            error_arg = error.args[0]
            if isinstance(error_arg, bytes):
                error_str = error_arg.decode('utf-8', errors='replace')
            else:
                error_str = str(error_arg)
        return error_str
    except Exception:
        return "Unknown API error occurred"

# OPTIMIZED: Fast sets fetching with minimal API calls
@st.cache_data(ttl=7200, show_spinner=False)  # Cache for 2 hours
def fetch_sets_optimized():
    """Ultra-fast sets fetching with single API call and optimizations"""
    try:
        # Use maximum page size to minimize API calls
        all_sets = Set.all()
        if all_sets:
            # Convert to DataFrame immediately and process efficiently
            df = pd.DataFrame(all_sets)
            # Pre-process images to avoid repeated processing
            if 'images' in df.columns:
                df['logo'] = df['images'].apply(
                    lambda x: x.get('logo', 'https://via.placeholder.com/150x150?text=No+Logo') 
                    if isinstance(x, dict) else 'https://via.placeholder.com/150x150?text=No+Logo'
                )
                df['symbol'] = df['images'].apply(
                    lambda x: x.get('symbol', '') if isinstance(x, dict) else ''
                )
            return df
        return None
    except Exception as e:
        st.error(f"Error fetching sets: {handle_api_error(e)}")
        return None

# OPTIMIZED: Concurrent card fetching with progress tracking
def fetch_cards_concurrent(set_name: str, max_workers: int = 3) -> pd.DataFrame:
    """Fetch cards using concurrent requests for maximum speed"""
    all_cards = []
    page_size = 250  # Maximum allowed
    
    def fetch_page(page_num):
        try:
            return Card.where(q=f'set.name:"{set_name}"', page=page_num, pageSize=page_size)
        except Exception as e:
            st.error(f"Error fetching page {page_num}: {handle_api_error(e)}")
            return []
    
    try:
        # First, get the first page to determine total pages needed
        first_page_results = fetch_page(1)
        if not first_page_results:
            return pd.DataFrame()
        
        all_cards.extend(first_page_results)
        
        # If we got the full page size, there might be more pages
        if len(first_page_results) == page_size:
            # Use concurrent futures for remaining pages
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit requests for potential additional pages
                futures = []
                for page in range(2, 6):  # Check up to 5 pages concurrently
                    futures.append(executor.submit(fetch_page, page))
                
                # Collect results as they complete
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result(timeout=10)  # 10 second timeout per request
                        if result:
                            all_cards.extend(result)
                            if len(result) < page_size:
                                break  # No more pages
                        else:
                            break  # No more results
                    except concurrent.futures.TimeoutError:
                        st.warning("Some requests timed out, showing partial results")
                        break
                    except Exception as e:
                        st.warning(f"Error in concurrent fetch: {handle_api_error(e)}")
                        break
        
        return pd.DataFrame(all_cards) if all_cards else pd.DataFrame()
        
    except Exception as e:
        st.error(f"Error in concurrent card fetching: {handle_api_error(e)}")
        return pd.DataFrame()

# OPTIMIZED: Live API calls with smart progress bars
def fetch_cards_live_with_progress(set_name: str) -> pd.DataFrame:
    """Live API call with optimized progress tracking"""
    
    # Create progress container
    progress_container = st.container()
    
    with progress_container:
        st.info(f"🃏 Loading cards from **{set_name}**...")
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Phase 1: Initialize (0-20%)
        for i in range(0, 21, 5):
            progress_bar.progress(i)
            status_text.text(f"🔧 Initializing connection... ({i}%)")
            time.sleep(0.1)
        
        # Phase 2: Fetch data (20-85%)
        progress_bar.progress(25)
        status_text.text("📡 Fetching card data...")
        
        # Actual API call
        cards_data = fetch_cards_concurrent(set_name)
        
        # Phase 3: Processing (85-100%)
        for i in range(85, 101, 3):
            progress_bar.progress(i)
            status_text.text(f"🔄 Processing {len(cards_data)} cards... ({i}%)")
            time.sleep(0.05)
        
        # Clear progress
        time.sleep(0.3)
        progress_container.empty()
        
        return cards_data

# OPTIMIZED: Query-based fetching with concurrent processing
def fetch_cards_by_query_concurrent(query: str, max_workers: int = 3) -> pd.DataFrame:
    """Optimized query-based card fetching with concurrency"""
    
    def fetch_query_page(page_num):
        try:
            return Card.where(q=query, page=page_num, pageSize=250)
        except Exception as e:
            st.error(f"Error fetching query page {page_num}: {handle_api_error(e)}")
            return []
    
    try:
        all_cards = []
        
        # Get first page
        first_page = fetch_query_page(1)
        if not first_page:
            return pd.DataFrame()
        
        all_cards.extend(first_page)
        
        # If full page, fetch more concurrently
        if len(first_page) == 250:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(fetch_query_page, page) for page in range(2, 6)]
                
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result(timeout=8)
                        if result:
                            all_cards.extend(result)
                            if len(result) < 250:
                                break
                        else:
                            break
                    except (concurrent.futures.TimeoutError, Exception) as e:
                        st.warning(f"Some requests failed: {handle_api_error(e)}")
                        break
        
        return pd.DataFrame(all_cards) if all_cards else pd.DataFrame()
        
    except Exception as e:
        st.error(f"Error in query fetching: {handle_api_error(e)}")
        return pd.DataFrame()

def fetch_cards_by_query_with_progress(query: str, operation_name: str) -> pd.DataFrame:
    """Wrapper for query-based fetching with progress"""
    progress_container = st.container()
    
    with progress_container:
        st.info(f"🔍 {operation_name}...")
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Quick progress updates
        for i in range(0, 31, 10):
            progress_bar.progress(i)
            status_text.text(f"🔧 Preparing search... ({i}%)")
            time.sleep(0.1)
        
        progress_bar.progress(40)
        status_text.text("🎯 Executing search...")
        
        # Actual API call
        cards_data = fetch_cards_by_query_concurrent(query)
        
        # Final progress
        for i in range(80, 101, 5):
            progress_bar.progress(i)
            if not cards_data.empty:
                status_text.text(f"✅ Found {len(cards_data)} cards! ({i}%)")
            else:
                status_text.text(f"⚠️ No cards found ({i}%)")
            time.sleep(0.05)
        
        time.sleep(0.2)
        progress_container.empty()
        return cards_data

# CSS for styling (unchanged but optimized)
st.markdown("""
<style>
    .image-container {
        border: 2px solid transparent;
        border-radius: 10px;
        padding: 5px;
        transition: all 0.2s ease;
        text-align: center;
        margin-bottom: 10px;
        background-color: white;
        cursor: pointer;
    }
    .image-container:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 16px rgba(0,0,0,0.1);
    }
    .selected-container {
        border: 3px solid #4CAF50;
        box-shadow: 0 0 20px rgba(76, 175, 80, 0.6);
        transform: translateY(-2px);
    }
    .set-name {
        font-weight: bold;
        margin-top: 8px;
        font-size: 0.9em;
        color: #333;
    }
    .set-code {
        color: #666;
        font-size: 0.8em;
    }
    .stButton button {
        width: 100%;
        background-color: #4CAF50 !important;
        color: white !important;
        border: none !important;
        border-radius: 5px;
        padding: 8px;
        margin-top: 5px;
        transition: background-color 0.2s;
    }
    .stButton button:hover {
        background-color: #45a049 !important;
    }
    .card-container {
        margin-bottom: 15px;
        transition: transform 0.2s ease;
        border-radius: 8px;
        overflow: hidden;
    }
    .card-container:hover {
        transform: translateY(-2px);
    }
    .price-info {
        font-size: 0.9em;
        margin-top: 5px;
        padding: 5px;
        background-color: #f8f9fa;
        border-radius: 4px;
    }
    #cards-section {
        scroll-margin-top: 20px;
        border-top: 3px solid #4CAF50;
        padding-top: 20px;
        margin-top: 20px;
    }
</style>
""", unsafe_allow_html=True)

# OPTIMIZED: Set selection with improved UX
def select_set(sets_data):
    if 'selected_set' not in st.session_state:
        st.session_state.selected_set = None
    
    # Add search functionality for sets
    search_term = st.text_input("🔍 Search sets:", placeholder="Type to filter sets...")
    
    # Filter sets based on search
    if search_term:
        filtered_sets = sets_data[
            sets_data['name'].str.contains(search_term, case=False, na=False) |
            sets_data['id'].str.contains(search_term, case=False, na=False)
        ]
    else:
        filtered_sets = sets_data
    
    if filtered_sets.empty:
        st.warning("No sets found matching your search.")
        return st.session_state.selected_set
    
    st.info(f"📊 Showing {len(filtered_sets)} sets")
    
    num_columns = 4
    
    for i in range(0, len(filtered_sets), num_columns):
        cols = st.columns(num_columns)
        
        for j in range(num_columns):
            if i + j < len(filtered_sets):
                set_data = filtered_sets.iloc[i + j]
                
                with cols[j]:
                    is_selected = st.session_state.selected_set == set_data['name']
                    selected_class = "selected-container" if is_selected else ""
                    
                    logo_url = set_data.get('logo', 'https://via.placeholder.com/150x150?text=No+Logo')
                    
                    st.markdown(f"""
                    <div class="image-container {selected_class}">
                        <img src="{logo_url}" style="max-height: 120px; width: auto; max-width: 100%; border-radius: 4px;">
                        <div class="set-name">{set_data['name']}</div>
                        <div class="set-code">{set_data['id']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button(f"📋 Select", key=f"set_{set_data['id']}", help=f"Load cards from {set_data['name']}"):
                        st.session_state.selected_set = set_data['name']
                        st.info("📜 **Set selected!** Please scroll down to view all cards from this set.")
                        st.rerun()
    
    return st.session_state.selected_set

# OPTIMIZED: Card display with complete set view
def display_cards(set_name: str, cards_data: pd.DataFrame):
    st.markdown('<div id="cards-section"></div>', unsafe_allow_html=True)
    
    st.header(f"🃏 Cards from {set_name}")
    
    if cards_data.empty:
        st.warning("No cards found for this set.")
        return
    
    # Enhanced info display
    total_cards = len(cards_data)
    total_value = cards_data.get('tcgplayer', pd.Series()).apply(extract_card_price).sum()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 Total Cards", total_cards)
    with col2:
        st.metric("💰 Estimated Value", f"${total_value:.2f}")
    with col3:
        avg_price = total_value / total_cards if total_cards > 0 else 0
        st.metric("📈 Average Price", f"${avg_price:.2f}")
    
    # Display all cards (no pagination)
    st.info(f"📋 Displaying all {total_cards} cards from this set")
    
    # Display cards in grid
    num_columns = 4
    
    for i in range(0, len(cards_data), num_columns):
        cols = st.columns(num_columns)
        
        for j in range(num_columns):
            idx = i + j
            if idx < len(cards_data):
                card = cards_data.iloc[idx]
                
                with cols[j]:
                    with st.container():
                        # Card image with error handling
                        try:
                            if isinstance(card['images'], dict) and 'small' in card['images']:
                                st.image(card['images']['small'], use_column_width=True)
                            else:
                                st.image("https://via.placeholder.com/150x209?text=No+Image", use_column_width=True)
                        except:
                            st.image("https://via.placeholder.com/150x209?text=Error", use_column_width=True)
                        
                        # Card name
                        st.markdown(f"**{card.get('name', 'Unknown Card')}**")
                        
                        # Price information with better formatting
                        if isinstance(card.get('tcgplayer'), dict) and 'prices' in card['tcgplayer']:
                            prices = card['tcgplayer']['prices']
                            price_html = "<div class='price-info'>"
                            
                            price_types = ['holofoil', 'reverseHolofoil', 'normal']
                            price_labels = ['🌟 Holofoil', '🔄 Reverse Holo', '📋 Normal']
                            
                            for price_type, label in zip(price_types, price_labels):
                                if (price_type in prices and 
                                    isinstance(prices[price_type], dict) and 
                                    'market' in prices[price_type]):
                                    price = prices[price_type]['market']
                                    price_html += f"<p style='margin: 2px 0;'><b>{label}:</b> <span style='color: #2e7d32; font-weight: bold;'>${price:.2f}</span></p>"
                            
                            price_html += "</div>"
                            st.markdown(price_html, unsafe_allow_html=True)
                        else:
                            st.markdown("<p style='font-style: italic; color: #666;'>💸 Price unavailable</p>", unsafe_allow_html=True)

# OPTIMIZED: Set selection handler with live calls
def handle_set_selection(selected_set: str):
    """Handle set selection with live API calls and progress tracking"""
    st.markdown('<div id="cards-section"></div>', unsafe_allow_html=True)
    
    # Make live API call (no caching for real-time data)
    cards_data = fetch_cards_live_with_progress(selected_set)
    
    if not cards_data.empty:
        display_cards(selected_set, cards_data)
    else:
        st.error(f"❌ Failed to load cards for {selected_set}. Please try again.")

# AI chat function (optimized with faster timeout)
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

    if not API_KEY:
        st.error("Chatbot API key is not set. Please set the CHATBOT_API_KEY environment variable.")
        return "API key not found."
    
    MODEL = "meta-llama/llama-4-maverick:free"

    try:
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
            timeout=15  # Reduced timeout for faster failure
        )
        
        if response.status_code == 200:
            response_data = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        else:
            return f"Error: {response.status_code}, {response.text}"

        json_match = re.search(r'({[\s\S]*})', response_data)
        
        if json_match:
            query_interpretation = json.loads(json_match.group(1))
            
            if "request_type" not in query_interpretation or "search_term" not in query_interpretation:
                return "None of the allowed request types were found. Please try again."
                
            allowed_types = ["pokemon", "set", "total_cost", "top_cards"]
            if query_interpretation["request_type"] not in allowed_types:
                return "None of the allowed request types were found. Please try again."
                
            return query_interpretation
        else:
            return "None of the allowed request types were found. Please try again."
    
    except Exception as e:
        return f"An error occurred: {str(e)}"

# OPTIMIZED: AI response parsing with concurrent processing
def parse_output(ai_content):
    if isinstance(ai_content, str):
        st.error(ai_content)
        return
        
    request_type = ai_content["request_type"]
    search_term = ai_content["search_term"]
    
    if request_type == "pokemon":
        pokemon_cards = fetch_cards_by_query_with_progress(
            f'name:"{search_term}"', 
            f"Searching for **{search_term}** cards"
        )
        if not pokemon_cards.empty:
            display_cards(f"🔍 {search_term} Cards", pokemon_cards)
        else:
            st.error(f"No cards found for Pokemon: {search_term}")
            
    elif request_type == "set":
        set_cards = fetch_cards_by_query_with_progress(
            f'set.name:"{search_term}"', 
            f"Loading **{search_term}** set"
        )
        if not set_cards.empty:
            display_cards(f"📦 {search_term} Set", set_cards)
        else:
            st.error(f"No cards found for set: {search_term}")
            
    elif request_type == "total_cost":
        set_cards = fetch_cards_by_query_with_progress(
            f'set.name:"{search_term}"', 
            f"Calculating total cost for **{search_term}**"
        )
        if set_cards.empty:
            st.error(f"No cards found for set: {search_term}")
            return
            
        # Quick calculation
        total_cost = set_cards['tcgplayer'].apply(extract_card_price).sum()
        
        # Display result with metrics
        col1, col2 = st.columns(2)
        with col1:
            st.success(f"💰 **Total Cost of '{search_term}':** ${total_cost:.2f}")
        with col2:
            avg_cost = total_cost / len(set_cards) if len(set_cards) > 0 else 0
            st.info(f"📊 **Average Card Price:** ${avg_cost:.2f}")
            
    elif request_type == "top_cards":
        set_cards = fetch_cards_by_query_with_progress(
            f'set.name:"{search_term}"', 
            f"Finding top cards in **{search_term}**"
        )
        if set_cards.empty:
            st.error(f"No cards found for set: {search_term}")
            return
            
        # Quick processing
        set_cards['price'] = set_cards['tcgplayer'].apply(extract_card_price)
        top_cards = set_cards.sort_values(by='price', ascending=False).head(10)
        
        display_cards(f"🏆 Top 10 Most Expensive Cards in {search_term}", top_cards)
    
    # Auto-scroll to results
    st.markdown("""
    <script>
        setTimeout(function() {
            const element = document.getElementById('cards-section');
            if (element) {
                element.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }, 200);
    </script>
    """, unsafe_allow_html=True)

# OPTIMIZED: Price extraction with error handling
def extract_card_price(card_price) -> float:
    """Extract card price with optimized error handling"""
    if isinstance(card_price, str):
        try:
            card_price = json.loads(card_price)
        except json.JSONDecodeError:
            return 0.0
    
    try:
        if isinstance(card_price, dict) and 'prices' in card_price:
            prices = card_price['prices']
            
            # Priority order for price types
            price_priority = ['holofoil', 'normal', 'reverseHolofoil']
            
            for price_type in price_priority:
                if (price_type in prices and 
                    isinstance(prices[price_type], dict) and 
                    'market' in prices[price_type] and
                    prices[price_type]['market'] is not None):
                    return float(prices[price_type]['market'])
            
            # Fallback: any available price
            for price_type in prices:
                if isinstance(prices[price_type], dict) and 'market' in prices[price_type]:
                    try:
                        return float(prices[price_type]['market'])
                    except (ValueError, TypeError):
                        continue
    except Exception:
        pass
    
    return 0.0

# MAIN APPLICATION
def main():
    if not configure_pokemon_tcg_api():
        st.error("Cannot proceed without Pokemon TCG API key. Please configure your API key.")
        return
    
    # Enhanced instructions
    st.info("""
    🎯 **Quick Start Guide:**
    - **Sets Tab:** Browse all Pokemon TCG sets with live data loading
    - **PokeAI Tab:** Ask questions about cards, sets, and prices
    - Use the search bar to quickly find specific sets
    """)

    # Initialize session state
    if 'sets_data' not in st.session_state:
        st.session_state.sets_data = None
    
    # Create tabs
    tab1, tab2 = st.tabs(["🃏 Sets Explorer", "🤖 PokeAI Assistant"])
    
    with tab1:
        st.markdown("### Pokemon TCG Sets Collection")
        
        # Load sets data with progress (cached for performance)
        if st.session_state.sets_data is None:
            with st.spinner("🔄 Loading Pokemon TCG sets..."):
                all_sets = fetch_sets_optimized()
                
                if all_sets is not None:
                    # Reverse order for newest first
                    all_sets = all_sets[::-1]
                    
                    # Select required columns
                    sets_data = all_sets[["id", "name", "logo", "symbol"]].copy()
                    st.session_state.sets_data = sets_data
                    
                    st.success(f"🎉 Successfully loaded {len(sets_data)} Pokemon TCG sets!")
                else:
                    st.error("❌ Failed to load sets data. Please refresh the page to try again.")
                    return
        
        # Display set selection grid
        if st.session_state.sets_data is not None:
            selected_set = select_set(st.session_state.sets_data)
            
            # Handle set selection with live API calls
            if selected_set:
                handle_set_selection(selected_set)
    
    with tab2:
        st.markdown("""
        ### 🤖 PokeAI: Your Pokemon TCG Assistant
        
        **Ask me anything about Pokemon cards:**
        - 💰 *"What is the total cost of Base Set?"*
        - 🏆 *"What are the top 10 most expensive cards in Jungle?"*
        - 📦 *"Show me all cards in Team Rocket set"*
        - 🔍 *"Find all Pikachu cards"*
        """)
        
        user_message = st.text_area(
            "Your question:", 
            height=100,
            placeholder="Ask about Pokemon cards, sets, or prices..."
        )

        if st.button("🚀 Send", help="Submit your question to PokeAI"):
            if not user_message.strip():
                st.error("Please enter a question.")
            else:
                # AI processing with progress
                with st.spinner("🤖 PokeAI is analyzing your request..."):
                    ai_response = ai_chat(user_message)
                
                st.markdown("### 🎉 PokeAI Response:")
                parse_output(ai_response)
    
    # Footer with performance info
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("🚀 **Optimized Performance**")
        st.caption("Concurrent API calls & smart caching")
    with col2:
        st.markdown("📊 **Real-time Data**")
        st.caption("Live API calls with progress tracking")
    with col3:
        st.markdown("🃏 **Powered by Pokémon TCG API**")
        st.caption("Official data source")

if __name__ == "__main__":
    main()