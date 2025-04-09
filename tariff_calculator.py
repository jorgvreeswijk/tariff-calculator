import os
import requests
import streamlit as st # Import Streamlit
from datetime import date, timedelta
from dotenv import load_dotenv
import pandas as pd # Import pandas for better table display

# Laad de API-sleutel uit het .env bestand
load_dotenv()
API_KEY = os.getenv("MARKETSTACK_API_KEY")
BASE_URL = "http://api.marketstack.com/v1/"

# Configureer Streamlit pagina
st.set_page_config(layout="wide", page_title="Markt Verlies Calculator")
st.title("📉 Marktontwikkeling sinds 12 Maart 2024 📈")

# Controleer of de API-sleutel is geladen
if not API_KEY:
    st.error("Fout: MARKETSTACK_API_KEY niet gevonden in .env bestand. Zorg dat er een .env bestand is met je sleutel.")
    st.stop() # Stop de app als de sleutel mist

# Definieer de indices en ETFs die we willen volgen
# Let op: Beschikbaarheid en exacte symbolen kunnen variëren bij Marketstack
# Indices (INDX):
indices = {
    "AEX": "AEX.INDX",
    "S&P 500": "GSPC.INDX",
    "FTSE 100": "FTSE.INDX",
    "DAX": "GDAXI.INDX",
    "CAC 40": "FCHI.INDX",
    "Nikkei 225": "N225.INDX",
    "Hang Seng": "HSI.INDX",
}

# ETFs (met geschatte valuta - controleer dit!):
# Het vinden van correcte en beschikbare ETF-tickers kan lastig zijn.
# Deze lijst is een startpunt.
etfs = {
    "iShares AEX UCITS ETF": ("IAEX.AS", "EUR"), # Amsterdam
    "iShares Core S&P 500 UCITS ETF EUR Hedged": ("CSPX.AS", "EUR"), # Amsterdam
    "iShares Core FTSE 100 UCITS ETF": ("ISF.LSE", "GBP"), # London (Let op: in GBP!)
    "iShares Core DAX UCITS ETF": ("EXS1.XETRA", "EUR"), # Xetra
    "Lyxor CAC 40 UCITS ETF": ("LYXCE.XPAR", "EUR"), # Paris
}

START_DATE_STR = "2024-03-12"

# Gebruik caching om API calls te minimaliseren bij herladen app
@st.cache_data(ttl=3600) # Cache data for 1 hour
def get_closest_trading_day_data(symbol, target_date_str):
    """
    Haalt data op voor de dichtstbijzijnde handelsdag *op of voor* de target_date.
    Marketstack's gratis plan ondersteunt geen date range, dus we proberen de exacte dag
    en gaan eventueel een paar dagen terug.
    Retourneert data dict of None bij falen.
    """
    # Plaats een placeholder tijdens het laden
    with st.spinner(f'Ophalen data voor {symbol} rond {target_date_str}...'):
        target_date = date.fromisoformat(target_date_str)
        params = {
            'access_key': API_KEY,
            'symbols': symbol,
        }
        # Probeer tot 5 dagen terug te gaan om een handelsdag te vinden
        for i in range(5):
            current_date_str = (target_date - timedelta(days=i)).isoformat()
            params['date_from'] = current_date_str
            params['date_to'] = current_date_str
            params['limit'] = 1 # Zorg dat we maar 1 resultaat krijgen

            try:
                api_result = requests.get(BASE_URL + "eod", params)
                api_result.raise_for_status()
                json_result = api_result.json()

                if json_result.get("data") and len(json_result["data"]) > 0:
                    data = json_result["data"][0]
                    if data and data.get("close") is not None:
                        retrieved_date_str = data.get("date", "")[:10]
                        if retrieved_date_str == current_date_str:
                            # st.success(f"Data gevonden voor {symbol} op {retrieved_date_str}") # Minder output in UI
                            return data
                # st.write(f"Geen data voor {symbol} op {current_date_str}, probeer vorige...") # Minder output
            except requests.exceptions.RequestException as e:
                st.warning(f"API Fout voor {symbol} op {current_date_str}: {e}")
                return None
            except Exception as e:
                st.warning(f"Verwerkingsfout voor {symbol}: {e}")
                return None

        st.warning(f"Kon geen data vinden voor {symbol} rond {target_date_str}")
        return None

# Gebruik caching om API calls te minimaliseren bij herladen app
@st.cache_data(ttl=3600) # Cache data for 1 hour
def get_latest_trading_day_data(symbol):
    """Haalt de meest recente EOD data op. Retourneert data dict of None."""
    with st.spinner(f'Ophalen meest recente data voor {symbol}...'):
        params = {
            'access_key': API_KEY,
            'symbols': symbol,
            'limit': 1
        }
        try:
            api_result = requests.get(BASE_URL + "eod/latest", params)
            if api_result.status_code == 404:
                # st.write(f"Fallback naar /eod voor {symbol}") # Minder output
                api_result = requests.get(BASE_URL + "eod", params)

            api_result.raise_for_status()
            json_result = api_result.json()

            if json_result.get("data") and len(json_result["data"]) > 0:
                data = json_result["data"][0]
                if data and data.get("close") is not None:
                    retrieved_date_str = data.get("date", "")[:10]
                    # st.success(f"Recente data gevonden voor {symbol} op {retrieved_date_str}") # Minder output
                    return data
            st.warning(f"Geen recente data gevonden voor {symbol}")
            return None
        except requests.exceptions.RequestException as e:
            st.warning(f"API Fout (recent) voor {symbol}: {e}")
            return None
        except Exception as e:
            st.warning(f"Verwerkingsfout (recent) voor {symbol}: {e}")
            return None

# --- Hoofdlogica --- 

st.sidebar.header("Instellingen")
st.sidebar.info(f"Startdatum voor vergelijking: **{START_DATE_STR}**")

# Knop om data te herladen
if st.sidebar.button('Data Herladen'):
    st.cache_data.clear() # Wis de cache
    st.rerun()

# Verzamel resultaten in lijsten voor DataFrames
index_results_list = []
etf_results_list = []

# Verwerk Indices
st.subheader("Indices")
with st.container(): # Gebruik container voor betere layout
    cols = st.columns(len(indices)) # Maak kolommen voor elke index
    col_idx = 0
    for name, symbol in indices.items():
        with cols[col_idx]:
            st.metric(label=f"{name} ({symbol})", value="Laden...", delta="") # Placeholder
            start_data = get_closest_trading_day_data(symbol, START_DATE_STR)
            latest_data = get_latest_trading_day_data(symbol)

            if start_data and latest_data and start_data.get('close') and latest_data.get('close'):
                start_price = start_data['close']
                latest_price = latest_data['close']
                percentage_change = ((latest_price - start_price) / start_price) * 100
                
                # Update de metric
                st.metric(label=f"{name} ({symbol})", 
                          value=f"{latest_price:.2f}", 
                          delta=f"{percentage_change:.2f}%",
                          delta_color="normal") # Kleur wordt automatisch bepaald
                
                index_results_list.append({
                    "Index": name,
                    "Symbool": symbol,
                    "Start Datum": start_data.get("date", "")[:10],
                    "Start Prijs": start_price,
                    "Laatste Datum": latest_data.get("date", "")[:10],
                    "Laatste Prijs": latest_price,
                    "Verandering (%)": percentage_change,
                })
            else:
                st.metric(label=f"{name} ({symbol})", value="Data Fout", delta="")
                index_results_list.append({"Index": name, "Symbool": symbol, "Verandering (%)": "Fout"})
        col_idx += 1

# Verwerk ETFs
st.subheader("ETFs")
with st.container(): 
    cols = st.columns(len(etfs)) # Maak kolommen voor elke ETF
    col_idx = 0
    for name, (symbol, currency) in etfs.items():
        with cols[col_idx]:
            st.metric(label=f"{name} ({symbol})", value="Laden...", delta="") # Placeholder
            start_data = get_closest_trading_day_data(symbol, START_DATE_STR)
            latest_data = get_latest_trading_day_data(symbol)

            if start_data and latest_data and start_data.get('close') and latest_data.get('close'):
                start_price = start_data['close']
                latest_price = latest_data['close']
                absolute_change = latest_price - start_price

                # Update de metric
                st.metric(label=f"{name} ({symbol})", 
                          value=f"{latest_price:.2f} {currency}", 
                          delta=f"{absolute_change:+.2f} {currency}",
                          delta_color="normal") # Kleur wordt automatisch bepaald

                etf_results_list.append({
                    "ETF": name,
                    "Symbool": symbol,
                    "Valuta": currency,
                    "Start Datum": start_data.get("date", "")[:10],
                    "Start Prijs": start_price,
                    "Laatste Datum": latest_data.get("date", "")[:10],
                    "Laatste Prijs": latest_price,
                    "Verandering Absoluut": absolute_change,
                })
            else:
                st.metric(label=f"{name} ({symbol})", value="Data Fout", delta="")
                etf_results_list.append({"ETF": name, "Symbool": symbol, "Verandering Absoluut": "Fout"})
        col_idx += 1

# --- Toon Gedetailleerde Tabellen --- 
st.divider() # Visuele scheiding
st.subheader("Gedetailleerde Resultaten")

tab1, tab2 = st.tabs(["Index Details", "ETF Details"]) 

with tab1:
    if index_results_list:
        index_df = pd.DataFrame(index_results_list)
        # Formatteer de percentages
        index_df['Verandering (%)'] = index_df['Verandering (%)'].apply(lambda x: f"{x:.2f}%" if isinstance(x, (int, float)) else x)
        st.dataframe(index_df, use_container_width=True)
    else:
        st.info("Geen index resultaten om weer te geven.")

with tab2:
    if etf_results_list:
        etf_df = pd.DataFrame(etf_results_list)
        # Formatteer de absolute veranderingen
        etf_df['Verandering Absoluut'] = etf_df.apply(lambda row: f"{row['Verandering Absoluut']:+.2f} {row['Valuta']}" if isinstance(row['Verandering Absoluut'], (int, float)) else row['Verandering Absoluut'], axis=1)
        st.dataframe(etf_df, use_container_width=True)
    else:
        st.info("Geen ETF resultaten om weer te geven.")

st.sidebar.markdown("--- Gemaakt met Marketstack & Streamlit ---") 