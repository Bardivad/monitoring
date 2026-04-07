import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from apify_client import ApifyClient
import anthropic

# 1. Načtení klíčů
load_dotenv()
APIFY_TOKEN = os.getenv("APIFY_TOKEN")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")

client = ApifyClient(APIFY_TOKEN)
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

# 2. Kouzlo s časem - zjistíme, kolikátého bylo přesně před 24 hodinami
vcera = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

# 3. Načtení a úprava cílů
hledane_vyrazy = []
with open("cile.txt", "r", encoding="utf-8") as f:
    for line in f:
        cisty_text = line.strip()
        if cisty_text and not cisty_text.startswith("#"):
            # Automaticky přilepíme filtr za posledních 24 hodin
            hledane_vyrazy.append(f"{cisty_text} since:{vcera}")

if not hledane_vyrazy:
    print("❌ ZASTAVENO: Nenačetl jsem žádná slova! Zkontroluj soubor cile.txt.")
    exit()

# Záchranná brzda nastavena na 150 položek celkem
run_input = {
    "searchTerms": hledane_vyrazy, 
    "maxItems": 150, 
    "proxyConfig": { "useApifyProxy": True }
}

print(f"🚀 Startuju Apify scraper (hledám zprávy od: {vcera})...")

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
    
    with open("prompt.txt", "r", encoding="utf-8") as f:
        sablona_promptu = f.read()
        
    prompt = sablona_promptu.format(data=vsechny_tweety)

    # Voláme Anthropic API (s opraveným modelem!)
    response = claude_client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    analyza = response.content[0].text
    analyza = analyza.replace("```html", "").replace("```", "").strip()
    print("✅ Claude má hotovo!")

    # --- FÁZE 3: UKLÁDÁNÍ DO JSON DATABÁZE ---
    print("💾 Ukládám svodku do databáze...")
    
    # Zjistíme dnešní datum pro databázi i pro hezký titulek
    dnesni_datum = datetime.now().strftime("%Y-%m-%d")
    hezke_datum = datetime.now().strftime("%d. %m. %Y")
    
    # Vytvoříme slovník pro dnešní záznam
    novy_zaznam = {
        "datum": dnesni_datum,
        "titulek": f"Svodka {hezke_datum}",
        "obsah": analyza
    }

    # Zkusíme otevřít existující databázi. Když ještě neexistuje, začneme s prázdným seznamem.
    if os.path.exists("databaze.json"):
        with open("databaze.json", "r", encoding="utf-8") as f:
            databaze = json.load(f)
    else:
        databaze = []

    # Zkontrolujeme, jestli už svodka se stejným datem v databázi neexistuje
    existujici_index = next((index for (index, d) in enumerate(databaze) if d["datum"] == dnesni_datum), None)

    if existujici_index is not None:
        # Pokud ano, prostě tu starou dnešní přepíšeme tou novou, čerstvější
        databaze[existujici_index] = novy_zaznam
    else:
        # Pokud ne (je to opravdu nový den), vložíme ji na první místo nahoru
        databaze.insert(0, novy_zaznam)

    # Uložíme přepsanou databázi zpět do souboru
    with open("databaze.json", "w", encoding="utf-8") as f:
        json.dump(databaze, f, ensure_ascii=False, indent=2)

    print("🎉 Databáze úspěšně aktualizována! Podívej se na soubor databaze.json.")

except Exception as e:
    print(f"❌ Sakra, někde to ruplo: {e}")