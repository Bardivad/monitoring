import os
from dotenv import load_dotenv
from apify_client import ApifyClient
import anthropic # Tohle je ten náš nový mozek

# 1. Načtení klíčů (Ujisti se, že máš v .env i ANTHROPIC_API_KEY)
load_dotenv()
APIFY_TOKEN = os.getenv("APIFY_TOKEN")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")

client = ApifyClient(APIFY_TOKEN)
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

with open("cile.txt", "r", encoding="utf-8") as f:
    hledane_vyrazy = [line.strip() for line in f if line.strip() and not line.startswith("#")]

if not hledane_vyrazy:
    print("❌ ZASTAVENO: Nenačetl jsem žádná slova! Zkontroluj soubor cile.txt.")
    exit()

run_input = {
    "searchTerms": hledane_vyrazy, 
    "maxItems": 5, # Pořád testujeme jen na 5 kusech
    "proxyConfig": { "useApifyProxy": True }
}

print("🚀 Startuju Apify scraper...")

try:
    # --- FÁZE 1: ZÍSKÁNÍ DAT ---
    run = client.actor("apidojo/twitter-scraper-lite").call(run_input=run_input)
    print("✅ Apify hotovo, zpracovávám data...")
    dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
    
    # Sbíráme všechny texty do jedné proměnné
    vsechny_tweety = ""
    for tweet in dataset_items:
        text = tweet.get("fullText", "")
        if text:
            vsechny_tweety += f"- {text}\n"

    # --- FÁZE 2: ANALÝZA (CLAUDE) ---
    print("🧠 Předávám data Claudovi k analýze...")
    
    # 1. Načteme šablonu promptu z textáku
    with open("prompt.txt", "r", encoding="utf-8") as f:
        sablona_promptu = f.read()
        
    # 2. Pomocí .format() vložíme naše ulovené tweety přesně tam, kde je v textáku značka {data}
    prompt = sablona_promptu.format(data=vsechny_tweety)

    # Voláme Anthropic API
    response = claude_client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    analyza = response.content[0].text
    analyza = analyza.replace("```html", "").replace("```", "").strip()
    print("✅ Claude má hotovo!")

    # --- FÁZE 3: VYTVOŘENÍ WEBU ---
    print("🌐 Generuji HTML soubor...")
    
    # Jednoduchá šablona pro tvůj GitHub web
    html_obsah = f"""
    <!DOCTYPE html>
    <html lang="cs">
    <head>
        <meta charset="UTF-8">
        <title>Monitoring UA - Svodka</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 800px; margin: 40px auto; line-height: 1.6; color: #333; }}
            h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
            .analyza {{ background: #f9f9f9; padding: 20px; border-radius: 8px; border-left: 5px solid #3498db; }}
        </style>
    </head>
    <body>
        <h1>Vojenský monitoring: Rychlá svodka</h1>
        <div class="analyza">
            {analyza.replace(chr(10), '<br>')}
        </div>
        <p><small>Vygenerováno automaticky pomocí Apify a Claude AI.</small></p>
    </body>
    </html>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_obsah)

    print("🎉 Všechno je hotovo! Otevři si soubor index.html ve svém prohlížeči.")

except Exception as e:
    print(f"❌ Sakra, někde to ruplo: {e}")