# Pokemon TCG Explorer

![Pokemon TCG Logo](https://pokemontcg.io/static/media/logo.3b4370bb.svg)

## 🚀 Live Demo

Check out the live application: [https://poketcgai.streamlit.app/](https://poketcgai.streamlit.app/)

## 📝 Description

Pokemon TCG Explorer is a web application that leverages the Pokemon TCG API and AI to help users explore and analyze Pokemon Trading Card Game data. 
The application enables users to search for cards, analyze set values, and find the most valuable cards!

## ✨ Features

- **Pokemon Card Search**: Search for all cards of a specific Pokemon with pricing data
- **Set Display**: View all cards from a specific TCG set
- **Value Analysis**:
  - Find the top 10 most valuable cards of any set
  - Calculate the total cost of completing a set
- **AI-Powered Interface**: Use natural language to interact with the application

## 🛠️ Technologies Used

- **Python**: Core programming language
- **Streamlit**: Web application framework
- **Pokemon TCG SDK**: API integration for card data
- **OpenRouter AI**: Natural language processing for query interpretation
- **Pandas**: Data manipulation and analysis
- **Pillow**: Image processing

## 🔧 Setup and Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/pokemon-tcg-explorer.git
   cd pokemon-tcg-explorer
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up API keys:
   - Register for a Pokemon TCG API key at [https://dev.pokemontcg.io/](https://dev.pokemontcg.io/)
   - Register for an OpenRouter API key at [https://openrouter.ai/](https://openrouter.ai/)
   - Create a `.streamlit/secrets.toml` file with the following content:
     ```toml
     POKEMONTCG_IO_API_KEY = "your_pokemon_tcg_api_key"
     CHATBOT_API_KEY = "your_openrouter_api_key"
     ```

4. Run the application:
   ```bash
   streamlit run app.py
   ```

## 📊 Usage Examples

### Searching for Pokemon Cards
Type a query like: "Show me all cards of Pikachu"

### Viewing a Set
Type a query like: "Display the Brilliant Stars set"

### Finding Valuable Cards
Type a query like: "Show me the most expensive cards in Lost Origin"

### Calculating Set Value
Type a query like: "What's the total cost of the Scarlet & Violet set?"

## 🧩 Project Structure

```
pokemon-tcg-explorer/
├── app.py                  # Main application file
├── requirements.txt        # Dependencies
├── .streamlit/             # Streamlit configuration
│   └── secrets.toml        # API keys (not in repo)
├── assets/                 # Static assets
└── README.md               # This file
```

## 🔍 How It Works

1. The application uses Streamlit to create an interactive web interface
2. User queries are processed by an AI model to determine intent
3. Based on the interpreted intent, the app makes targeted calls to the Pokemon TCG API
4. Results are processed using Pandas and displayed in the Streamlit interface
5. For analytical queries, the application performs calculations on card pricing data

## 🙏 Acknowledgements

- [Pokemon TCG API](https://pokemontcg.io/) for providing the card data
- [Streamlit](https://streamlit.io/) for the web application framework
- [OpenRouter](https://openrouter.ai/) for AI query processing

## 👤 Contact

For questions or feedback, please reach out via:
- GitHub: [@yourusername](https://github.com/rishp66)
- LinkedIn: [Your Name](https://www.linkedin.com/in/rish-pednekar/)

---

⚡ Gotta catch 'em all :)
