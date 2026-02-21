import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
import json
import time
import re
import concurrent.futures
from typing import Optional, Dict, List
from datetime import datetime, timedelta

# Set page config
st.set_page_config(
    page_title="Pokemon TCG Sets Explorer",
    page_icon="🃏",
    layout="wide"
)

# ============================================================
# KEEP-ALIVE: Auto-refresh every 4 hours ONLY when idle
# ============================================================
try:
    from streamlit_autorefresh import st_autorefresh
    if 'last_interaction' not in st.session_state:
        st.session_state.last_interaction = datetime.now()
    idle_time = datetime.now() - st.session_state.last_interaction
    if idle_time > timedelta(minutes=30):
        st_autorefresh(interval=14400000, key="keepalive")
except ImportError:
    if 'last_interaction' not in st.session_state:
        st.session_state.last_interaction = datetime.now()


def mark_user_active():
    st.session_state.last_interaction = datetime.now()


# ============================================================
# POKEWALLET API CONFIGURATION
# ============================================================
POKEWALLET_BASE_URL = "https://api.pokewallet.io"


def get_api_key_pokewallet():
    api_key = st.secrets.get('POKEWALLET_API_KEY')
    if not api_key:
        st.error("PokéWallet API key is not set. Please set the POKEWALLET_API_KEY secret.")
    return api_key


def get_api_key_chatbot():
    api_key = st.secrets.get('CHATBOT_API_KEY')
    if not api_key:
        st.error("Chatbot API key is not set. Please set the CHATBOT_API_KEY secret.")
    return api_key


def _pw_headers():
    """Build auth headers for PokéWallet API."""
    api_key = get_api_key_pokewallet()
    return {"X-API-Key": api_key} if api_key else {}


def retry_api_call(func, max_retries=3, base_delay=2, description="API call"):
    """Retry API calls with exponential backoff."""
    last_exception = None
    for attempt in range(max_retries):
        try:
            result = func()
            if result is not None:
                return result
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                st.toast(f"⏳ {description} — retrying in {delay}s (attempt {attempt + 2}/{max_retries})...", icon="🔄")
                time.sleep(delay)
    if last_exception:
        raise last_exception
    return None


# ============================================================
# DATA FETCHING — SETS
# ============================================================
@st.cache_data(ttl=7200, show_spinner=False)
def fetch_all_sets():
    """Fetch all Pokemon TCG sets from PokéWallet API."""
    try:
        def _fetch():
            resp = requests.get(
                f"{POKEWALLET_BASE_URL}/sets",
                headers=_pw_headers(),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])

        sets_list = retry_api_call(_fetch, description="Fetching all sets")
        if sets_list:
            return pd.DataFrame(sets_list)
        return None
    except Exception as e:
        st.error(f"Error fetching sets: {e}")
        return None


# ============================================================
# DATA FETCHING — CARDS BY SET
# ============================================================
def fetch_set_cards(set_code: str, set_id: str = None) -> pd.DataFrame:
    """Fetch all cards in a set from PokéWallet with pagination.
    Tries set_code first, then falls back to set_id."""

    # Build ordered list of identifiers to try
    identifiers = []
    if set_code:
        identifiers.append(set_code)
    if set_id and set_id != set_code:
        identifiers.append(set_id)
    if not identifiers:
        return pd.DataFrame()

    limit = 200

    for identifier in identifiers:
        all_cards = []
        set_info = {}
        page = 1

        try:
            while True:
                def _fetch(p=page, ident=identifier):
                    resp = requests.get(
                        f"{POKEWALLET_BASE_URL}/sets/{ident}",
                        headers=_pw_headers(),
                        params={"page": p, "limit": limit},
                        timeout=30,
                    )
                    resp.raise_for_status()
                    return resp.json()

                data = retry_api_call(
                    _fetch, max_retries=2, description=f"Fetching {identifier} p{page}"
                )
                if not data:
                    break

                cards_batch = data.get("cards", [])
                set_info = data.get("set", {})

                if not cards_batch and page == 1:
                    break  # No cards — try next identifier

                for card in cards_batch:
                    card['set_name'] = set_info.get('name', '')
                    card['set_code_val'] = set_info.get('set_code', identifier)

                all_cards.extend(cards_batch)

                pagination = data.get("pagination", {})
                total_pages = pagination.get("total_pages", 1)
                if page >= total_pages:
                    break
                page += 1

        except Exception:
            continue  # Try next identifier

        if all_cards:
            df = pd.DataFrame(all_cards)

            # Check if prices are empty — enrich via /search
            df['_price'] = extract_price_series(df)
            if df['_price'].sum() == 0:
                sn = set_info.get('name', '')
                if sn:
                    df = _enrich_prices_via_search(df, sn)
                df.drop(columns=['_price'], inplace=True, errors='ignore')

            return df

    # All identifiers failed — return empty
    return pd.DataFrame()


def _enrich_prices_via_search(df: pd.DataFrame, set_name: str) -> pd.DataFrame:
    """
    When /sets/:code returns cards with empty prices, use /search to fetch
    prices and merge them back by card id.
    """
    try:
        search_results = search_cards(set_name, max_pages=10)
        if search_results.empty:
            return df

        # Build a price lookup: card id -> price
        price_lookup = {}
        for _, row in search_results.iterrows():
            card_id = row.get('id', '')
            if card_id:
                price = extract_price_from_card(row)
                if price > 0:
                    price_lookup[card_id] = price

        if not price_lookup:
            return df

        # Also try to bring in the full tcgplayer/cardmarket dicts
        tcg_lookup = {}
        cm_lookup = {}
        for _, row in search_results.iterrows():
            card_id = row.get('id', '')
            if card_id:
                tcg = row.get('tcgplayer')
                cm = row.get('cardmarket')
                if tcg and isinstance(tcg, dict):
                    prices = tcg.get('prices', [])
                    if isinstance(prices, (dict, list)) and prices:
                        tcg_lookup[card_id] = tcg
                if cm and isinstance(cm, dict):
                    cm_lookup[card_id] = cm

        # Merge back into df
        def _merge_tcg(row):
            cid = row.get('id', '')
            existing = row.get('tcgplayer')
            if existing and isinstance(existing, dict):
                existing_prices = existing.get('prices', [])
                if existing_prices:
                    return existing
            return tcg_lookup.get(cid, existing)

        def _merge_cm(row):
            cid = row.get('id', '')
            return cm_lookup.get(cid, row.get('cardmarket'))

        df['tcgplayer'] = df.apply(_merge_tcg, axis=1)
        if 'cardmarket' not in df.columns:
            df['cardmarket'] = None
        df['cardmarket'] = df.apply(_merge_cm, axis=1)

        return df

    except Exception as e:
        # Silently fail — prices just stay empty
        return df


def fetch_set_cards_with_progress(set_name: str, set_code: str, set_id: str = None) -> pd.DataFrame:
    """Fetch set cards with progress tracking UI."""
    progress_container = st.container()

    with progress_container:
        st.info(f"🃏 Loading cards from **{set_name}**...")
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i in range(0, 21, 10):
            progress_bar.progress(i)
            status_text.text(f"🔧 Connecting to PokéWallet API... ({i}%)")
            time.sleep(0.05)

        progress_bar.progress(25)
        status_text.text("📡 Fetching card data (may also fetch prices via search)...")

        cards_data = fetch_set_cards(set_code, set_id)

        for i in range(85, 101, 5):
            progress_bar.progress(i)
            count = len(cards_data) if not cards_data.empty else 0
            status_text.text(f"🔄 Processing {count} cards... ({i}%)")
            time.sleep(0.03)

        time.sleep(0.2)
        progress_container.empty()
        return cards_data


# ============================================================
# DATA FETCHING — SEARCH CARDS
# ============================================================
def search_cards(query: str, max_pages: int = 5) -> pd.DataFrame:
    """Search cards via PokéWallet /search endpoint with pagination."""
    all_results = []
    page = 1
    limit = 100

    try:
        while page <= max_pages:
            def _fetch(p=page):
                resp = requests.get(
                    f"{POKEWALLET_BASE_URL}/search",
                    headers=_pw_headers(),
                    params={"q": query, "page": p, "limit": limit},
                    timeout=30,
                )
                resp.raise_for_status()
                return resp.json()

            data = retry_api_call(_fetch, description=f"Searching page {page}")
            if not data:
                break

            results_batch = data.get("results", [])
            all_results.extend(results_batch)

            pagination = data.get("pagination", {})
            total_pages = pagination.get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1

        return pd.DataFrame(all_results) if all_results else pd.DataFrame()

    except Exception as e:
        st.error(f"Error searching cards: {e}")
        return pd.DataFrame()


def search_cards_with_progress(query: str, operation_name: str) -> pd.DataFrame:
    """Search cards with progress UI."""
    progress_container = st.container()

    with progress_container:
        st.info(f"🔍 {operation_name}...")
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i in range(0, 31, 10):
            progress_bar.progress(i)
            status_text.text(f"🔧 Preparing search... ({i}%)")
            time.sleep(0.05)

        progress_bar.progress(40)
        status_text.text("🎯 Executing search...")

        cards_data = search_cards(query)

        for i in range(80, 101, 5):
            progress_bar.progress(i)
            count = len(cards_data) if not cards_data.empty else 0
            if count > 0:
                status_text.text(f"✅ Found {count} cards! ({i}%)")
            else:
                status_text.text(f"⚠️ No cards found ({i}%)")
            time.sleep(0.03)

        time.sleep(0.2)
        progress_container.empty()
        return cards_data


# ============================================================
# CARD IMAGE FETCHING (cached 24h)
# ============================================================
@st.cache_data(ttl=86400, show_spinner=False)
def fetch_card_image(card_id: str, size: str = "low") -> Optional[bytes]:
    """Fetch card image bytes from PokéWallet /images endpoint."""
    try:
        resp = requests.get(
            f"{POKEWALLET_BASE_URL}/images/{card_id}",
            headers=_pw_headers(),
            params={"size": size},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.content
    except Exception:
        pass
    return None


# ============================================================
# PRICE EXTRACTION
# ============================================================
def _try_float(val) -> float:
    """Safely convert a value to float, returning 0.0 on failure."""
    if val is None:
        return 0.0
    try:
        f = float(val)
        return f if f > 0 else 0.0
    except (ValueError, TypeError):
        return 0.0


def _best_price_from_dict(d: dict) -> float:
    """Try multiple price field names in priority order."""
    for key in ['market_price', 'mid_price', 'low_price', 'high_price',
                'market', 'mid', 'low', 'high', 'avg', 'trend']:
        val = _try_float(d.get(key))
        if val > 0:
            return val
    return 0.0


def extract_price_from_card(card) -> float:
    """Extract best available market price from a PokéWallet card record."""
    if not isinstance(card, (dict, pd.Series)):
        return 0.0

    # --- 1) TCG_Prices list (from /sets/:setCode response) ---
    tcg_prices = card.get('TCG_Prices')
    if tcg_prices and isinstance(tcg_prices, list):
        for p in tcg_prices:
            if isinstance(p, dict):
                val = _best_price_from_dict(p)
                if val > 0:
                    return val

    # --- 2) tcgplayer dict (from /search response) ---
    tcgplayer = card.get('tcgplayer')
    if tcgplayer and isinstance(tcgplayer, dict):
        prices = tcgplayer.get('prices', {})
        if isinstance(prices, dict):
            val = _best_price_from_dict(prices)
            if val > 0:
                return val
        elif isinstance(prices, list):
            for p in prices:
                if isinstance(p, dict):
                    val = _best_price_from_dict(p)
                    if val > 0:
                        return val

    # --- 3) CardMarket fallback ---
    cardmarket = card.get('cardmarket')
    if cardmarket and isinstance(cardmarket, dict):
        cm_prices = cardmarket.get('prices', [])
        if isinstance(cm_prices, list):
            for p in cm_prices:
                if isinstance(p, dict):
                    val = _best_price_from_dict(p)
                    if val > 0:
                        return val

    # --- 4) Scan ALL top-level keys for any price-like field ---
    for key in card.keys() if isinstance(card, dict) else card.index:
        val = card.get(key)
        if isinstance(val, (int, float)) and val > 0 and 'price' in str(key).lower():
            return float(val)

    return 0.0


def extract_price_series(df: pd.DataFrame) -> pd.Series:
    """Apply price extraction across a DataFrame."""
    return df.apply(lambda row: extract_price_from_card(row), axis=1)


# ============================================================
# CSS STYLING
# ============================================================
st.markdown("""
<style>
    .set-card {
        border: 2px solid #444;
        border-radius: 10px;
        padding: 15px;
        transition: all 0.2s ease;
        text-align: center;
        margin-bottom: 10px;
        background-color: #1a1a2e;
        cursor: pointer;
        min-height: 100px;
    }
    .set-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 16px rgba(0,0,0,0.3);
        border-color: #4CAF50;
    }
    .selected-set-card {
        border: 3px solid #4CAF50 !important;
        box-shadow: 0 0 20px rgba(76, 175, 80, 0.6);
    }
    .set-name {
        font-weight: bold;
        font-size: 1em;
        color: #e0e0e0;
    }
    .set-meta {
        color: #aaa;
        font-size: 0.85em;
        margin-top: 4px;
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
    #cards-section {
        scroll-margin-top: 20px;
        border-top: 3px solid #4CAF50;
        padding-top: 20px;
        margin-top: 20px;
    }
</style>
""", unsafe_allow_html=True)

st.title("Pokemon TCG Sets Explorer")
st.markdown("Browse Pokemon TCG sets with real-time pricing powered by **PokéWallet API**.")


# ============================================================
# SET SELECTION UI
# ============================================================
def select_set(sets_data: pd.DataFrame):
    if 'selected_set' not in st.session_state:
        st.session_state.selected_set = None
        st.session_state.selected_set_code = None
        st.session_state.selected_set_id = None

    search_term = st.text_input("🔍 Search sets:", placeholder="Type to filter sets...")
    if search_term:
        mark_user_active()

    filtered = sets_data.copy()

    # Language filter
    if 'language' in filtered.columns:
        lang_filter = st.checkbox("Show English sets only", value=True)
        if lang_filter:
            filtered = filtered[
                filtered['language'].fillna('eng').isin(['eng'])
            ]

    if search_term:
        filtered = filtered[
            filtered['name'].str.contains(search_term, case=False, na=False)
        ]

    if filtered.empty:
        st.warning("No sets found matching your search.")
        return st.session_state.selected_set

    st.info(f"📊 Showing {len(filtered)} sets")

    num_columns = 4

    for i in range(0, len(filtered), num_columns):
        cols = st.columns(num_columns)
        for j in range(num_columns):
            if i + j < len(filtered):
                set_row = filtered.iloc[i + j]
                with cols[j]:
                    is_selected = st.session_state.selected_set == set_row['name']
                    selected_class = "selected-set-card" if is_selected else ""

                    card_count = set_row.get('card_count', '?')
                    set_code = set_row.get('set_code', '')
                    release = set_row.get('release_date', '')
                    code_display = set_code if set_code else set_row.get('set_id', '')

                    st.markdown(f"""
                    <div class="set-card {selected_class}">
                        <div class="set-name">🃏 {set_row['name']}</div>
                        <div class="set-meta">{code_display} · {card_count} cards</div>
                        <div class="set-meta">{release if release else ''}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    btn_key = f"set_{set_row.get('set_id', '')}_{i+j}"
                    if st.button("📋 Select", key=btn_key,
                                 help=f"Load cards from {set_row['name']}"):
                        mark_user_active()
                        st.session_state.selected_set = set_row['name']
                        st.session_state.selected_set_code = set_row.get('set_code')
                        st.session_state.selected_set_id = set_row.get('set_id')
                        st.session_state.scroll_to_cards = True
                        st.rerun()

    return st.session_state.selected_set


# ============================================================
# CARD DISPLAY
# ============================================================
def display_cards(title: str, cards_data: pd.DataFrame, show_images: bool = True):
    """Display cards in a paginated grid with images and pricing."""
    st.markdown('<div id="cards-section"></div>', unsafe_allow_html=True)
    st.header(f"🃏 {title}")

    if cards_data.empty:
        st.warning("No cards found.")
        return

    total_cards = len(cards_data)

    # Calculate prices
    cards_data = cards_data.copy()
    cards_data['_price'] = extract_price_series(cards_data)
    total_value = cards_data['_price'].sum()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 Total Cards", total_cards)
    with col2:
        st.metric("💰 Estimated Value", f"${total_value:.2f}")
    with col3:
        avg_price = total_value / total_cards if total_cards > 0 else 0
        st.metric("📈 Average Price", f"${avg_price:.2f}")

    # Pagination controls
    cards_per_page = 20
    total_pages = max(1, (total_cards + cards_per_page - 1) // cards_per_page)

    page_key = f'card_page_{title}'
    if page_key not in st.session_state:
        st.session_state[page_key] = 1

    if total_pages > 1:
        page_col1, page_col2, page_col3 = st.columns([1, 2, 1])
        with page_col2:
            current_page = st.number_input(
                f"Page (1–{total_pages})",
                min_value=1,
                max_value=total_pages,
                value=st.session_state[page_key],
                key=f"page_input_{title}"
            )
            st.session_state[page_key] = current_page
    else:
        current_page = 1

    start_idx = (current_page - 1) * cards_per_page
    end_idx = min(start_idx + cards_per_page, total_cards)
    page_cards = cards_data.iloc[start_idx:end_idx]

    st.info(f"📋 Showing cards {start_idx + 1}–{end_idx} of {total_cards}")

    # Render card grid
    num_columns = 4
    for i in range(0, len(page_cards), num_columns):
        cols = st.columns(num_columns)
        for j in range(num_columns):
            idx = i + j
            if idx < len(page_cards):
                card = page_cards.iloc[idx]
                with cols[j]:
                    with st.container():
                        # --- Image ---
                        if show_images:
                            card_id = card.get('id', '')
                            if card_id:
                                img_bytes = fetch_card_image(card_id, size="low")
                                if img_bytes:
                                    st.image(img_bytes, use_column_width=True)
                                else:
                                    st.image(
                                        "https://via.placeholder.com/150x209?text=No+Image",
                                        use_column_width=True
                                    )
                            else:
                                st.image(
                                    "https://via.placeholder.com/150x209?text=No+ID",
                                    use_column_width=True
                                )

                        # --- Card name ---
                        card_name = card.get('name', card.get('clean_name', 'Unknown'))
                        card_number = card.get('card_number', '')
                        rarity = card.get('rarity', '')

                        # Handle nested card_info from /search results
                        card_info = card.get('card_info')
                        if isinstance(card_info, dict):
                            card_name = card_info.get('name', card_name)
                            card_number = card_info.get('card_number', card_number)
                            rarity = card_info.get('rarity', rarity)

                        st.markdown(f"**{card_name}**")
                        if card_number:
                            meta = f"#{card_number}"
                            if rarity:
                                meta += f" · {rarity}"
                            st.caption(meta)

                        # --- Price ---
                        price = card.get('_price', 0.0)
                        if price > 0:
                            st.markdown(
                                f"<p style='margin:2px 0;'><b>💰 Market:</b> "
                                f"<span style='color:#2e7d32;font-weight:bold;'>${price:.2f}</span></p>",
                                unsafe_allow_html=True
                            )
                        else:
                            st.markdown(
                                "<p style='font-style:italic;color:#666;'>💸 Price unavailable</p>",
                                unsafe_allow_html=True
                            )


# ============================================================
# SET SELECTION HANDLER
# ============================================================
def handle_set_selection(set_name: str, set_code: str, set_id: str):
    should_scroll = st.session_state.get('scroll_to_cards', False)
    if should_scroll:
        st.toast(f"📜 Loading {set_name}...", icon="⬇️")
        st.session_state.scroll_to_cards = False

    st.markdown('<div id="cards-section"></div>', unsafe_allow_html=True)

    cards_data = fetch_set_cards_with_progress(set_name, set_code, set_id)

    if not cards_data.empty:
        display_cards(f"Cards from {set_name}", cards_data)

        if should_scroll:
            import streamlit.components.v1 as components
            components.html("""
                <script>
                    setTimeout(function() {
                        const el = window.parent.document.getElementById('cards-section');
                        if (el) el.scrollIntoView({behavior: 'smooth', block: 'start'});
                    }, 200);
                </script>
            """, height=0)
    else:
        st.error(f"❌ No cards found for {set_name}. This set may not have card data in PokéWallet yet (tried codes: {set_code}, {set_id}).")


# ============================================================
# AI CHAT (PokeAI)
# ============================================================
def ai_chat(prompt):
    mark_user_active()
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
        return "Chatbot API key not found."

    MODEL = "meta-llama/llama-3.3-70b-instruct:free"

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            data=json.dumps({
                "model": MODEL,
                "messages": [{"role": "user", "content": formatted_prompt}]
            }),
            timeout=30
        )

        if response.status_code == 200:
            response_data = (
                response.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
        else:
            return f"Error: {response.status_code}, {response.text}"

        json_match = re.search(r'({[\s\S]*})', response_data)
        if json_match:
            parsed = json.loads(json_match.group(1))
            if "request_type" not in parsed or "search_term" not in parsed:
                return "Could not interpret your request. Please try again."
            if parsed["request_type"] not in ["pokemon", "set", "total_cost", "top_cards"]:
                return "Could not interpret your request. Please try again."
            return parsed
        else:
            return "Could not interpret your request. Please try again."

    except Exception as e:
        return f"An error occurred: {str(e)}"


def parse_output(ai_content):
    if isinstance(ai_content, str):
        st.error(ai_content)
        return

    request_type = ai_content["request_type"]
    search_term = ai_content["search_term"]

    if request_type == "pokemon":
        cards = search_cards_with_progress(search_term, f"Searching for **{search_term}** cards")
        if not cards.empty:
            display_cards(f"🔍 {search_term} Cards", cards)
        else:
            st.error(f"No cards found for Pokemon: {search_term}")

    elif request_type == "set":
        cards = search_cards_with_progress(search_term, f"Loading **{search_term}** set")
        if not cards.empty:
            display_cards(f"📦 {search_term} Set", cards)
        else:
            st.error(f"No cards found for set: {search_term}")

    elif request_type == "total_cost":
        cards = search_cards_with_progress(search_term, f"Calculating total cost for **{search_term}**")
        if cards.empty:
            st.error(f"No cards found for: {search_term}")
            return

        cards['_price'] = extract_price_series(cards)
        total_cost = cards['_price'].sum()

        col1, col2 = st.columns(2)
        with col1:
            st.success(f"💰 **Total Cost of '{search_term}':** ${total_cost:.2f}")
        with col2:
            avg_cost = total_cost / len(cards) if len(cards) > 0 else 0
            st.info(f"📊 **Average Card Price:** ${avg_cost:.2f}")

    elif request_type == "top_cards":
        cards = search_cards_with_progress(search_term, f"Finding top cards in **{search_term}**")
        if cards.empty:
            st.error(f"No cards found for: {search_term}")
            return

        cards['_price'] = extract_price_series(cards)
        top_cards = cards.sort_values(by='_price', ascending=False).head(10)
        display_cards(f"🏆 Top 10 Most Expensive — {search_term}", top_cards)


# ============================================================
# MAIN APPLICATION
# ============================================================
def main():
    api_key = get_api_key_pokewallet()
    if not api_key:
        st.error("Cannot proceed without PokéWallet API key. Add POKEWALLET_API_KEY to your Streamlit secrets.")
        return

    st.info("""
    🎯 **Quick Start Guide:**
    - **Sets Tab:** Browse all Pokemon TCG sets with real-time pricing
    - **PokeAI Tab:** Ask questions about cards, sets, and prices
    - Use the search bar to quickly find specific sets
    - Cards are paginated (20 per page) to save API calls & load fast
    """)

    if 'sets_data' not in st.session_state:
        st.session_state.sets_data = None

    tab1, tab2 = st.tabs(["🃏 Sets Explorer", "🤖 PokeAI Assistant"])

    with tab1:
        st.markdown("### Pokemon TCG Sets Collection")

        if st.session_state.sets_data is None:
            with st.spinner("🔄 Loading Pokemon TCG sets from PokéWallet..."):
                all_sets = fetch_all_sets()
                if all_sets is not None and not all_sets.empty:
                    # Sort by release_date descending (most recent first)
                    if 'release_date' in all_sets.columns:
                        all_sets['_sort_date'] = pd.to_datetime(
                            all_sets['release_date'], errors='coerce'
                        )
                        all_sets = all_sets.sort_values(
                            '_sort_date', ascending=False, na_position='last'
                        ).drop(columns=['_sort_date']).reset_index(drop=True)
                    else:
                        all_sets = all_sets[::-1].reset_index(drop=True)
                    st.session_state.sets_data = all_sets
                    st.success(f"🎉 Successfully loaded {len(all_sets)} Pokemon TCG sets!")
                else:
                    st.error("❌ Failed to load sets. Please check your API key and refresh.")
                    return

        if st.session_state.sets_data is not None:
            selected_set = select_set(st.session_state.sets_data)
            if selected_set:
                handle_set_selection(
                    selected_set,
                    st.session_state.get('selected_set_code'),
                    st.session_state.get('selected_set_id'),
                )

    with tab2:
        st.markdown("""
        ### 🤖 PokeAI: Your Pokemon TCG Assistant - Coming Soon!

        """)

    #     user_message = st.text_area(
    #         "Your question:",
    #         height=100,
    #         placeholder="Ask about Pokemon cards, sets, or prices..."
    #     )

    #     if st.button("🚀 Send", help="Submit your question to PokeAI"):
    #         mark_user_active()
    #         if not user_message.strip():
    #             st.error("Please enter a question.")
    #         else:
    #             with st.spinner("🤖 PokeAI is analyzing your request..."):
    #                 ai_response = ai_chat(user_message)
    #             st.markdown("### 🎉 PokeAI Response:")
    #             parse_output(ai_response)

    # st.markdown("---")
    # col1, col2, col3 = st.columns(3)
    # with col1:
    #     st.markdown("🚀 **Reliable & Fast**")
    #     st.caption("PokéWallet API with retry logic")
    # with col2:
    #     st.markdown("📊 **Real-time Pricing**")
    #     st.caption("TCGPlayer & CardMarket data")
    # with col3:
    #     st.markdown("🃏 **Powered by PokéWallet**")
    #     st.caption("50,000+ cards database")


if __name__ == "__main__":
    main()