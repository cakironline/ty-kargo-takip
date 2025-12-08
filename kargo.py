import streamlit as st
import pandas as pd
import requests
import base64
from datetime import datetime
import time

# -------------------------------------------------------------------
# TELEGRAM AYARLARI
# -------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = "8236447530:AAHauUFiObcgHZftAQhOjO8OwI4kYCygBvg"
TELEGRAM_GROUP_ID = "-1003294991997"

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_GROUP_ID,
        "text": text
    }
    try:
        requests.post(url, data=data, timeout=10)
    except:
        pass

# -------------------------------------------------------------------
# OTOMATİK 5 DAKİKADA BİR YENİLEME
# -------------------------------------------------------------------
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

if time.time() - st.session_state.last_refresh > 300:
    st.session_state.last_refresh = time.time()
    st.rerun()

# -------------------------------------------------------------------
# DAHA ÖNCE BİLDİRİLEN MAĞAZALAR (HAFIZA)
# -------------------------------------------------------------------
if "notified_stores" not in st.session_state:
    st.session_state.notified_stores = set()

# -------------------------------------------------------------------
# Sayfa ayarları
# -------------------------------------------------------------------
st.set_page_config(page_title="Trendyol Kargo Takip", layout="wide")
st.title("📦 Trendyol Kargo Takip")

# -------------------------------------------------------------------
# Hamurlabs API
# -------------------------------------------------------------------
HAMURLABS_URL = "http://dgn.hamurlabs.io/api/order/v2/search/"
HAMURLABS_HEADERS = {
    "Authorization": "Basic c2VsaW0uc2FyaWtheWE6NDMxMzQyNzhDY0A=",
    "Content-Type": "application/json"
}

# -------------------------------------------------------------------
# Trendyol API
# -------------------------------------------------------------------
TRENDYOL_SELLER_ID = "107703"
TRENDYOL_API_KEY = "BTDnnGqkUveH8tSlGFC4"
TRENDYOL_API_SECRET = "wwDwc4pXf4J563N1pJww"

auth_str = f"{TRENDYOL_API_KEY}:{TRENDYOL_API_SECRET}"
auth_base64 = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")

TRENDYOL_HEADERS = {
    "User-Agent": "Trendyol",
    "Authorization": f"Basic {auth_base64}"
}

# -------------------------------------------------------------------
# Warehouse → Mağaza Mapping
# -------------------------------------------------------------------
WAREHOUSE_MAP = {
    "4216": "Ereğli", "27005": "Karataş", "27004": "Gazikent", "6101": "Trabzon",
    "27003": "İpekyolu", "4215": "Meram", "46002": "Binevler", "TOM": "TOM",
    "27001": "Sanko", "4203": "Kampüs", "46001": "Piazza", "4200": "Merkez Ayakkabı",
    "4201": "Merkez Giyim", "4210": "Novada", "4214": "Fabrika Satış",
    "46012": "Oniki Şubat", "27000": "Gazimuhtar", "27002": "Suburcu",
    "4207": "BosnaMix", "4212": "Real", "4206": "Plus", "M": "Aykent Depo",
    "4202": "Sportive"
}

# -------------------------------------------------------------------
# HamurLabs’tan Sipariş Çekme
# -------------------------------------------------------------------
def fetch_hamur_orders(start_date, end_date):
    all_orders = []
    payload = {
        "company_id": "1",
        "updated_at__start": start_date,
        "updated_at__end": end_date,
        "size": 50,
        "start": 0,
        "shop_id": "2",
        "tracker_code": "",
        "order_types": ["selling"]
    }

    while True:
        resp = requests.post(HAMURLABS_URL, headers=HAMURLABS_HEADERS, json=payload)
        if resp.status_code != 200:
            break

        data = resp.json()
        orders = data.get("data", [])
        all_orders.extend(orders)

        total = data.get("total", 0)
        if payload["start"] + payload["size"] >= total:
            break

        payload["start"] += payload["size"]

    return all_orders

# -------------------------------------------------------------------
# Trendyol – shipped tarihi alma
# -------------------------------------------------------------------
def fetch_trendyol_order_status(package_id_raw: str):
    if not package_id_raw:
        return None, None
    try:
        package_id = int(package_id_raw.split("_")[0])
    except:
        return None, None

    url = f"https://apigw.trendyol.com/integration/order/sellers/{TRENDYOL_SELLER_ID}/orders"
    params = {
        "shipmentPackageIds": package_id,
        "size": 1,
        "orderByField": "PackageLastModifiedDate",
        "orderByDirection": "DESC"
    }

    try:
        resp = requests.get(url, headers=TRENDYOL_HEADERS, params=params, timeout=15)
    except:
        return None, None

    if resp.status_code != 200:
        return None, None

    data = resp.json()
    content = data.get("content", [])
    if not content:
        return None, None

    shipment_package = content[0]
    if shipment_package.get("cargoProviderName") != "Trendyol Express Marketplace":
        return None, None

    status = shipment_package.get("status")

    shipped_created_date = None
    for hist in shipment_package.get("packageHistories", []):
        if hist.get("status") == "Shipped":
            shipped_created_date = datetime.fromtimestamp(hist["createdDate"] / 1000)
            break

    return status, shipped_created_date

# -------------------------------------------------------------------
# OTOMATİK ÇALIŞTIR (BUTONSUZ)
# -------------------------------------------------------------------
today = datetime.now()
start = today.strftime("%Y-%m-%d 00:00:00")
end = today.strftime("%Y-%m-%d 23:59:59")

orders = fetch_hamur_orders(start, end)
if not orders:
    st.stop()

df = pd.json_normalize(orders)
df = df[df.get("source") == "Trendyol"]

df["package_id_raw"] = df["tracker_code"].astype(str)
df["store_name"] = df["warehouse_code"].map(WAREHOUSE_MAP)
df["packed_at_dt"] = pd.to_datetime(df.get("packed_at"), errors="coerce")
df["shipped_at_dt"] = pd.to_datetime(df.get("shipped_at"), errors="coerce")

store_samples = {}
today_ts = pd.Timestamp(today).normalize()
yesterday_ts = today_ts - pd.Timedelta(days=1)

for store in df["store_name"].dropna().unique():
    store_df = df[(df["store_name"] == store)]
    packed_df = store_df[
        (~store_df["packed_at_dt"].isna()) &
        (store_df["packed_at_dt"].dt.normalize().isin([yesterday_ts, today_ts]))
    ]
    store_samples[store] = packed_df.head(30)

store_status = {}
store_shipped_date = {}

for store, samples_df in store_samples.items():
    shipped_found = False
    first_shipped_date = None

    for _, row in samples_df.iterrows():
        status, shipped_date = fetch_trendyol_order_status(row["package_id_raw"])

        if status == "Shipped":
            shipped_found = True
            if first_shipped_date is None or (shipped_date and shipped_date < first_shipped_date):
                first_shipped_date = shipped_date

    store_status[store] = shipped_found
    store_shipped_date[store] = first_shipped_date

    # ✅ TELEGRAM BİLDİRİM (SADECE İLK YEŞİLDE)
    if shipped_found and store not in st.session_state.notified_stores:
        st.session_state.notified_stores.add(store)

        if first_shipped_date:
            adjusted_date = first_shipped_date + pd.Timedelta(hours=3)
            saat_str = adjusted_date.strftime("%d.%m.%Y %H:%M")
        else:
            saat_str = "Saat bilgisi yok"

        mesaj = f"""✅ KARGO UĞRADI
🏬 Mağaza: {store}
🕒 Saat: {saat_str}"""

        send_telegram_message(mesaj)

# -------------------------------------------------------------------
# GRID GÖSTERİM
# -------------------------------------------------------------------
sorted_stores = sorted(store_status.items(), key=lambda x: not x[1])
st.subheader("📍 Mağaza Durumları")
stores_per_row = 5
row_columns = []

for i, (store, shipped_ok) in enumerate(sorted_stores):
    if i % stores_per_row == 0:
        row_columns = st.columns(stores_per_row)
    col = row_columns[i % stores_per_row]

    shipped_date = store_shipped_date[store]
    if shipped_ok:
        bg = "#4CAF50"
        status_text = "Kargo Uğradı: "
        if shipped_date:
            adjusted_date = shipped_date + pd.Timedelta(hours=3)
            status_text += adjusted_date.strftime('%d.%m.%Y %H:%M')
    else:
        bg = "#FF4C4C"
        status_text = "Kargo Henüz Uğramamış."

    with col:
        st.markdown(f"""
            <div style='background-color:{bg}; border-radius:12px; padding:20px; height:150px;
                        display:flex; flex-direction:column; justify-content:center;
                        align-items:center; text-align:center; color:white;'>
                <h3 style='margin:0 0 10px 0;'>{store}</h3>
                <p style='margin:0;'>{status_text}</p>
            </div>
        """, unsafe_allow_html=True)
