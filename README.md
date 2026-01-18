# Pokemon TCG Sets Explorer 🃏

A Streamlit web app for exploring Pokemon Trading Card Game sets, viewing card collections, and checking market prices with an AI-powered assistant.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## Features

- **Browse All Sets** - View all Pokemon TCG sets with logos, sorted newest first
- **Search Sets** - Filter sets by name or ID
- **View Complete Card Lists** - See all cards in any set with images and pricing
- **Market Prices** - Real-time pricing data from TCGPlayer (holofoil, reverse holo, normal)
- **Set Statistics** - Total cards, estimated value, and average card price
- **PokeAI Assistant** - AI chatbot to help find cards and analyze sets

## PokeAI Commands

Ask the AI assistant questions like:
- *"What is the total cost of Base Set?"*
- *"What are the top 10 most expensive cards in Jungle?"*
- *"Show me all cards in Team Rocket set"*
- *"Find all Pikachu cards"*

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/pokemon-tcg-explorer.git
   cd pokemon-tcg-explorer
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up API keys**
   
   Create a `.streamlit/secrets.toml` file:
   ```toml
   POKEMONTCG_IO_API_KEY = "your-pokemon-tcg-api-key"
   CHATBOT_API_KEY = "your-openrouter-api-key"
   ```

   - Get a Pokemon TCG API key at [pokemontcg.io](https://pokemontcg.io/)
   - Get an OpenRouter API key at [openrouter.ai](https://openrouter.ai/)

4. **Run the app**
   ```bash
   streamlit run pokemon_app.py
   ```

## Requirements

```
streamlit
pandas
numpy
requests
pokemontcgsdk
Pillow
streamlit-autorefresh
```

## Deployment on Streamlit Cloud

1. Push your code to GitHub
2. Connect your repo to [Streamlit Cloud](https://streamlit.io/cloud)
3. Add your API keys in the Streamlit Cloud secrets management
4. Deploy!

The app includes a keep-alive feature that auto-refreshes every 4 hours when idle to prevent Streamlit Cloud from putting it to sleep.

## Project Structure

```
├── pokemon_app.py          # Main application file
├── requirements.txt        # Python dependencies
├── README.md              # This file
└── .streamlit/
    └── secrets.toml       # API keys (not committed)
```

## API Usage

This app uses:
- **[Pokemon TCG API](https://pokemontcg.io/)** - Card and set data
- **[TCGPlayer](https://www.tcgplayer.com/)** - Market pricing (via Pokemon TCG API)
- **[OpenRouter](https://openrouter.ai/)** - AI chat (Llama 4 Maverick)

## Performance Features

- Concurrent API calls for faster card loading
- Smart caching (2-hour TTL for sets data)
- Progress tracking with visual feedback
- Optimized DataFrame processing

## License

MIT License - feel free to use and modify for your own projects.

## Contributing

Pull requests welcome! Feel free to open an issue for bugs or feature requests.

---

Built with ❤️ using [Streamlit](https://streamlit.io/) and the [Pokemon TCG API](https://pokemontcg.io/)